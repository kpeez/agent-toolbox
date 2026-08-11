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
from typing import Any, Literal

MCP_PROTOCOL_VERSION = "2025-06-18"
ACP_PROTOCOL_VERSION = 1
SERVER_NAME = "acp-bridge"

# ACP tool kinds a read-only delegation may run. Anything else -- `edit`,
# `delete`, `move`, `execute`, `switch_mode`, `other`, or a kind added to ACP
# after this was written -- is rejected. Failing closed is deliberate: an
# unrecognised kind in a read-only run is exactly the case where guessing is
# unsafe.
READ_ONLY_KINDS = frozenset({"read", "search", "fetch", "think"})

MODES = ("read-only", "review", "write")

ACP_STDERR_TAIL_BYTES = 4096
ACP_STDERR_READ_BYTES = 1024
CANCEL_GRACE_SECONDS = 2.0
MESSAGE_PROGRESS_INTERVAL = 200

# Leading argv flags, ahead of the ACP agent's own command line. `--model` and
# `--effort` pin a server to one model so the caller cannot pick another: model
# policy then lives in the .mcp.json entry, not in a prompt some model has to
# obey. `--read-only-mode` names the agent's own read-only session mode.
BRIDGE_OPTIONS = ("--model", "--effort", "--read-only-mode", "--mode", "--turn-timeout")

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
    review: non-mutating tool kinds and execute pass.
    write: read-only kinds pass regardless of location; remaining kinds pass
    when every named location is inside the workspace. A tool call naming no
    location (a shell command, say) is allowed in write mode -- ACP does not
    describe its effects, and a write delegation asked for exactly that.
    Codex's OS-level sandbox is the stronger guarantee when a task needs one.
    """
    if mode not in MODES:
        raise ValueError(f"unknown delegation mode {mode!r}; expected one of {MODES}")

    kind = tool_call.get("kind", "other")
    if mode == "read-only":
        return select_option(options, allow=kind in READ_ONLY_KINDS)
    if mode == "review":
        return select_option(options, allow=kind in READ_ONLY_KINDS or kind == "execute")
    if kind in READ_ONLY_KINDS:
        return select_option(options, allow=True)

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


class AcpRequestError(RuntimeError):
    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        self.exit_code = exit_code


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
        self.load_session = False
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=cwd,
        )
        self._next_id = 0
        self._write_lock = threading.Lock()
        self._request_lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._closed = threading.Event()
        self._stderr_lock = threading.Lock()
        self._stderr_closed = threading.Event()
        self._stderr_bytes = 0
        self._stderr_tail = bytearray()
        self._inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        self._reader = threading.Thread(target=self._read_frames, daemon=True)
        self._stderr_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self._reader.start()
        self._stderr_reader.start()

    def _read_frames(self) -> None:
        assert self.process.stdout is not None
        try:
            for line in self.process.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    self._inbox.put(json.loads(line))
                except json.JSONDecodeError:
                    continue
        finally:
            self._closed.set()
            self._inbox.put({"__closed__": True})

    def _read_stderr(self) -> None:
        """Drain stderr and retain only a bounded raw tail."""
        try:
            assert self.process.stderr is not None
            while chunk := os.read(self.process.stderr.fileno(), ACP_STDERR_READ_BYTES):
                with self._stderr_lock:
                    self._stderr_bytes += len(chunk)
                    self._stderr_tail.extend(chunk)
                    if len(self._stderr_tail) > ACP_STDERR_TAIL_BYTES:
                        del self._stderr_tail[:-ACP_STDERR_TAIL_BYTES]
        except OSError:
            pass
        finally:
            self._stderr_closed.set()

    def enrich_request_error(self, error: AcpRequestError) -> AcpRequestError:
        """Append safe stderr metadata after the child has been cleaned up."""
        self._stderr_closed.wait()
        with self._stderr_lock:
            byte_count = self._stderr_bytes
            stderr_tail = bytes(self._stderr_tail).decode(errors="replace")
            is_truncated = self._stderr_bytes > ACP_STDERR_TAIL_BYTES
        fields = [
            f"bytes={byte_count}",
            f"truncated={str(is_truncated).lower()}",
            f"tail={stderr_tail}",
        ]
        if error.exit_code is not None:
            fields.append(f"exitCode={error.exit_code}")
        metadata = "; ".join(fields)
        return AcpRequestError(f"{error}\n\nACP stderr metadata: {metadata}", error.exit_code)

    def _send(self, frame: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        with self._write_lock:
            self.process.stdin.write(json.dumps(frame) + "\n")
            self.process.stdin.flush()

    def notify(self, method: str, params: dict[str, Any]) -> None:
        """Send an id-less JSON-RPC notification alongside the request pump."""
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

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
        with self._request_lock:
            if self._closed.is_set() or self.process.poll() is not None:
                raise AcpRequestError(
                    f"the ACP agent exited before answering {method}", self.process.poll()
                )
            self._next_id += 1
            request_id = self._next_id
            try:
                self._send(
                    {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
                )
            except OSError as error:
                raise AcpRequestError(
                    f"{method} failed: {error}", self.process.poll()
                ) from error

            while True:
                frame = self._inbox.get()
                if frame.get("__closed__"):
                    raise AcpRequestError(
                        f"the ACP agent exited before answering {method}", self.process.poll()
                    )
                if frame.get("id") == request_id and ("result" in frame or "error" in frame):
                    if "error" in frame:
                        raise AcpRequestError(f"{method} failed: {frame['error']}")
                    return frame["result"]
                if on_frame is not None:
                    reply = on_frame(frame)
                    if reply is not None:
                        try:
                            self._send(reply)
                        except OSError as error:
                            raise AcpRequestError(
                                f"{method} failed: {error}", self.process.poll()
                            ) from error

    def close(self) -> None:
        with self._close_lock:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            self.process.wait()
            self._stderr_closed.wait()


class ToolCallCancelled(RuntimeError):
    pass


class TurnTimeout(RuntimeError):
    pass


class ActiveCall:
    """The one ACP process owned by an active MCP tools/call request.

    A session survives a cancel iff the agent ends the turn before the grace
    timer fires.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session: AcpSession | None = None
        self._session_id: str | None = None
        self._cancel_reason: Literal["cancelled", "timeout"] | None = None
        self._completed = False
        self._prompt_started = False
        self._cancel_timer: threading.Timer | None = None

    def attach(self, session: AcpSession, session_id: str | None) -> None:
        with self._lock:
            self._session = session
            self._session_id = session_id
            should_close = self._cancel_reason is not None and not self._completed
        if should_close:
            session.close()
            raise ToolCallCancelled("tool call cancelled")

    def cancel(self, reason: Literal["cancelled", "timeout"] = "cancelled") -> AcpSession | None:
        with self._lock:
            if self._completed:
                return None
            if self._cancel_reason is not None:
                return self._session
            self._cancel_reason = reason
            session = self._session
            session_id = self._session_id
            if session is None:
                return None
            if session_id is None or not self._prompt_started:
                close_immediately = True
            else:
                close_immediately = False
                timer = threading.Timer(CANCEL_GRACE_SECONDS, self._close_session)
                timer.daemon = True
                self._cancel_timer = timer
                timer.start()
        if close_immediately:
            session.close()
            return None
        try:
            session.notify("session/cancel", {"sessionId": session_id})
        except OSError:
            pass
        return session

    def _close_session(self) -> None:
        with self._lock:
            if self._completed:
                return
            session = self._session
        if session is not None:
            session.close()

    def complete(self) -> None:
        with self._lock:
            self._completed = True
            timer = self._cancel_timer
            self._cancel_timer = None
            self._session = None
            self._session_id = None
        if timer is not None:
            timer.cancel()

    def start_prompt(self) -> None:
        with self._lock:
            if self._cancel_reason is not None:
                raise ToolCallCancelled("tool call cancelled")
            self._prompt_started = True

    def raise_if_cancelled(self) -> None:
        with self._lock:
            cancel_reason = self._cancel_reason
        if cancel_reason is not None:
            raise ToolCallCancelled("tool call cancelled")

    def cancel_reason(self) -> Literal["cancelled", "timeout"] | None:
        with self._lock:
            return self._cancel_reason

    def is_completed(self) -> bool:
        with self._lock:
            return self._completed


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
    unreported_text = ""

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
                nonlocal unreported_text
                content = update.get("content", {})
                if content.get("type") == "text":
                    text = content.get("text", "")
                else:
                    content_type = content.get("type")
                    text = (
                        f"[{content_type} omitted]"
                        if content_type
                        else "[non-text content omitted]"
                    )
                chunks.append(text)
                unreported_text += text
                while len(unreported_text) >= MESSAGE_PROGRESS_INTERVAL:
                    report(" ".join(unreported_text.split())[-MESSAGE_PROGRESS_INTERVAL:])
                    unreported_text = unreported_text[MESSAGE_PROGRESS_INTERVAL:]
            elif kind in ("tool_call", "tool_call_update"):
                if chunks:
                    chunks.clear()
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
    has_execute_denial = any(call.split(":", 1)[0] == "execute" for call in denied)
    should_report_denials = mode == "write" or has_execute_denial
    if answer and not (denied and should_report_denials):
        return answer
    if denied and should_report_denials:
        blocked = "; ".join(denied)
        remedy = (
            "Re-dispatch with mode='write' if this task is meant to change files."
            if mode == "read-only"
            # A write run's denials are escapes, not the mode: telling the caller
            # to retry in the mode it already used sends it round the same loop.
            else "Every denial named a path outside the workspace; re-scope the "
            "task to the workspace, or dispatch it with a cwd that contains those paths."
        )
        account = (
            f"The bridge denied {len(denied)} tool call(s) under mode={mode}: "
            f"{blocked}. {remedy}"
        )
        if answer:
            return f"{answer}\n\n---\n\n{account}"
        return f"The agent returned no message. {account}"
    if answer:
        return answer
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
        mode: str | None = None,
        turn_timeout: float | None = None,
    ) -> None:
        if mode is not None and mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
        self.command = command
        self.model = model
        self.effort = effort
        self.read_only_mode = read_only_mode
        self.mode = mode
        self.turn_timeout = turn_timeout
        self.tool = delegate_tool(model)
        self.sessions: dict[str, AcpSession] = {}
        self.active_calls: dict[Any, ActiveCall] = {}
        self._lock = threading.Lock()

    def open_session(
        self, cwd: str, active_call: ActiveCall, session_id: str | None = None
    ) -> tuple[AcpSession, str]:
        session = AcpSession(self.command, cwd)
        try:
            active_call.attach(session, None)
            initialized = session.request(
                "initialize",
                {
                    "protocolVersion": ACP_PROTOCOL_VERSION,
                    "clientCapabilities": {
                        "fs": {"readTextFile": False, "writeTextFile": False}
                    },
                },
            )
            capabilities = initialized.get("agentCapabilities", {})
            session.load_session = isinstance(capabilities, dict) and capabilities.get(
                "loadSession", False
            ) is True
            if session_id is None:
                opened = session.request("session/new", {"cwd": cwd, "mcpServers": []})
            else:
                if not session.load_session:
                    raise ValueError(
                        f"session {session_id} is not open on this bridge; "
                        "omit sessionId to start a fresh one"
                    )
                opened = session.request(
                    "session/load",
                    {"sessionId": session_id, "cwd": cwd, "mcpServers": []},
                    on_frame=lambda _frame: None,
                )
            opened_session_id = opened["sessionId"]
            active_call.attach(session, opened_session_id)
            session.default_mode = config_value(opened.get("configOptions", []), "mode")
            with self._lock:
                self.sessions[opened_session_id] = session
            return session, opened_session_id
        except AcpRequestError as error:
            session.close()
            raise session.enrich_request_error(error) from error
        except Exception:
            session.close()
            raise

    def discard_session(self, session_id: str | None, session: AcpSession) -> None:
        if session_id is not None:
            with self._lock:
                if self.sessions.get(session_id) is session:
                    del self.sessions[session_id]
        session.close()

    def start_call(self, request_id: Any) -> ActiveCall:
        active_call = ActiveCall()
        with self._lock:
            self.active_calls[request_id] = active_call
        return active_call

    def cancel_call(self, request_id: Any) -> None:
        with self._lock:
            active_call = self.active_calls.get(request_id)
        if active_call is not None:
            active_call.cancel()

    def finish_call(self, request_id: Any, active_call: ActiveCall) -> None:
        with self._lock:
            if self.active_calls.get(request_id) is active_call:
                del self.active_calls[request_id]

    def close(self) -> None:
        """Stop active and retained ACP children when the MCP transport closes."""
        with self._lock:
            active_calls = list(self.active_calls.values())
            sessions = list(self.sessions.values())
            self.active_calls.clear()
            self.sessions.clear()
        for active_call in active_calls:
            if session := active_call.cancel():
                sessions.append(session)
        sessions_by_identity = {id(session): session for session in sessions}
        for session in sessions_by_identity.values():
            session.close()

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

    def session_for_call(
        self, arguments: dict[str, Any], active_call: ActiveCall
    ) -> tuple[AcpSession, str]:
        session_id = arguments.get("sessionId")
        if session_id:
            with self._lock:
                session = self.sessions.get(session_id)
            if session is not None:
                active_call.attach(session, session_id)
                return session, session_id

        cwd = arguments.get("cwd") or os.getcwd()
        if not Path(cwd).is_dir():
            raise ValueError(f"cwd {cwd!r} is not a directory")
        session, opened_session_id = self.open_session(cwd, active_call, session_id)
        if self.model:
            self.select_model(session, opened_session_id, self.model, self.effort)
        return session, opened_session_id

    def delegate(
        self, arguments: dict[str, Any], report: Any, active_call: ActiveCall
    ) -> dict[str, Any]:
        task = arguments["task"]
        mode = arguments["mode"]
        if self.mode is not None and mode != self.mode:
            raise ValueError(
                f"this server is pinned to mode {self.mode}; requested mode was {mode}"
            )
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
        if self.model and (arguments.get("model") or arguments.get("effort")):
            raise ValueError(
                f"this server is pinned to model {self.model}"
                f"{f' ({self.effort} effort)' if self.effort else ''}; "
                "drop `model`/`effort` from the call, or use a server that does not pin one"
            )

        session: AcpSession | None = None
        session_id = arguments.get("sessionId")
        try:
            active_call.raise_if_cancelled()
            session, session_id = self.session_for_call(arguments, active_call)

            if model := arguments.get("model"):
                self.select_model(session, session_id, model, arguments.get("effort"))
            self.select_session_mode(session, session_id, mode)

            active_call.start_prompt()
            timeout_timer: threading.Timer | None = None
            if self.turn_timeout is not None:
                timeout_timer = threading.Timer(
                    self.turn_timeout, active_call.cancel, args=("timeout",)
                )
                timeout_timer.daemon = True
                timeout_timer.start()
            try:
                turn = run_turn(session, session_id, task, mode, report)
            finally:
                if timeout_timer is not None:
                    timeout_timer.cancel()

            if active_call.cancel_reason() == "timeout":
                active_call.complete()
                raise TurnTimeout(
                    f"turn timed out after {self.turn_timeout} seconds; "
                    f"session {session_id} retained"
                )
            active_call.complete()
            return {"sessionId": session_id, **turn}
        except Exception as error:
            cancel_reason = active_call.cancel_reason()
            completed = active_call.is_completed()
            if session is not None and not (cancel_reason == "timeout" and completed):
                self.discard_session(session_id, session)
            if cancel_reason == "timeout":
                if isinstance(error, TurnTimeout):
                    raise
                retained = f"; session {session_id} retained" if completed else ""
                raise TurnTimeout(
                    f"turn timed out after {self.turn_timeout} seconds{retained}"
                ) from error
            if cancel_reason == "cancelled" and not isinstance(error, ToolCallCancelled):
                raise ToolCallCancelled("tool call cancelled") from error
            if session is not None and isinstance(error, AcpRequestError):
                raise session.enrich_request_error(error) from error
            raise


