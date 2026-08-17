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
session mode selected, which the explorer profile's `session_mode` does. Writes that escape the
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
import time
from dataclasses import dataclass, field
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
OPENCODE_TOOLS = ("explore", "implement", "review")
DEFAULT_ROLES_PATH = Path(__file__).resolve().parents[1] / "roles.json"

ACP_STDERR_TAIL_BYTES = 4096
ACP_STDERR_READ_BYTES = 1024
CANCEL_GRACE_SECONDS = 2.0
MESSAGE_PROGRESS_INTERVAL = 200
LIVENESS_TIMEOUT_SECONDS = 30.0
RECOVERY_PROMPT = (
    "The completed task needs its final answer. Return that answer now without "
    "repeating any work."
)
_MCP_WRITE_LOCK = threading.Lock()

# Leading argv flags, ahead of the ACP agent's own command line. The roles file
# is the only profile input; callers select one of the fixed tools instead.
BRIDGE_OPTIONS = (
    "--roles",
    "--turn-timeout",
)

@dataclass(frozen=True)
class RoleProfile:
    tool: str
    model: str
    effort: str
    mode: str
    session_mode: str | None


def load_profiles(path: str | Path) -> dict[str, RoleProfile]:
    data = json.loads(Path(path).read_text())
    roles = data.get("roles")
    if not isinstance(roles, dict):
        raise ValueError("roles file must contain a roles object")

    profiles: dict[str, RoleProfile] = {}
    for role_name, role in roles.items():
        pin = role.get("opencode") if isinstance(role, dict) else None
        if not isinstance(pin, dict):
            continue
        tool = pin.get("tool")
        if not isinstance(tool, str) or tool not in OPENCODE_TOOLS:
            raise ValueError(f"invalid OpenCode tool for {role_name}: {tool!r}")
        if tool in profiles:
            raise ValueError(f"duplicate OpenCode tool: {tool}")
        mode = pin.get("mode")
        if mode not in MODES:
            raise ValueError(f"invalid OpenCode mode for {role_name}: {mode!r}")
        model = pin.get("model")
        effort = pin.get("effort")
        if not isinstance(model, str) or not isinstance(effort, str):
            raise ValueError(f"incomplete OpenCode profile for {role_name}")
        session_mode = pin.get("session_mode")
        if session_mode is not None and not isinstance(session_mode, str):
            raise ValueError(f"invalid OpenCode session mode for {role_name}")
        profiles[tool] = RoleProfile(tool, model, effort, mode, session_mode)

    if set(profiles) != set(OPENCODE_TOOLS):
        raise ValueError(f"roles file must define exactly {OPENCODE_TOOLS} OpenCode tools")
    return profiles


