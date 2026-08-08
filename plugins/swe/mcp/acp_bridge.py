#!/usr/bin/env python3
"""Expose an Agent Client Protocol agent to Claude Code as an MCP tool.

Motivating failure mode: delegation by shell string. A forwarder subagent that
composes `copilot -p "..."` in Bash re-derives quoting, sandbox flags, timeout
ceilings, and exit-code handling on every call, and "never work the task
yourself" is only a prose rule the model may ignore. Here the caller fills a
JSON schema, and the subagent that calls it is allowed no other tool.

The bridge is also where read-only actually means read-only. Copilot has no
OS-level sandbox the way `codex exec -s read-only` does; ACP instead asks the
client for permission per tool call, so this process answers those requests
itself and rejects every write when the caller asked for read-only. That is the
whole reason to own a bridge rather than shell out.

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

DELEGATE_TOOL = {
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


# ---------------------------------------------------------------------------
# permission policy -- pure, and the security boundary worth testing directly
# ---------------------------------------------------------------------------


def is_inside(path: str, workspace: str) -> bool:
    """True when `path` resolves inside `workspace`.

    Symlinks are resolved first: a write to a symlink pointing out of the
    worktree is a write out of the worktree.
    """
    try:
        resolved = Path(path).resolve()
        root = Path(workspace).resolve()
    except (OSError, ValueError):
        return False
    return resolved == root or root in resolved.parents


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
    Returning that silence as the answer is the failure the codex delegator
    already learned the hard way: a caller cannot tell "nothing to report" from
    "the run was blocked", and acts on the emptiness either way.
    """
    answer = streamed.strip()
    if answer:
        return answer
    if denied:
        blocked = "; ".join(denied)
        return (
            f"The agent returned no message. The bridge denied {len(denied)} tool "
            f"call(s) under mode={mode}: {blocked}. Re-dispatch with mode='write' "
            "if this task is meant to change files."
        )
    return "The agent returned no message."


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------


class Bridge:
    def __init__(self, command: list[str]) -> None:
        self.command = command
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
        with self._lock:
            self.sessions[session_id] = session
        return session, session_id

    def delegate(self, arguments: dict[str, Any], report: Any) -> dict[str, Any]:
        task = arguments["task"]
        mode = arguments["mode"]
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")

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

        if model := arguments.get("model"):
            session.request("session/set_model", {"sessionId": session_id, "modelId": model})

        turn = run_turn(session, session_id, task, mode, report)
        return {"sessionId": session_id, **turn}


def send_mcp(frame: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(frame) + "\n")
    sys.stdout.flush()


def handle_tools_call(bridge: Bridge, message: dict[str, Any]) -> dict[str, Any]:
    params = message.get("params", {})
    if params.get("name") != DELEGATE_TOOL["name"]:
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
            send_mcp({"jsonrpc": "2.0", "id": message_id, "result": {"tools": [DELEGATE_TOOL]}})
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


def main(argv: list[str]) -> int:
    if not argv:
        sys.stderr.write("usage: acp_bridge.py <agent-command> [args...]\n")
        return 2
    serve(Bridge(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
