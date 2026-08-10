#!/usr/bin/env python3
"""Expose an Agent Client Protocol agent to Claude Code as an MCP tool.

Motivating failure mode: delegation by shell string. A forwarder subagent that
composes `opencode run "..."` in Bash re-derives quoting, sandbox flags, timeout
ceilings, and exit-code handling on every call, and "never work the task
yourself" is only a prose rule the model may ignore. Here the caller fills a
JSON schema, and the subagent that calls it is allowed no other tool.

The bridge is also where read-only actually means read-only. An ACP agent has
no OS-level sandbox the way `codex exec -s read-only` does; ACP instead asks the
client for permission per tool call, so this process answers those requests
itself and rejects every write when the caller asked for read-only. That is the
whole reason to own a bridge rather than shell out.

Answering permission requests is not enough on its own, though: OpenCode
auto-approves edits inside the session cwd and never asks, so the kind policy
below simply never fires for them. An agent like that needs its OWN read-only
session mode selected, which `--read-only-mode` does. Writes that escape the
cwd DO come through as permission requests, so the workspace-containment policy
still covers the case the sandbox is really there for.

Both protocols are newline-delimited JSON-RPC over stdio, so the bridge is a
transport translation and a permission policy -- nothing else. One ACP
subprocess per session keeps concurrent delegations independent; the alternative
(one shared agent process) buys nothing here and costs a request multiplexer.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

MCP_PROTOCOL_VERSION = "2025-06-18"
ACP_PROTOCOL_VERSION = 1
SERVER_NAME = "acp-bridge"

# ACP tool kinds a read-only delegation may run. Anything else -- `edit`,
# `delete`, `move`, `execute`, `switch_mode`, `other`, or a kind added to ACP
# after this was written -- is rejected. Failing closed is deliberate: an
# unrecognised kind in a read-only run is exactly the case where guessing is
# unsafe.
READ_ONLY_KINDS = frozenset({"read", "search", "fetch", "think"})

MODES = ("read-only", "write")

# Leading argv flags, ahead of the ACP agent's own command line. `--model` and
# `--effort` pin a server to one model so the caller cannot pick another: model
# policy then lives in the .mcp.json entry, not in a prompt some model has to
# obey. `--read-only-mode` names the agent's own read-only session mode.
BRIDGE_OPTIONS = ("--model", "--effort", "--read-only-mode")

DELEGATE_TOOL: dict[str, Any] = {
    "name": "delegate",
    "title": "Delegate a task to an external coding agent",
    "description": (
        "Run one bounded task on an external Agent Client Protocol agent and "
        "return its final message. The agent explores the workspace itself; "
        "pass the task as it should be worked, not a summary of your findings. "
        "Use mode='read-only' for exploration, review, diagnosis, or planning "
        "-- the bridge rejects every file write the agent attempts. Use "
        "mode='write' only when the task is meant to change files. Pass "
        "sessionId from a previous call to continue that conversation."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["task", "mode"],
        "additionalProperties": False,
        "properties": {
            "task": {
                "type": "string",
                "description": "The task text, forwarded to the agent verbatim.",
            },
            "mode": {
                "type": "string",
                "enum": list(MODES),
                "description": (
                    "read-only rejects the agent's file writes; write allows "
                    "edits inside the workspace."
                ),
            },
            "model": {
                "type": "string",
                "description": "Agent-specific model id. Omit to use its default.",
            },
            "effort": {
                "type": "string",
                "description": (
                    "Reasoning-effort variant, applied as the agent's `effort` "
                    "config option AFTER the model -- the set of legal values "
                    "depends on which model is selected. Agents that expose no "
                    "such option reject it."
                ),
            },
            "cwd": {
                "type": "string",
                "description": (
                    "Absolute workspace root for the agent. Defaults to this "
                    "server's working directory; pass it explicitly when the "
                    "task belongs to a git worktree."
                ),
            },
            "sessionId": {
                "type": "string",
                "description": "Continue a session returned by an earlier call.",
            },
        },
    },
    "outputSchema": {
        "type": "object",
        "required": ["text", "sessionId", "stopReason", "deniedToolCalls"],
        "properties": {
            "text": {"type": "string"},
            "sessionId": {"type": "string"},
            "stopReason": {"type": "string"},
            "deniedToolCalls": {"type": "array", "items": {"type": "string"}},
            "usage": {"type": "object"},
        },
    },
}


def delegate_tool(model: str | None) -> dict[str, Any]:
    """The advertised `delegate` tool, minus anything this server has pinned.

    A pinned server exists precisely so the model is not negotiable, so the
    caller is not offered the choice: dropping the fields is what keeps role
    model policy out of a prompt and in the `.mcp.json` entry.
    """
    if model is None:
        return DELEGATE_TOOL
    schema = dict(DELEGATE_TOOL["inputSchema"])
    schema["properties"] = {
        name: value
        for name, value in schema["properties"].items()
        if name not in ("model", "effort")
    }
    return {
        **DELEGATE_TOOL,
        "description": f"{DELEGATE_TOOL['description']} This server always runs {model}.",
        "inputSchema": schema,
    }


def split_argv(argv: list[str]) -> tuple[dict[str, str], list[str]]:
    """Split the bridge's own leading options from the ACP agent's command.

    Parsing stops at the first token that is not a bridge option, so an agent
    flag that happens to share a name (`some-agent --model x`) is never claimed
    here.
    """
    options: dict[str, str] = {}
    index = 0
    while index < len(argv) and argv[index] in BRIDGE_OPTIONS:
        if index + 1 >= len(argv):
            raise ValueError(f"{argv[index]} needs a value")
        options[argv[index].removeprefix("--").replace("-", "_")] = argv[index + 1]
        index += 2
    return options, argv[index:]


def config_value(config_options: list[dict[str, Any]], config_id: str) -> str | None:
    """The current value of one `session/new` config option, if the agent has it."""
    for option in config_options:
        if option.get("id") == config_id:
            value = option.get("currentValue")
            return value if isinstance(value, str) else None
    return None


# ---------------------------------------------------------------------------
# permission policy -- pure, and the security boundary worth testing directly
# ---------------------------------------------------------------------------


def is_inside(path: str, workspace: str) -> bool:
    """True when `path` stays inside `workspace`, lexically or after resolution.

    Lexical containment sanctions workspace-internal symlinks: a repo that
    plants `docs/agents -> <vault>/projects/<repo>` means writes spelled under
    `docs/agents/` to land there, so a path spelled inside the workspace is
    allowed even when a symlink carries it elsewhere. A path that escapes in
    its own spelling (`..`, an absolute path elsewhere — including a symlink's
    resolved target) is still out. This check was never write mode's hard
    boundary anyway — location-less execute calls pass — the OS sandbox is the
    stronger guarantee.
    """
    try:
        root = Path(workspace)
        candidate = Path(os.path.normpath(root / path))
        resolved = Path(path).resolve()
        resolved_root = root.resolve()
    except (OSError, ValueError):
        return False
    if resolved.is_relative_to(resolved_root):
        return True
    lexical_roots = {Path(os.path.normpath(root)), resolved_root}
    return any(candidate.is_relative_to(lexical) for lexical in lexical_roots)


def select_option(options: list[dict[str, Any]], allow: bool) -> dict[str, Any]:
    """Pick the offered permission option matching the verdict.

    Prefers the one-shot kinds so the bridge never installs a standing grant in
    the agent's session -- every tool call is judged on its own.
    """
    wanted = ("allow_once", "allow_always") if allow else ("reject_once", "reject_always")
    by_kind = {option.get("kind"): option for option in options}
    for kind in wanted:
        option = by_kind.get(kind)
        if option is not None and "optionId" in option:
            return {"outcome": "selected", "optionId": option["optionId"]}
    # The agent offered no option matching the verdict; cancelling is the only
    # honest answer and ACP treats it as "the turn cannot proceed".
    return {"outcome": "cancelled"}


def permission_outcome(
    mode: str,
    tool_call: dict[str, Any],
    options: list[dict[str, Any]],
    workspace: str,
) -> dict[str, Any]:
    """Answer one ACP `session/request_permission` without asking a human.

    read-only: only non-mutating tool kinds pass.
    write: mutating kinds pass when every named location is inside the
    workspace. A tool call naming no location (a shell command, say) is allowed
    in write mode -- ACP does not describe its effects, and a write delegation
    asked for exactly that. Codex's OS-level sandbox is the stronger guarantee
    when a task needs one.
    """
    if mode not in MODES:
        raise ValueError(f"unknown delegation mode {mode!r}; expected one of {MODES}")

    kind = tool_call.get("kind", "other")
    if mode == "read-only":
        return select_option(options, allow=kind in READ_ONLY_KINDS)

    locations = [
        location["path"]
        for location in tool_call.get("locations", [])
        if isinstance(location, dict) and "path" in location
    ]
    escapes = [path for path in locations if not is_inside(path, workspace)]
    return select_option(options, allow=not escapes)


def describe_tool_call(tool_call: dict[str, Any]) -> str:
    """One-line label for a denied call, so the caller learns what was blocked."""
    title = tool_call.get("title") or tool_call.get("toolCallId") or "tool call"
    return f"{tool_call.get('kind', 'other')}: {title}"


# ---------------------------------------------------------------------------
# ACP client
# ---------------------------------------------------------------------------


class AcpSession:
    """One ACP agent subprocess driven over stdio.

    Kept alive between `delegate` calls that share a sessionId so a follow-up
    prompt lands in the same conversation.
    """

    def __init__(self, command: list[str], cwd: str) -> None:
        self.cwd = cwd
        # The agent's own session mode when it opened, so a session reused for a
        # write delegation can be switched back out of read-only.
        self.default_mode: str | None = None
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            cwd=cwd,
        )
        self._next_id = 0
        self._write_lock = threading.Lock()
        self._inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        self._reader = threading.Thread(target=self._read_frames, daemon=True)
        self._reader.start()

    def _read_frames(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._inbox.put(json.loads(line))
            except json.JSONDecodeError:
                continue
        self._inbox.put({"__closed__": True})

    def _send(self, frame: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        with self._write_lock:
            self.process.stdin.write(json.dumps(frame) + "\n")
            self.process.stdin.flush()

    def request(
        self,
        method: str,
        params: dict[str, Any],
        on_frame: Any = None,
    ) -> dict[str, Any]:
        """Send a request and pump frames until its response arrives.

        `on_frame` sees every intervening frame -- notifications to report as
        progress, and agent-to-client requests such as permission prompts.
        """
        self._next_id += 1
        request_id = self._next_id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})

        while True:
            frame = self._inbox.get()
            if frame.get("__closed__"):
                raise RuntimeError(f"the ACP agent exited before answering {method}")
            if frame.get("id") == request_id and ("result" in frame or "error" in frame):
                if "error" in frame:
                    raise RuntimeError(f"{method} failed: {frame['error']}")
                return frame["result"]
            if on_frame is not None:
                reply = on_frame(frame)
                if reply is not None:
                    self._send(reply)

    def close(self) -> None:
        self.process.terminate()


def run_turn(
    session: AcpSession,
    session_id: str,
    task: str,
    mode: str,
    report: Any,
) -> dict[str, Any]:
    """Prompt the agent once and collect its answer.

    The `session/prompt` result carries only a stop reason and token usage, so
    the answer itself is assembled from the streamed message chunks.
    """
    chunks: list[str] = []
    denied: list[str] = []

    def on_frame(frame: dict[str, Any]) -> dict[str, Any] | None:
        method = frame.get("method")
        if method == "session/request_permission" and "id" in frame:
            params = frame.get("params", {})
            tool_call = params.get("toolCall", {})
            outcome = permission_outcome(
                mode, tool_call, params.get("options", []), session.cwd
            )
            if outcome.get("outcome") != "selected" or "reject" in str(
                outcome.get("optionId", "")
            ):
                denied.append(describe_tool_call(tool_call))
            return {"jsonrpc": "2.0", "id": frame["id"], "result": {"outcome": outcome}}

        if method == "session/update":
            update = frame.get("params", {}).get("update", {})
            kind = update.get("sessionUpdate")
            if kind == "agent_message_chunk":
                chunks.append(update.get("content", {}).get("text", ""))
            elif kind == "tool_call":
                report(update.get("title") or update.get("kind") or "working")
        return None

    result = session.request(
        "session/prompt",
        {"sessionId": session_id, "prompt": [{"type": "text", "text": task}]},
        on_frame=on_frame,
    )
    return {
        "text": final_text("".join(chunks), denied, mode),
        "stopReason": result.get("stopReason", "unknown"),
        "usage": result.get("usage", {}),
        "deniedToolCalls": denied,
    }


def final_text(streamed: str, denied: list[str], mode: str) -> str:
    """The agent's answer, or an account of why there isn't one.

    An agent that gets its writes rejected often stops without saying anything.
    Returning that silence as the answer is a failure earlier delegators
    already learned the hard way: a caller cannot tell "nothing to report" from
    "the run was blocked", and acts on the emptiness either way.
    """
    answer = streamed.strip()
    if answer:
        return answer
    if denied:
        blocked = "; ".join(denied)
        remedy = (
            "Re-dispatch with mode='write' if this task is meant to change files."
            if mode == "read-only"
            # A write run's denials are escapes, not the mode: telling the caller
            # to retry in the mode it already used sends it round the same loop.
            else "Every denial named a path outside the workspace; re-scope the "
            "task to the workspace, or dispatch it with a cwd that contains those paths."
        )
        return (
            f"The agent returned no message. The bridge denied {len(denied)} tool "
            f"call(s) under mode={mode}: {blocked}. {remedy}"
        )
    return "The agent returned no message."


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------


class Bridge:
    def __init__(
        self,
        command: list[str],
        model: str | None = None,
        effort: str | None = None,
        read_only_mode: str | None = None,
    ) -> None:
        self.command = command
        self.model = model
        self.effort = effort
        self.read_only_mode = read_only_mode
        self.tool = delegate_tool(model)
        self.sessions: dict[str, AcpSession] = {}
        self._lock = threading.Lock()

    def open_session(self, cwd: str) -> tuple[AcpSession, str]:
        session = AcpSession(self.command, cwd)
        session.request(
            "initialize",
            {
                "protocolVersion": ACP_PROTOCOL_VERSION,
                "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}},
            },
        )
        created = session.request("session/new", {"cwd": cwd, "mcpServers": []})
        session_id = created["sessionId"]
        session.default_mode = config_value(created.get("configOptions", []), "mode")
        with self._lock:
            self.sessions[session_id] = session
        return session, session_id

    def select_model(self, session: AcpSession, session_id: str, model: str, effort: str | None) -> None:
        """Pin the session to one model, then to a reasoning variant of it.

        Order is not cosmetic: an agent's effort values are model-dependent
        (OpenCode offers `high|max` on one model and `none|low|medium|high|
        xhigh|max` on another, and none at all on a third), so the variant can
        only be set once the model is. Both requests raise on an unknown value
        rather than running whatever the agent defaulted to -- a delegation
        that silently ran a different model than the one it was routed to
        would destroy exactly the cost guarantee the routing exists for.
        """
        session.request("session/set_model", {"sessionId": session_id, "modelId": model})
        if effort:
            session.request(
                "session/set_config_option",
                {"sessionId": session_id, "configId": "effort", "value": effort},
            )

    def select_session_mode(self, session: AcpSession, session_id: str, mode: str) -> None:
        """Put the agent in its own read-only mode for a read-only delegation.

        Only for agents configured with `--read-only-mode`: the ones that
        auto-approve their in-workspace writes instead of asking, where the
        permission policy alone never sees the call. Restoring the session's
        opening mode for a write delegation matters when a read-only session is
        continued by id -- otherwise the follow-up's edits are silently refused.
        """
        if not self.read_only_mode:
            return
        # No `mode` option at all means the agent never advertised one on
        # session/new -- there is nothing to select, and for a read-only
        # delegation nothing to enforce with either.
        if session.default_mode is None:
            if mode != "read-only":
                return
            raise RuntimeError(
                f"this server enforces read-only through the agent's {self.read_only_mode!r} "
                "session mode, and the agent advertised no `mode` config option; refusing to "
                "run a read-only delegation unprotected"
            )
        target = self.read_only_mode if mode == "read-only" else session.default_mode
        session.request(
            "session/set_config_option",
            {"sessionId": session_id, "configId": "mode", "value": target},
        )

    def delegate(self, arguments: dict[str, Any], report: Any) -> dict[str, Any]:
        task = arguments["task"]
        mode = arguments["mode"]
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
        if self.model and (arguments.get("model") or arguments.get("effort")):
            raise ValueError(
                f"this server is pinned to model {self.model}"
                f"{f' ({self.effort} effort)' if self.effort else ''}; "
                "drop `model`/`effort` from the call, or use a server that does not pin one"
            )

        session_id = arguments.get("sessionId")
        if session_id:
            with self._lock:
                session = self.sessions.get(session_id)
            if session is None:
                raise ValueError(
                    f"session {session_id} is not open on this bridge; "
                    "omit sessionId to start a fresh one"
                )
        else:
            cwd = arguments.get("cwd") or os.getcwd()
            if not Path(cwd).is_dir():
                raise ValueError(f"cwd {cwd!r} is not a directory")
            session, session_id = self.open_session(cwd)
            if self.model:
                self.select_model(session, session_id, self.model, self.effort)

        if model := arguments.get("model"):
            self.select_model(session, session_id, model, arguments.get("effort"))
        self.select_session_mode(session, session_id, mode)

        turn = run_turn(session, session_id, task, mode, report)
        return {"sessionId": session_id, **turn}


def send_mcp(frame: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(frame) + "\n")
    sys.stdout.flush()


def handle_tools_call(bridge: Bridge, message: dict[str, Any]) -> dict[str, Any]:
    params = message.get("params", {})
    if params.get("name") != bridge.tool["name"]:
        raise ValueError(f"unknown tool {params.get('name')!r}")

    progress_token = params.get("_meta", {}).get("progressToken")
    step = 0

    def report(label: str) -> None:
        """Progress keeps a long delegation off the stdio idle timeout."""
        nonlocal step
        if progress_token is None:
            return
        step += 1
        send_mcp(
            {
                "jsonrpc": "2.0",
                "method": "notifications/progress",
                "params": {
                    "progressToken": progress_token,
                    "progress": step,
                    "message": label,
                },
            }
        )

    result = bridge.delegate(params.get("arguments", {}), report)
    return {
        "content": [{"type": "text", "text": result["text"]}],
        "structuredContent": result,
    }


def serve(bridge: Bridge) -> None:
    """Read newline-delimited MCP frames from stdin until it closes.

    Each tool call runs on its own thread: two delegations dispatched in
    parallel by the caller should run in parallel here too.
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = message.get("method")
        message_id = message.get("id")

        if method == "initialize":
            send_mcp(
                {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": {
                        "protocolVersion": MCP_PROTOCOL_VERSION,
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": SERVER_NAME, "version": "1.0.0"},
                    },
                }
            )
        elif method == "tools/list":
            send_mcp({"jsonrpc": "2.0", "id": message_id, "result": {"tools": [bridge.tool]}})
        elif method == "tools/call":
            threading.Thread(
                target=_run_tool_call, args=(bridge, message), daemon=True
            ).start()
        elif message_id is not None:
            send_mcp(
                {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "error": {"code": -32601, "message": f"method not found: {method}"},
                }
            )


def _run_tool_call(bridge: Bridge, message: dict[str, Any]) -> None:
    try:
        result = handle_tools_call(bridge, message)
    except Exception as error:  # surfaced to the caller, never swallowed
        result = {
            "content": [{"type": "text", "text": f"{type(error).__name__}: {error}"}],
            "isError": True,
        }
    send_mcp({"jsonrpc": "2.0", "id": message["id"], "result": result})


USAGE = (
    "usage: acp_bridge.py [--model ID] [--effort LEVEL] [--read-only-mode MODE] "
    "<agent-command> [args...]\n"
)


def main(argv: list[str]) -> int:
    try:
        options, command = split_argv(argv)
    except ValueError as error:
        sys.stderr.write(f"{error}\n{USAGE}")
        return 2
    if not command:
        sys.stderr.write(USAGE)
        return 2
    serve(Bridge(command, **options))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