def role_tool(profile: RoleProfile) -> dict[str, Any]:
    return {
        "name": profile.tool,
        "title": f"OpenCode {profile.tool} task",
        "description": (
            f"Run one bounded {profile.tool} task through the fixed OpenCode profile. "
            "The profile is selected by this tool and cannot be changed by the caller."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["task", "cwd"],
            "additionalProperties": False,
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task text, forwarded to the agent verbatim.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Absolute workspace root for this task.",
                },
                "sessionId": {
                    "type": "string",
                    "description": "Continue a session returned by this same role tool.",
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


def split_argv(argv: list[str]) -> tuple[dict[str, str], list[str]]:
    """Split the bridge's own leading options from the ACP agent's command.

    Parsing stops at the first token that is not a bridge option, so an agent
    flag that happens to share a name (`some-agent --roles x`) is never claimed
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


@dataclass
class TurnObservation:
    """Safe accounting for one or more ACP prompt turns."""

    event_counts: dict[str, int]
    last_activity: str | None = None
    last_activity_at: float | None = None
    non_text_content_types: dict[str, int] = field(default_factory=dict)

    @classmethod
    def create(cls) -> TurnObservation:
        return cls(event_counts={})

    def record(self, kind: str) -> None:
        self.event_counts[kind] = self.event_counts.get(kind, 0) + 1
        self.last_activity = kind
        self.last_activity_at = time.time()

    def record_non_text(self, content_type: str | None) -> None:
        kind = content_type if content_type else "unknown"
        self.non_text_content_types[kind] = self.non_text_content_types.get(kind, 0) + 1

    def merge(self, other: TurnObservation) -> None:
        for kind, count in other.event_counts.items():
            self.event_counts[kind] = self.event_counts.get(kind, 0) + count
        if other.last_activity_at is not None and (
            self.last_activity_at is None or other.last_activity_at >= self.last_activity_at
        ):
            self.last_activity = other.last_activity
            self.last_activity_at = other.last_activity_at
        for kind, count in other.non_text_content_types.items():
            self.non_text_content_types[kind] = self.non_text_content_types.get(kind, 0) + count

    def metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "eventCounts": dict(self.event_counts),
            "lastActivity": self.last_activity,
            "lastActivityAt": self.last_activity_at,
        }
        if self.non_text_content_types:
            metadata["nonTextContentTypes"] = dict(self.non_text_content_types)
        return metadata


class TurnActivity:
    """Serialize real ACP activity and one honest inactivity notice."""

    LABELS = {
        "agent_message_chunk": "agent message",
        "tool_call": "tool call",
        "tool_call_update": "tool call update",
        "permission_request": "permission request",
    }

    def __init__(
        self,
        session: AcpSession,
        report: Any,
        observation: TurnObservation,
        timeout: float = LIVENESS_TIMEOUT_SECONDS,
    ) -> None:
        self.session = session
        self.report = report
        self.observation = observation
        self.timeout = timeout
        self._lock = threading.Lock()
        self._last_event = time.monotonic()
        self._timer: threading.Timer | None = None
        self._stopped = False
        self._liveness_sent = False

    def start(self) -> None:
        with self._lock:
            self._schedule_locked(self.timeout)

    def event(self, kind: str) -> None:
        with self._lock:
            if self._stopped:
                return
            self.observation.record(kind)
            self._last_event = time.monotonic()
            self._schedule_locked(self.timeout)
            self.report(self.LABELS.get(kind, "ACP event"))

    def stop(self) -> None:
        with self._lock:
            self._stopped = True
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def _schedule_locked(self, delay: float) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(max(delay, 0.001), self._check_liveness)
        self._timer.daemon = True
        self._timer.start()

    def _check_liveness(self) -> None:
        with self._lock:
            self._timer = None
            if self._stopped or self._liveness_sent or self.session.process.poll() is not None:
                return
            elapsed = time.monotonic() - self._last_event
            if elapsed < self.timeout:
                self._schedule_locked(self.timeout - elapsed)
                return
            self._liveness_sent = True
            self.report("liveness: child process is alive; no ACP event arrived for 30 seconds")


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
    liveness_timeout: float = LIVENESS_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Prompt the agent once and collect its answer.

    The `session/prompt` result carries only a stop reason and token usage, so
    the answer itself is assembled from the streamed message chunks.
    """
    chunks: list[str] = []
    text_chunks: list[str] = []
    denied: list[str] = []
    observation = TurnObservation.create()
    activity = TurnActivity(session, report, observation, timeout=liveness_timeout)

    def on_frame(frame: dict[str, Any]) -> dict[str, Any] | None:
        method = frame.get("method")
        if method == "session/request_permission" and "id" in frame:
            activity.event("permission_request")
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
            if not isinstance(kind, str):
                kind = "unknown_update"
            activity.event(kind)
            if kind == "agent_message_chunk":
                content = update.get("content", {})
                if content.get("type") == "text":
                    text = content.get("text", "")
                    text_chunks.append(text)
                else:
                    content_type = content.get("type")
                    observation.record_non_text(content_type)
                    text = (
                        f"[{content_type} omitted]"
                        if content_type
                        else "[non-text content omitted]"
                    )
                chunks.append(text)
            elif kind == "tool_call":
                if chunks:
                    chunks.clear()
                if text_chunks:
                    text_chunks.clear()
        return None

    activity.start()
    try:
        result = session.request(
            "session/prompt",
            {"sessionId": session_id, "prompt": [{"type": "text", "text": task}]},
            on_frame=on_frame,
        )
    finally:
        activity.stop()

    streamed = "".join(chunks)
    has_final_text = bool("".join(text_chunks).strip())
    return {
        "text": final_text(streamed, denied, mode) if has_final_text else None,
        "hasFinalText": has_final_text,
        "stopReason": result.get("stopReason", "unknown"),
        "usage": result.get("usage", {}),
        "deniedToolCalls": denied,
        "observation": observation,
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


def missing_final_result(
    session_id: str,
    turn: dict[str, Any],
    observation: TurnObservation,
    recovery_attempted: bool,
) -> dict[str, Any]:
    """Build a safe typed result for a completed turn with no final text."""
    error = {
        "type": "missing_final_message",
        "sessionId": session_id,
        "recovered": False,
        "recoveryAttempted": recovery_attempted,
        **observation.metadata(),
    }
    return {
        "sessionId": session_id,
        "text": "missing_final_message: ACP ended without a final textual message",
        "stopReason": turn["stopReason"],
        "usage": turn["usage"],
        "deniedToolCalls": turn["deniedToolCalls"],
        "recovered": False,
        "error": error,
    }


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------


class Bridge:
    def __init__(
        self,
        command: list[str],
        roles_path: str | Path = DEFAULT_ROLES_PATH,
        turn_timeout: float | None = None,
    ) -> None:
        self.command = command
        self.profiles = load_profiles(roles_path)
        self.tools = {tool: role_tool(profile) for tool, profile in self.profiles.items()}
        self.turn_timeout = turn_timeout
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

    def select_model(self, session: AcpSession, session_id: str, profile: RoleProfile) -> None:
        """Pin the session to one model, then to a reasoning variant of it.

        Order is not cosmetic: an agent's effort values are model-dependent
        (OpenCode offers `high|max` on one model and `none|low|medium|high|
        xhigh|max` on another, and none at all on a third), so the variant can
        only be set once the model is. Both requests raise on an unknown value
        rather than running whatever the agent defaulted to -- a delegation
        that silently ran a different model than the one it was routed to
        would destroy exactly the cost guarantee the routing exists for.
        """
        session.request("session/set_model", {"sessionId": session_id, "modelId": profile.model})
        if profile.effort:
            session.request(
                "session/set_config_option",
                {"sessionId": session_id, "configId": "effort", "value": profile.effort},
            )

    def select_session_mode(
        self, session: AcpSession, session_id: str, profile: RoleProfile
    ) -> None:
        """Put the agent in its own read-only mode for a read-only delegation.

        Only for profiles with a `session_mode`: the ones that
        auto-approve their in-workspace writes instead of asking, where the
        permission policy alone never sees the call. Restoring the session's
        opening mode for a write delegation matters when a read-only session is
        continued by id -- otherwise the follow-up's edits are silently refused.
        """
        target = profile.session_mode
        if target is None:
            return
        # No `mode` option at all means the agent never advertised one on
        # session/new -- there is nothing to select, and for a read-only
        # delegation nothing to enforce with either.
        if profile.mode == "read-only" and session.default_mode is None:
            raise RuntimeError(
                f"this server enforces read-only through the agent's {profile.session_mode!r} "
                "session mode, and the agent advertised no `mode` config option; refusing to "
                "run a read-only delegation unprotected"
            )
        session.request(
            "session/set_config_option",
            {"sessionId": session_id, "configId": "mode", "value": target},
        )

    def require_session_mode(self, session: AcpSession, profile: RoleProfile) -> None:
        """Refuse an unprotected read-only session before selecting its model."""
        if (
            profile.mode == "read-only"
            and profile.session_mode is not None
            and session.default_mode is None
        ):
            session.close()
            raise RuntimeError(
                f"this server enforces read-only through the agent's {profile.session_mode!r} "
                "session mode, and the agent advertised no `mode` config option; refusing to "
                "run a read-only delegation unprotected"
            )

    def session_for_call(
        self, profile: RoleProfile, arguments: dict[str, Any], active_call: ActiveCall
    ) -> tuple[AcpSession, str, str]:
        cwd = arguments.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            raise ValueError("cwd is required")
        if not Path(cwd).is_dir():
            raise ValueError(f"cwd {cwd!r} is not a directory")

        session_id = arguments.get("sessionId")
        raw_session_id: str | None = None
        if session_id:
            if not isinstance(session_id, str):
                raise ValueError("sessionId must be a string returned by this bridge")
            session_tool, separator, raw_session_id = session_id.partition(":")
            if not separator or session_tool not in self.profiles or not raw_session_id:
                raise ValueError("sessionId is not a role-bound session returned by this bridge")
            if session_tool != profile.tool:
                raise ValueError(
                    f"session {session_id} is bound to role {session_tool}, "
                    f"not {profile.tool}"
                )
            with self._lock:
                session = self.sessions.get(session_id)
            if session is not None:
                assert raw_session_id is not None
                active_call.attach(session, raw_session_id)
                return session, session_id, raw_session_id

        session, opened_session_id = self.open_session(cwd, active_call, raw_session_id)
        try:
            self.require_session_mode(session, profile)
            self.select_model(session, opened_session_id, profile)
        except Exception:
            session.close()
            raise
        role_session_id = f"{profile.tool}:{opened_session_id}"
        with self._lock:
            self.sessions[role_session_id] = session
        return session, role_session_id, opened_session_id

    def delegate(
        self,
        profile: RoleProfile,
        arguments: dict[str, Any],
        report: Any,
        active_call: ActiveCall,
    ) -> dict[str, Any]:
        unexpected = set(arguments) - {"task", "cwd", "sessionId"}
        if unexpected:
            raise ValueError(
                "caller cannot choose profile fields: " + ", ".join(sorted(unexpected))
            )
        task = arguments["task"]

        session: AcpSession | None = None
        session_id = arguments.get("sessionId")
        try:
            active_call.raise_if_cancelled()
            session, session_id, acp_session_id = self.session_for_call(
                profile, arguments, active_call
            )
            self.select_session_mode(session, acp_session_id, profile)
            active_call.start_prompt()
            timeout_timer: threading.Timer | None = None
            if self.turn_timeout is not None:
                timeout_timer = threading.Timer(
                    self.turn_timeout, active_call.cancel, args=("timeout",)
                )
                timeout_timer.daemon = True
                timeout_timer.start()
            try:
                turn = run_turn(session, acp_session_id, task, profile.mode, report)
                if active_call.cancel_reason() == "timeout":
                    active_call.complete()
                    raise TurnTimeout(
                        f"turn timed out after {self.turn_timeout} seconds; "
                        f"session {session_id} retained"
                    )

                recovered = False
                if turn["stopReason"] == "end_turn" and not turn["hasFinalText"]:
                    if profile.tool == "explore":
                        recovery = run_turn(
                            session,
                            acp_session_id,
                            RECOVERY_PROMPT,
                            profile.mode,
                            report,
                        )
                        if active_call.cancel_reason() == "timeout":
                            active_call.complete()
                            raise TurnTimeout(
                                f"turn timed out after {self.turn_timeout} seconds; "
                                f"session {session_id} retained"
                            )
                        observation = turn["observation"]
                        observation.merge(recovery["observation"])
                        if recovery["hasFinalText"]:
                            turn = recovery
                            turn["observation"] = observation
                            recovered = True
                        else:
                            active_call.complete()
                            return missing_final_result(
                                session_id, recovery, observation, recovery_attempted=True
                            )
                    else:
                        active_call.complete()
                        return missing_final_result(
                            session_id, turn, turn["observation"], recovery_attempted=False
                        )

                if not turn["hasFinalText"]:
                    turn["text"] = final_text("", turn["deniedToolCalls"], profile.mode)
                active_call.complete()
                return {
                    "sessionId": session_id,
                    "text": turn["text"],
                    "stopReason": turn["stopReason"],
                    "usage": turn["usage"],
                    "deniedToolCalls": turn["deniedToolCalls"],
                    "recovered": recovered,
                }
            finally:
                if timeout_timer is not None:
                    timeout_timer.cancel()
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
    with _MCP_WRITE_LOCK:
        sys.stdout.write(json.dumps(frame) + "\n")
        sys.stdout.flush()


def handle_tools_call(
    bridge: Bridge, message: dict[str, Any], active_call: ActiveCall
) -> dict[str, Any]:
    params = message.get("params", {})
    tool_name = params.get("name")
    profile = bridge.profiles.get(tool_name)
    if profile is None:
        raise ValueError(f"unknown tool {tool_name!r}")

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

    result = bridge.delegate(profile, params.get("arguments", {}), report, active_call)
    response = {
        "content": [{"type": "text", "text": result["text"]}],
        "structuredContent": result,
    }
    if "error" in result:
        response["isError"] = True
    return response


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
                        "result": {"tools": [bridge.tools[name] for name in OPENCODE_TOOLS]},
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
    "usage: acp_bridge.py [--roles PATH] [--turn-timeout SECONDS] "
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
            roles_path=options.get("roles", DEFAULT_ROLES_PATH),
            turn_timeout=turn_timeout,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