def send_mcp(frame: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(frame) + "\n")
    sys.stdout.flush()


def handle_tools_call(
    bridge: Bridge, message: dict[str, Any], active_call: ActiveCall
) -> dict[str, Any]:
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

    result = bridge.delegate(params.get("arguments", {}), report, active_call)
    return {
        "content": [{"type": "text", "text": result["text"]}],
        "structuredContent": result,
    }


def serve(bridge: Bridge) -> None:
    """Read newline-delimited MCP frames from stdin until it closes.

    Each tool call runs on its own thread: two delegations dispatched in
    parallel by the caller should run in parallel here too.
    """
    try:
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
                send_mcp(
                    {
                        "jsonrpc": "2.0",
                        "id": message_id,
                        "result": {"tools": [bridge.tool]},
                    }
                )
            elif method == "tools/call":
                active_call = bridge.start_call(message_id)
                threading.Thread(
                    target=_run_tool_call,
                    args=(bridge, message, active_call),
                    daemon=True,
                ).start()
            elif method == "notifications/cancelled":
                bridge.cancel_call(message.get("params", {}).get("requestId"))
            elif message_id is not None:
                send_mcp(
                    {
                        "jsonrpc": "2.0",
                        "id": message_id,
                        "error": {"code": -32601, "message": f"method not found: {method}"},
                    }
                )
    finally:
        bridge.close()


def _run_tool_call(
    bridge: Bridge, message: dict[str, Any], active_call: ActiveCall
) -> None:
    try:
        result = handle_tools_call(bridge, message, active_call)
    except Exception as error:  # surfaced to the caller, never swallowed
        result = {
            "content": [{"type": "text", "text": f"{type(error).__name__}: {error}"}],
            "isError": True,
        }
    finally:
        bridge.finish_call(message["id"], active_call)
    send_mcp({"jsonrpc": "2.0", "id": message["id"], "result": result})


USAGE = (
    "usage: acp_bridge.py [--model ID] [--effort LEVEL] [--read-only-mode MODE] "
    "[--turn-timeout SECONDS] "
    "<agent-command> [args...]\n"
)


def main(argv: list[str]) -> int:
    try:
        options, command = split_argv(argv)
        turn_timeout = None
        if "turn_timeout" in options:
            turn_timeout = float(options["turn_timeout"])
            if not turn_timeout > 0:
                raise ValueError("--turn-timeout must be greater than 0")
    except ValueError as error:
        sys.stderr.write(f"{error}\n{USAGE}")
        return 2
    if not command:
        sys.stderr.write(USAGE)
        return 2
    serve(
        Bridge(
            command,
            model=options.get("model"),
            effort=options.get("effort"),
            read_only_mode=options.get("read_only_mode"),
            mode=options.get("mode"),
            turn_timeout=turn_timeout,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
