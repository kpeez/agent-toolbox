"""The ACP bridge: permission policy, and the protocol path end to end.

The policy tests matter most. An ACP agent has no OS-level sandbox, so `mode`
is only meaningful because this bridge answers the agent's permission requests
-- or, for an agent that does not ask, because the bridge selects that agent's
own read-only session mode. If either leaks, "read-only delegation" is a lie
told to the caller.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "swe" / "mcp"))

import acp_bridge  # noqa: E402

FAKE_AGENT = ROOT / "tests" / "harness" / "fake_acp_agent.py"

STANDARD_OPTIONS = [
    {"optionId": "allow_once", "kind": "allow_once", "name": "Allow once"},
    {"optionId": "allow_always", "kind": "allow_always", "name": "Always"},
    {"optionId": "reject_once", "kind": "reject_once", "name": "Deny"},
]


def tool_call(kind: str, paths: list[str] | None = None) -> dict:
    call: dict = {"toolCallId": "c1", "title": "Some call", "kind": kind}
    if paths is not None:
        call["locations"] = [{"path": path} for path in paths]
    return call


def outcome(mode: str, kind: str, workspace: str, paths: list[str] | None = None) -> dict:
    return acp_bridge.permission_outcome(mode, tool_call(kind, paths), STANDARD_OPTIONS, workspace)


def allowed(result: dict) -> bool:
    return result.get("outcome") == "selected" and "allow" in result.get("optionId", "")


# ---------------------------------------------------------------------------
# permission policy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(acp_bridge.READ_ONLY_KINDS))
def test_read_only_allows_non_mutating_kinds(kind: str, tmp_path: Path) -> None:
    assert allowed(outcome("read-only", kind, str(tmp_path)))


@pytest.mark.parametrize("kind", ["edit", "delete", "move", "execute", "switch_mode"])
def test_read_only_rejects_mutating_kinds(kind: str, tmp_path: Path) -> None:
    result = outcome("read-only", kind, str(tmp_path), paths=[str(tmp_path / "f.txt")])

    assert not allowed(result)
    assert result["optionId"] == "reject_once"


def test_read_only_rejects_an_unknown_kind(tmp_path: Path) -> None:
    """A kind ACP adds later must fail closed, not fall through as harmless."""
    assert not allowed(outcome("read-only", "quantum_teleport", str(tmp_path)))


def test_review_mode_passes_execute_denies_edit(tmp_path: Path) -> None:
    assert allowed(outcome("review", "execute", str(tmp_path)))
    assert not allowed(outcome("review", "edit", str(tmp_path)))


def test_write_allows_an_edit_inside_the_workspace(tmp_path: Path) -> None:
    target = tmp_path / "src" / "main.py"
    target.parent.mkdir()

    assert allowed(outcome("write", "edit", str(tmp_path), paths=[str(target)]))


def test_write_rejects_an_edit_outside_the_workspace(tmp_path: Path) -> None:
    outside = tmp_path.parent / "elsewhere.txt"

    assert not allowed(outcome("write", "edit", str(tmp_path / "repo"), paths=[str(outside)]))


@pytest.mark.parametrize("kind", sorted(acp_bridge.READ_ONLY_KINDS))
def test_write_allows_read_only_kinds_outside_the_workspace(kind: str, tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-read.txt"

    assert allowed(outcome("write", kind, str(tmp_path / "repo"), paths=[str(outside)]))


def test_write_rejects_when_any_location_escapes(tmp_path: Path) -> None:
    """One bad path in a batch poisons the whole call; it is one approval."""
    workspace = tmp_path / "repo"
    workspace.mkdir()
    paths = [str(workspace / "ok.py"), str(tmp_path / "escape.py")]

    assert not allowed(outcome("write", "edit", str(workspace), paths=paths))


def test_write_allows_an_edit_through_a_workspace_internal_symlink(tmp_path: Path) -> None:
    """docs/agents is a repo-planted symlink out of the tree; a write spelled
    inside the workspace is sanctioned even when the link carries it elsewhere,
    or every spec/ADR write in a delegated run comes back denied."""
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (tmp_path / "vault").mkdir()
    (workspace / "docs").symlink_to(tmp_path / "vault")

    result = outcome("write", "edit", str(workspace), paths=[str(workspace / "docs" / "spec.md")])

    assert allowed(result)


def test_write_rejects_the_symlink_targets_own_path(tmp_path: Path) -> None:
    """The sanction covers the workspace spelling only: naming the resolved
    target directly is an escape like any other absolute path outside."""
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (tmp_path / "vault").mkdir()
    (workspace / "docs").symlink_to(tmp_path / "vault")

    result = outcome("write", "edit", str(workspace), paths=[str(tmp_path / "vault" / "spec.md")])

    assert not allowed(result)


def test_write_rejects_a_lexical_dotdot_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    (workspace / "sub").mkdir(parents=True)

    escape = workspace / "sub" / ".." / ".." / "escape.py"
    assert not allowed(outcome("write", "edit", str(workspace), paths=[str(escape)]))


def test_write_allows_a_call_that_names_no_location(tmp_path: Path) -> None:
    """ACP does not describe a shell command's effects; a write run asked for it."""
    assert allowed(outcome("write", "execute", str(tmp_path)))


def test_an_unknown_mode_is_an_error_not_a_default(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown delegation mode"):
        outcome("yolo", "edit", str(tmp_path))


def test_one_shot_options_are_preferred_over_standing_grants(tmp_path: Path) -> None:
    """A standing grant would silently cover later calls this policy never saw."""
    assert outcome("read-only", "read", str(tmp_path))["optionId"] == "allow_once"


def test_cancels_when_no_offered_option_matches_the_verdict(tmp_path: Path) -> None:
    only_allow = [{"optionId": "allow_once", "kind": "allow_once", "name": "Allow"}]

    result = acp_bridge.permission_outcome("read-only", tool_call("edit"), only_allow, str(tmp_path))

    assert result == {"outcome": "cancelled"}


# ---------------------------------------------------------------------------
# empty-answer reporting
# ---------------------------------------------------------------------------


def test_a_blocked_run_reports_the_denials_instead_of_an_empty_answer() -> None:
    text = acp_bridge.final_text("", ["execute: Run tests"], "read-only")

    assert "execute: Run tests" in text
    assert "read-only" in text


def test_read_only_text_reports_execute_denials_only() -> None:
    assert acp_bridge.final_text("answer", ["edit: Create file"], "read-only") == "answer"

    text = acp_bridge.final_text("answer", ["execute: Run tests"], "read-only")
    assert "The bridge denied 1 tool call(s) under mode=read-only" in text


def test_the_agents_own_answer_is_returned_untouched() -> None:
    assert acp_bridge.final_text("  6  ", [], "read-only") == "6"


# ---------------------------------------------------------------------------
# protocol path, over a real subprocess speaking ACP
# ---------------------------------------------------------------------------


class BridgeClient:
    """Drives acp_bridge.py over stdio the way Claude Code drives an MCP server."""

    def __init__(
        self,
        cwd: Path,
        options: list[str] | None = None,
        agent_args: list[str] | None = None,
        agent_command: list[str] | None = None,
    ) -> None:
        self.process = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "plugins" / "swe" / "mcp" / "acp_bridge.py"),
                *(options or []),
                *(
                    agent_command
                    or [
                        sys.executable,
                        str(FAKE_AGENT),
                        *(OPENCODE_LIKE if agent_args is None else agent_args),
                    ]
                ),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=cwd,
        )
        self._next_id = 0
        self.progress: list[str] = []
        self.progress_numbers: list[int] = []
        self._responses: dict[int, dict] = {}

    def start_call(self, method: str, params: dict) -> int:
        self._next_id += 1
        request_id = self._next_id
        assert self.process.stdin is not None
        self.process.stdin.write(
            json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            + "\n"
        )
        self.process.stdin.flush()
        return request_id

    def receive(self, request_id: int) -> dict:
        if response := self._responses.pop(request_id, None):
            return response
        assert self.process.stdout is not None
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError(f"bridge exited while waiting for request {request_id}")
            frame = json.loads(line)
            if frame.get("method") == "notifications/progress":
                self.progress.append(frame["params"]["message"])
                self.progress_numbers.append(frame["params"]["progress"])
                continue
            response_id = frame.get("id")
            if response_id == request_id:
                return frame
            if isinstance(response_id, int):
                self._responses[response_id] = frame

    def call(self, method: str, params: dict) -> dict:
        request_id = self.start_call(method, params)
        return self.receive(request_id)

    def start_delegate(self, tool: str = "explore", **arguments) -> int:
        mode = arguments.pop("mode", None)
        if mode is not None:
            tool = {"read-only": "explore", "write": "implement", "review": "review"}.get(
                mode, tool
            )
        meta = {"_meta": {"progressToken": "p1"}}
        return self.start_call(
            "tools/call", {"name": tool, "arguments": arguments, **meta}
        )

    def cancel(self, request_id: int) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/cancelled",
                    "params": {"requestId": request_id, "reason": "test cancellation"},
                }
            )
            + "\n"
        )
        self.process.stdin.flush()

    def delegate(self, tool: str = "explore", **arguments) -> dict:
        mode = arguments.pop("mode", None)
        if mode is not None:
            tool = {"read-only": "explore", "write": "implement", "review": "review"}.get(
                mode, tool
            )
        response = self.call(
            "tools/call",
            {"name": tool, "arguments": arguments, "_meta": {"progressToken": "p1"}},
        )
        return response["result"]

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=10)

    def shutdown(self) -> None:
        assert self.process.stdin is not None
        self.process.stdin.close()
        self.process.wait(timeout=10)


@pytest.fixture
def bridge(tmp_path: Path):
    client = BridgeClient(tmp_path)
    yield client
    client.close()


@pytest.fixture
def bridges(tmp_path: Path):
    """Bridges configured per test, all torn down together."""
    opened: list[BridgeClient] = []

    def open_bridge(options: list[str], agent_args: list[str]) -> BridgeClient:
        client = BridgeClient(tmp_path, options, agent_args)
        opened.append(client)
        return client

    yield open_bridge
    for client in opened:
        client.close()


LIFECYCLE_AGENT = r"""
import json
import os
import sys
import time

session_id = f"lifecycle-{os.getpid()}"

def send(frame):
    sys.stdout.write(json.dumps(frame) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": message["id"], "result": {"protocolVersion": 1}})
    elif method == "session/new":
        with open(f"{session_id}.pid", "w") as pid_file:
            pid_file.write(str(os.getpid()))
        send({
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {
                "sessionId": session_id,
                "configOptions": [
                    {"id": "mode", "currentValue": "plan"},
                    {"id": "effort", "currentValue": "high"},
                ],
            },
        })
    elif method in ("session/set_model", "session/set_config_option"):
        send({"jsonrpc": "2.0", "id": message["id"], "result": {}})
    elif method == "session/prompt":
        directive = json.loads(message["params"]["prompt"][0]["text"])
        if diagnostic := directive.get("diagnostic"):
            sys.stderr.write(diagnostic + "\n")
        for diagnostic_index in range(directive.get("diagnostic_lines", 0)):
            sys.stderr.write(f"routine-diagnostic-{diagnostic_index:04d}\n")
        sys.stderr.flush()
        with open(f"{session_id}.ready", "w") as ready_file:
            ready_file.write("ready")
        if directive.get("break_reply"):
            os.close(0)
            send({
                "jsonrpc": "2.0",
                "id": 99,
                "method": "session/request_permission",
                "params": {
                    "sessionId": session_id,
                    "toolCall": {
                        "toolCallId": "reply-break",
                        "title": "Read fixture",
                        "kind": "read",
                    },
                    "options": [
                        {"optionId": "allow_once", "kind": "allow_once", "name": "Allow"}
                    ],
                },
            })
            while True:
                time.sleep(1)
        if directive.get("exit"):
            os._exit(7)
        if directive.get("block"):
            while True:
                time.sleep(1)
        if directive.get("cancellable"):
            for line in sys.stdin:
                cancel = json.loads(line)
                if cancel.get("method") != "session/cancel":
                    continue
                partial_reply = directive.get("partial_reply", "")
                if partial_reply:
                    send({
                        "jsonrpc": "2.0",
                        "method": "session/update",
                        "params": {"sessionId": session_id, "update": {
                            "sessionUpdate": "agent_message_chunk",
                            "content": {"type": "text", "text": partial_reply},
                        }},
                    })
                send({
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {"stopReason": "cancelled"},
                })
                break
            continue
        reply = directive.get("reply", "")
        if reply:
            send({
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {"sessionId": session_id, "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": reply},
                }},
            })
        send({"jsonrpc": "2.0", "id": message["id"], "result": {"stopReason": "end_turn"}})
"""


@pytest.fixture
def lifecycle_bridge(tmp_path: Path):
    client = BridgeClient(
        tmp_path,
        agent_command=[sys.executable, "-u", "-c", LIFECYCLE_AGENT],
    )
    yield client
    client.close()


@pytest.fixture
def lifecycle_bridges(tmp_path: Path):
    opened: list[BridgeClient] = []

    def open_bridge(options: list[str]) -> BridgeClient:
        client = BridgeClient(
            tmp_path,
            options=options,
            agent_command=[sys.executable, "-u", "-c", LIFECYCLE_AGENT],
        )
        opened.append(client)
        return client

    yield open_bridge
    for client in opened:
        client.close()


def wait_for_sessions(tmp_path: Path, count: int) -> list[Path]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        paths = list(tmp_path.glob("lifecycle-*.pid"))
        if len(paths) >= count:
            return paths
        time.sleep(0.01)
    raise AssertionError(f"expected {count} ACP session(s)")


def wait_for_ready_session(tmp_path: Path) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if next(tmp_path.glob("lifecycle-*.ready"), None) is not None:
            return
        time.sleep(0.01)
    raise AssertionError("expected the ACP prompt to start")


def assert_process_stopped(pid_path: Path) -> None:
    pid = int(pid_path.read_text())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.01)
    raise AssertionError(f"ACP process {pid} is still running")


# The OpenCode-shaped fixture: a model list it validates against, a
# model-dependent `effort` option, and a `mode` option. Mirrors what
# `opencode acp` advertises.
OPENCODE_LIKE = [
    "--models",
    "opencode-go/deepseek-v4-flash,opencode-go/gpt-5.6-luna,opencode-go/deepseek-v4-pro",
    "--efforts",
    "high,max",
    "--modes",
    "build,plan",
]


def directive(**payload) -> str:
    return json.dumps(payload)


def test_the_bridge_advertises_exactly_the_three_fixed_role_tools(bridge: BridgeClient) -> None:
    listed = bridge.call("tools/list", {})["result"]["tools"]

    assert [tool["name"] for tool in listed] == ["explore", "implement", "review"]
    for tool in listed:
        assert tool["inputSchema"]["required"] == ["task", "cwd"]
        assert set(tool["inputSchema"]["properties"]) == {
            "task",
            "cwd",
            "sessionId",
            "model",
            "effort",
        }


def test_a_delegation_returns_the_agents_answer_and_its_session(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    result = bridge.delegate(
        task=directive(reply="the answer is 6"), mode="read-only", cwd=str(tmp_path)
    )

    assert result["content"][0]["text"] == "the answer is 6"
    assert result["structuredContent"]["sessionId"] == "explore:fake-session-1"
    assert result["structuredContent"]["stopReason"] == "end_turn"


def test_a_delegation_returns_only_the_message_after_tool_activity(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    result = bridge.delegate(
        task=directive(
            preamble=["Let me inspect the workspace first."],
            attempts=[{"kind": "read", "title": "Reading files"}],
            reply="The final answer",
        ),
        mode="read-only",
        cwd=str(tmp_path),
    )

    assert result["content"][0]["text"] == "The final answer"


def test_final_text_survives_a_trailing_tool_call_update(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    result = bridge.delegate(
        task=directive(reply="The final answer", trailing_tool_updates=[{}]),
        mode="read-only",
        cwd=str(tmp_path),
    )

    assert result["content"][0]["text"] == "The final answer"
    assert bridge.progress == ["agent message", "tool call update"]


def test_explorer_recovers_once_in_the_same_session(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    result = bridge.delegate(
        task=directive(
            reply_blocks=[{"type": "image", "uri": "fixture"}],
            recovery={"reply": "recovered final answer"},
        ),
        mode="read-only",
        cwd=str(tmp_path),
    )

    assert result["content"][0]["text"] == "recovered final answer"
    assert result["structuredContent"]["recovered"] is True
    assert result["structuredContent"]["sessionId"] == "explore:fake-session-1"
    assert (tmp_path / "fake-agent.prompt-count").read_text() == "2"


def test_explorer_recovery_exhaustion_is_a_typed_safe_error(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    result = bridge.delegate(
        task=directive(
            attempts=[{"kind": "read", "title": "Initial read"}],
            reply_blocks=[{"type": "image", "uri": "initial"}],
            recovery={
                "attempts": [{"kind": "read", "title": "Recovery read"}],
                "reply_blocks": [{"type": "image", "uri": "recovery"}],
            },
        ),
        mode="read-only",
        cwd=str(tmp_path),
    )

    structured = result["structuredContent"]
    assert result["isError"] is True
    assert structured["error"]["type"] == "missing_final_message"
    assert structured["error"]["recoveryAttempted"] is True
    assert structured["error"]["sessionId"] == "explore:fake-session-1"
    assert structured["error"]["eventCounts"] == {
        "tool_call": 2,
        "permission_request": 2,
        "agent_message_chunk": 2,
    }
    assert structured["error"]["lastActivity"] == "agent_message_chunk"
    assert isinstance(structured["error"]["lastActivityAt"], float)
    assert structured["error"]["nonTextContentTypes"] == {"image": 2}
    assert "missing_final_message" in result["content"][0]["text"]
    assert (tmp_path / "fake-agent.prompt-count").read_text() == "2"


@pytest.mark.parametrize("tool", ["implement", "review"])
def test_non_explorer_roles_never_replay_missing_final_text(
    bridge: BridgeClient, tmp_path: Path, tool: str
) -> None:
    result = bridge.delegate(
        tool=tool,
        task=directive(
            reply_blocks=[{"type": "image", "uri": "fixture"}],
            recovery={"reply": "must not be replayed"},
        ),
        cwd=str(tmp_path),
    )

    structured = result["structuredContent"]
    assert result["isError"] is True
    assert structured["error"]["type"] == "missing_final_message"
    assert structured["error"]["recoveryAttempted"] is False
    assert (tmp_path / "fake-agent.prompt-count").read_text() == "1"


def test_read_only_denies_the_agents_edit_over_the_wire(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    result = bridge.delegate(
        task=directive(
            attempts=[{"kind": "edit", "title": "Create file", "paths": [str(tmp_path / "x")]}],
            echo_granted=True,
        ),
        mode="read-only",
        cwd=str(tmp_path),
    )

    assert result["structuredContent"]["deniedToolCalls"] == ["edit: Create file"]
    assert result["content"][0]["text"] == "granted="


def test_write_mode_grants_the_same_edit(bridge: BridgeClient, tmp_path: Path) -> None:
    result = bridge.delegate(
        task=directive(
            attempts=[{"kind": "edit", "title": "Create file", "paths": [str(tmp_path / "x")]}],
            echo_granted=True,
        ),
        mode="write",
        cwd=str(tmp_path),
    )

    assert result["structuredContent"]["deniedToolCalls"] == []
    assert result["content"][0]["text"] == "granted=edit"


def test_review_mode_passes_execute_denies_edit_over_the_wire(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    result = bridge.delegate(
        task=directive(
            attempts=[
                {"kind": "execute", "title": "Run tests"},
                {"kind": "edit", "title": "Create file", "paths": [str(tmp_path / "x")]},
            ],
            echo_granted=True,
        ),
        mode="review",
        cwd=str(tmp_path),
    )

    assert result["structuredContent"]["deniedToolCalls"] == ["edit: Create file"]
    assert result["content"][0]["text"] == "granted=execute"


def test_write_mode_grants_a_read_outside_the_workspace(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    result = bridge.delegate(
        task=directive(
            attempts=[{"kind": "read", "paths": [str(tmp_path.parent / "outside-read.txt")]}],
            echo_granted=True,
        ),
        mode="write",
        cwd=str(tmp_path),
    )

    assert result["content"][0]["text"] == "granted=read"
    assert result["structuredContent"]["deniedToolCalls"] == []


def test_a_denied_but_chatty_run_carries_the_denial_account(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    result = bridge.delegate(
        task=directive(
            attempts=[
                {
                    "kind": "edit",
                    "title": "Edit outside workspace",
                    "paths": [str(tmp_path.parent / "outside-edit.txt")],
                }
            ],
            reply="planning sentence",
        ),
        mode="write",
        cwd=str(tmp_path),
    )

    text = result["content"][0]["text"]
    assert text.startswith("planning sentence\n\n---\n\n")
    assert "The bridge denied 1 tool call(s) under mode=write" in text
    assert "edit: Edit outside workspace" in text
    assert "outside the workspace" in text
    assert result["structuredContent"]["deniedToolCalls"] == ["edit: Edit outside workspace"]


def test_tool_calls_are_reported_as_progress(bridge: BridgeClient, tmp_path: Path) -> None:
    """Progress is what keeps a long delegation off the stdio idle timeout."""
    bridge.delegate(
        task=directive(attempts=[{"kind": "read", "title": "Reading files"}], reply="ok"),
        mode="read-only",
        cwd=str(tmp_path),
    )

    assert bridge.progress == ["tool call", "permission request", "agent message"]
    assert bridge.progress_numbers == [1, 2, 3]


def test_each_message_chunk_streams_as_activity_progress(bridge: BridgeClient, tmp_path: Path) -> None:
    chunks = ["a" * 75, "b" * 75, "c" * 75, "d" * 75, "e" * 75, "f" * 75]

    result = bridge.delegate(
        task=directive(
            attempts=[{"kind": "read", "title": "Reading files"}],
            reply_chunks=chunks,
        ),
        mode="read-only",
        cwd=str(tmp_path),
    )

    assert bridge.progress == [
        "tool call",
        "permission request",
        "agent message",
        "agent message",
        "agent message",
        "agent message",
        "agent message",
        "agent message",
    ]
    assert bridge.progress_numbers == list(range(1, 9))
    assert result["content"][0]["text"] == "".join(chunks)


def test_a_short_answer_emits_one_message_progress(bridge: BridgeClient, tmp_path: Path) -> None:
    bridge.delegate(
        task=directive(reply="a" * (acp_bridge.MESSAGE_PROGRESS_INTERVAL - 1)),
        mode="read-only",
        cwd=str(tmp_path),
    )

    assert bridge.progress == ["agent message"]


def test_liveness_notice_is_deterministic_and_stops_after_completion() -> None:
    reports: list[str] = []

    class QuietSession:
        cwd = "."
        process = SimpleNamespace(poll=lambda: None)

        def request(self, method, params, on_frame=None):
            time.sleep(0.04)
            return {"stopReason": "end_turn"}

    turn = acp_bridge.run_turn(
        cast(acp_bridge.AcpSession, QuietSession()),
        "quiet-session",
        "task",
        "read-only",
        reports.append,
        liveness_timeout=0.01,
    )

    assert reports == ["liveness: child process is alive; no ACP event arrived for 30 seconds"]
    assert turn["text"] is None
    assert turn["observation"].metadata() == {
        "eventCounts": {},
        "lastActivity": None,
        "lastActivityAt": None,
    }
    time.sleep(0.02)
    assert reports == ["liveness: child process is alive; no ACP event arrived for 30 seconds"]


def test_non_text_content_becomes_a_placeholder(bridge: BridgeClient, tmp_path: Path) -> None:
    result = bridge.delegate(
        task=directive(
            reply_blocks=[
                {"type": "text", "text": "before "},
                {"type": "image", "uri": "data:image/png;base64,fixture"},
                {"type": "text", "text": "after"},
            ]
        ),
        mode="read-only",
        cwd=str(tmp_path),
    )

    assert result["content"][0]["text"] == "before [image omitted]after"


def test_an_image_only_answer_is_a_missing_final_message(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    result = bridge.delegate(
        task=directive(
            reply_blocks=[{"type": "image", "uri": "fixture"}],
            recovery={"reply_blocks": [{"type": "image", "uri": "recovery"}]},
        ),
        mode="read-only",
        cwd=str(tmp_path),
    )

    assert result["isError"] is True
    assert result["structuredContent"]["error"]["type"] == "missing_final_message"
    assert result["structuredContent"]["error"]["nonTextContentTypes"] == {"image": 2}
    assert (tmp_path / "fake-agent.prompt-count").read_text() == "2"


def test_a_session_can_be_continued_by_id(bridge: BridgeClient, tmp_path: Path) -> None:
    first = bridge.delegate(task=directive(reply="one"), mode="read-only", cwd=str(tmp_path))
    session_id = first["structuredContent"]["sessionId"]

    second = bridge.delegate(
        task=directive(reply="two"), mode="read-only", cwd=str(tmp_path), sessionId=session_id
    )

    assert second["structuredContent"]["sessionId"] == session_id
    assert second["content"][0]["text"] == "two"


def test_a_compliant_agent_cancels_gracefully_and_keeps_its_session(
    lifecycle_bridge: BridgeClient, tmp_path: Path
) -> None:
    request_id = lifecycle_bridge.start_delegate(
        task=directive(cancellable=True, partial_reply="partial answer"),
        mode="read-only",
        cwd=str(tmp_path),
    )
    pid_path = wait_for_sessions(tmp_path, 1)[0]
    wait_for_ready_session(tmp_path)

    lifecycle_bridge.cancel(request_id)
    result = lifecycle_bridge.receive(request_id)["result"]

    assert "isError" not in result
    assert result["structuredContent"]["stopReason"] == "cancelled"
    assert result["content"][0]["text"] == "partial answer"
    session_id = result["structuredContent"]["sessionId"]
    assert session_id == f"explore:{pid_path.stem}"
    os.kill(int(pid_path.read_text()), 0)

    continuation = lifecycle_bridge.delegate(
        task=directive(reply="still alive"),
        mode="read-only",
        cwd=str(tmp_path),
        sessionId=session_id,
    )
    assert continuation["content"][0]["text"] == "still alive"


def test_cancelling_a_tool_call_stops_and_forgets_its_acp_session(
    lifecycle_bridge: BridgeClient, tmp_path: Path
) -> None:
    request_id = lifecycle_bridge.start_delegate(
        task=directive(block=True), mode="read-only", cwd=str(tmp_path)
    )
    pid_path = wait_for_sessions(tmp_path, 1)[0]

    lifecycle_bridge.cancel(request_id)
    result = lifecycle_bridge.receive(request_id)["result"]

    assert result["isError"] is True
    assert "cancelled" in result["content"][0]["text"].lower()
    assert_process_stopped(pid_path)
    continuation = lifecycle_bridge.delegate(
        task=directive(reply="must not run"),
        mode="read-only",
        cwd=str(tmp_path),
        sessionId=f"explore:{pid_path.stem}",
    )
    assert "is not open" in continuation["content"][0]["text"]


def test_a_hung_turn_times_out_with_a_named_error(lifecycle_bridges, tmp_path: Path) -> None:
    client = lifecycle_bridges(["--turn-timeout", "0.05"])
    request_id = client.start_delegate(
        task=directive(block=True), mode="read-only", cwd=str(tmp_path)
    )
    pid_path = wait_for_sessions(tmp_path, 1)[0]

    result = client.receive(request_id)["result"]

    error_text = result["content"][0]["text"]
    assert result["isError"] is True
    assert "TurnTimeout" in error_text
    assert "0.05" in error_text
    assert_process_stopped(pid_path)


def test_a_timed_out_compliant_agent_keeps_its_session(lifecycle_bridges, tmp_path: Path) -> None:
    client = lifecycle_bridges(["--turn-timeout", "0.05"])
    request_id = client.start_delegate(
        task=directive(cancellable=True, partial_reply="partial answer"),
        mode="read-only",
        cwd=str(tmp_path),
    )
    pid_path = wait_for_sessions(tmp_path, 1)[0]
    wait_for_ready_session(tmp_path)

    result = client.receive(request_id)["result"]

    error_text = result["content"][0]["text"]
    session_id = f"explore:{pid_path.stem}"
    assert result["isError"] is True
    assert "TurnTimeout" in error_text
    assert "0.05" in error_text
    assert session_id == f"explore:{pid_path.stem}"
    assert session_id in error_text
    continuation = client.delegate(
        task=directive(reply="still alive"),
        mode="read-only",
        cwd=str(tmp_path),
        sessionId=session_id,
    )
    assert continuation["content"][0]["text"] == "still alive"


def test_the_timeout_timer_is_disarmed_when_the_turn_completes(
    lifecycle_bridges, tmp_path: Path
) -> None:
    client = lifecycle_bridges(["--turn-timeout", "0.05"])
    first = client.delegate(
        task=directive(reply="complete"), mode="read-only", cwd=str(tmp_path)
    )
    session_id = first["structuredContent"]["sessionId"]
    time.sleep(0.15)

    continuation = client.delegate(
        task=directive(reply="still alive"),
        mode="read-only",
        cwd=str(tmp_path),
        sessionId=session_id,
    )

    assert continuation["content"][0]["text"] == "still alive"


@pytest.mark.parametrize("value", ["not-a-number", "0", "-1"])
def test_a_bad_turn_timeout_is_a_usage_error(value: str, capsys: pytest.CaptureFixture) -> None:
    assert acp_bridge.main(["--turn-timeout", value]) == 2

    assert "usage:" in capsys.readouterr().err


def test_child_exit_stops_the_wait_and_forgets_the_session(
    lifecycle_bridge: BridgeClient, tmp_path: Path
) -> None:
    request_id = lifecycle_bridge.start_delegate(
        task=directive(exit=True), mode="read-only", cwd=str(tmp_path)
    )
    pid_path = wait_for_sessions(tmp_path, 1)[0]

    result = lifecycle_bridge.receive(request_id)["result"]

    assert result["isError"] is True
    assert "exited before answering session/prompt" in result["content"][0]["text"]
    assert_process_stopped(pid_path)
    continuation = lifecycle_bridge.delegate(
        task=directive(reply="must not run"),
        mode="read-only",
        cwd=str(tmp_path),
        sessionId=f"explore:{pid_path.stem}",
    )
    assert "is not open" in continuation["content"][0]["text"]


def test_unexpected_exit_reports_bounded_raw_stderr_metadata(
    lifecycle_bridge: BridgeClient, tmp_path: Path
) -> None:
    diagnostic = "authentication failed; connection refused; unclassified detail"
    diagnostic_lines = 1000
    expected_bytes = len((diagnostic + "\n").encode()) + sum(
        len(f"routine-diagnostic-{index:04d}\n".encode())
        for index in range(diagnostic_lines)
    )

    result = lifecycle_bridge.delegate(
        task=directive(
            diagnostic=diagnostic, diagnostic_lines=diagnostic_lines, exit=True
        ),
        mode="read-only",
        cwd=str(tmp_path),
    )
    error_text = result["content"][0]["text"]

    assert "exited before answering session/prompt" in error_text
    assert "ACP stderr metadata:" in error_text
    assert f"bytes={expected_bytes}" in error_text
    assert "truncated=true" in error_text
    assert "exitCode=7" in error_text
    assert "categories=" not in error_text
    assert "tail=" in error_text
    assert "routine-diagnostic-0999" in error_text


def test_permission_reply_send_failure_includes_raw_stderr_metadata(
    lifecycle_bridge: BridgeClient, tmp_path: Path
) -> None:
    result = lifecycle_bridge.delegate(
        task=directive(
            diagnostic="network unavailable; token=fixture-value /example/private.txt",
            break_reply=True,
        ),
        mode="read-only",
        cwd=str(tmp_path),
    )
    error_text = result["content"][0]["text"]

    assert "session/prompt failed" in error_text
    assert "ACP stderr metadata:" in error_text
    assert "tail=" in error_text
    assert "network unavailable" in error_text
    assert "categories=" not in error_text


def test_success_does_not_expose_stderr_metadata(
    lifecycle_bridge: BridgeClient, tmp_path: Path
) -> None:
    result = lifecycle_bridge.delegate(
        task=directive(
            diagnostic="authentication failed token=fixture-value /example/private.txt",
            reply="clean answer",
        ),
        mode="read-only",
        cwd=str(tmp_path),
    )

    assert result["content"][0]["text"] == "clean answer"
    assert "stderr" not in json.dumps(result).lower()
    assert "authentication" not in json.dumps(result).lower()


def test_cancellation_does_not_expose_stderr_metadata(
    lifecycle_bridge: BridgeClient, tmp_path: Path
) -> None:
    request_id = lifecycle_bridge.start_delegate(
        task=directive(
            diagnostic="network failed token=fixture-value /example/private.txt",
            block=True,
        ),
        mode="read-only",
        cwd=str(tmp_path),
    )
    wait_for_ready_session(tmp_path)

    lifecycle_bridge.cancel(request_id)
    result = lifecycle_bridge.receive(request_id)["result"]

    assert "cancelled" in result["content"][0]["text"].lower()
    assert "stderr" not in json.dumps(result).lower()
    assert "network" not in json.dumps(result).lower()


def test_cancelling_one_concurrent_call_does_not_corrupt_the_other(
    lifecycle_bridge: BridgeClient, tmp_path: Path
) -> None:
    blocked_id = lifecycle_bridge.start_delegate(
        task=directive(block=True), mode="read-only", cwd=str(tmp_path)
    )
    wait_for_sessions(tmp_path, 1)
    successful_id = lifecycle_bridge.start_delegate(
        task=directive(reply="independent"), mode="read-only", cwd=str(tmp_path)
    )
    pid_paths = wait_for_sessions(tmp_path, 2)

    successful = lifecycle_bridge.receive(successful_id)["result"]
    successful_session_id = successful["structuredContent"]["sessionId"]
    lifecycle_bridge.cancel(blocked_id)
    cancelled = lifecycle_bridge.receive(blocked_id)["result"]

    assert successful["content"][0]["text"] == "independent"
    assert cancelled["isError"] is True
    blocked_pid_path = next(
        path for path in pid_paths if path.stem != successful_session_id.removeprefix("explore:")
    )
    assert_process_stopped(blocked_pid_path)
    continued = lifecycle_bridge.delegate(
        task=directive(reply="still alive"),
        mode="read-only",
        cwd=str(tmp_path),
        sessionId=successful_session_id,
    )
    assert continued["content"][0]["text"] == "still alive"


def test_concurrent_tool_calls_return_complete_json_frames(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    first_id = bridge.start_delegate(
        task=directive(reply="first"), mode="read-only", cwd=str(tmp_path)
    )
    second_id = bridge.start_delegate(
        task=directive(reply="second"), mode="read-only", cwd=str(tmp_path)
    )

    first = bridge.receive(first_id)
    second = bridge.receive(second_id)

    assert first["id"] == first_id
    assert second["id"] == second_id
    assert first["result"]["content"][0]["text"] == "first"
    assert second["result"]["content"][0]["text"] == "second"


def test_server_shutdown_stops_retained_acp_sessions(
    lifecycle_bridge: BridgeClient, tmp_path: Path
) -> None:
    retained = lifecycle_bridge.delegate(
        task=directive(reply="complete"), mode="read-only", cwd=str(tmp_path)
    )
    lifecycle_bridge.start_delegate(
        task=directive(block=True), mode="read-only", cwd=str(tmp_path)
    )
    pid_paths = wait_for_sessions(tmp_path, 2)
    wait_for_ready_session(tmp_path)

    assert retained["content"][0]["text"] == "complete"
    lifecycle_bridge.shutdown()

    for pid_path in pid_paths:
        assert_process_stopped(pid_path)


def test_an_unknown_session_is_loaded_when_the_agent_supports_it(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    result = bridge.delegate(
        task=directive(reply="loaded"),
        mode="read-only",
        cwd=str(tmp_path),
        sessionId="explore:fake-session-1",
    )

    assert result["content"][0]["text"] == "loaded"
    assert "replayed history" not in result["content"][0]["text"]
    assert "replayed history" not in bridge.progress
    session_id = result["structuredContent"]["sessionId"]
    continuation = bridge.delegate(
        task=directive(reply="continued"),
        mode="read-only",
        cwd=str(tmp_path),
        sessionId=session_id,
    )
    assert continuation["content"][0]["text"] == "continued"


def test_load_is_refused_when_the_capability_is_absent(bridges, tmp_path: Path) -> None:
    client = bridges([], ["--no-load-session"])

    result = client.delegate(
        task=directive(reply="must not run"),
        mode="read-only",
        cwd=str(tmp_path),
        sessionId="explore:fake-session-1",
    )

    assert result["isError"] is True
    assert "fake-session-1 is not open on this bridge" in result["content"][0]["text"]


def test_a_failed_load_surfaces_the_agents_error(bridges, tmp_path: Path) -> None:
    client = bridges([], OPENCODE_LIKE)

    result = client.delegate(
        task=directive(reply="must not run"),
        mode="read-only",
        cwd=str(tmp_path),
        sessionId="explore:never-opened",
    )

    assert result["isError"] is True
    assert "session/load failed" in result["content"][0]["text"]
    assert "unknown session: never-opened" in result["content"][0]["text"]
    assert_process_stopped(tmp_path / "fake-agent.pid")


def test_bridge_options_are_split_from_the_agent_command() -> None:
    options, command = acp_bridge.split_argv(
        [
            "--roles",
            "roles.json",
            "opencode",
            "acp",
        ]
    )

    assert options == {"roles": "roles.json"}
    assert command == ["opencode", "acp"]


def test_option_parsing_stops_at_the_agent_command() -> None:
    """An agent flag that looks like a bridge flag belongs to the agent."""
    options, command = acp_bridge.split_argv(["opencode", "acp", "--roles", "sneaky"])

    assert options == {}
    assert command == ["opencode", "acp", "--roles", "sneaky"]


def test_an_option_without_a_value_is_an_error() -> None:
    with pytest.raises(ValueError, match="--roles needs a value"):
        acp_bridge.split_argv(["--roles"])


def test_callers_cannot_supply_policy_fields(bridge: BridgeClient, tmp_path: Path) -> None:
    for field in ("mode", "role"):
        result = bridge.call(
            "tools/call",
            {
                "name": "explore",
                "arguments": {
                    "task": directive(reply="must not run"),
                    "cwd": str(tmp_path),
                    field: "caller-choice",
                },
            },
        )
        result = result["result"]
        assert result["isError"] is True
        assert field in result["content"][0]["text"]


def test_each_fixed_tool_selects_its_internal_profile(bridge: BridgeClient, tmp_path: Path) -> None:
    expected = {
        "explore": "config=model=opencode-go/deepseek-v4-flash|effort=high|mode=plan",
        "implement": "config=model=opencode-go/gpt-5.6-luna|effort=high|mode=build",
        "review": "config=model=opencode-go/deepseek-v4-pro|effort=max",
    }
    for tool, config in expected.items():
        result = bridge.delegate(
            tool=tool, task=directive(reply="", echo_config=True), cwd=str(tmp_path)
        )
        assert result["content"][0]["text"] == config


def test_a_model_override_reaches_the_agent(bridge: BridgeClient, tmp_path: Path) -> None:
    result = bridge.delegate(
        task=directive(reply="", echo_config=True),
        mode="read-only",
        cwd=str(tmp_path),
        model="opencode-go/gpt-5.6-luna",
    )

    assert result["content"][0]["text"] == (
        "config=model=opencode-go/gpt-5.6-luna|effort=high|mode=plan"
    )


def test_an_effort_override_keeps_the_role_default_model(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    """Effort enums are model-dependent, so a model-only override keeps the
    role's default effort and an effort-only override keeps the default model."""
    result = bridge.delegate(
        task=directive(reply="", echo_config=True),
        mode="read-only",
        cwd=str(tmp_path),
        effort="max",
    )

    assert result["content"][0]["text"] == (
        "config=model=opencode-go/deepseek-v4-flash|effort=max|mode=plan"
    )


def test_an_override_repins_a_continued_session(bridge: BridgeClient, tmp_path: Path) -> None:
    """The config log accumulates across a continued session, so the assertion
    reads the trailing selections this turn actually applied."""
    first = bridge.delegate(task=directive(reply="one"), mode="read-only", cwd=str(tmp_path))
    session_id = first["structuredContent"]["sessionId"]

    second = bridge.delegate(
        task=directive(reply="two", echo_config=True),
        mode="read-only",
        cwd=str(tmp_path),
        sessionId=session_id,
        model="opencode-go/gpt-5.6-luna",
        effort="max",
    )

    selections = second["content"][0]["text"].removeprefix("config=").split("|")
    assert selections[-3:] == [
        "model=opencode-go/gpt-5.6-luna",
        "effort=max",
        "mode=plan",
    ]


def test_a_continuation_without_an_override_keeps_its_selection(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    first = bridge.delegate(
        task=directive(reply="one"),
        mode="read-only",
        cwd=str(tmp_path),
        model="opencode-go/gpt-5.6-luna",
    )
    session_id = first["structuredContent"]["sessionId"]

    second = bridge.delegate(
        task=directive(reply="two", echo_config=True),
        mode="read-only",
        cwd=str(tmp_path),
        sessionId=session_id,
    )

    selections = second["content"][0]["text"].split("config=", 1)[1]
    assert selections.startswith("model=opencode-go/gpt-5.6-luna")
    assert "|model=" not in selections


def test_a_non_string_override_is_a_caller_error(bridge: BridgeClient, tmp_path: Path) -> None:
    result = bridge.delegate(
        task=directive(reply="must not run"),
        mode="read-only",
        cwd=str(tmp_path),
        model=123,
    )

    assert result["isError"] is True
    assert "model must be a string" in result["content"][0]["text"]


def test_an_unknown_model_fails_instead_of_rerouting(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    """The fake agent rejects unknown ids the way OpenCode does; the delegation
    must surface that rejection rather than quietly run the role default."""
    result = bridge.delegate(
        task=directive(reply="must not run"),
        mode="read-only",
        cwd=str(tmp_path),
        model="opencode-go/nonexistent",
    )

    assert result["isError"] is True
    assert "model not found" in result["content"][0]["text"]


# ---------------------------------------------------------------------------
# read-only for an agent that does not ask before writing
# ---------------------------------------------------------------------------


def test_read_only_selects_the_agents_own_read_only_session_mode(
    bridges, tmp_path: Path
) -> None:
    """OpenCode auto-approves in-workspace edits, so the kind policy never sees
    them; its own read-only mode is the only thing that actually stops them."""
    client = bridges([], OPENCODE_LIKE)

    result = client.delegate(
        task=directive(reply="", echo_config=True), mode="read-only", cwd=str(tmp_path)
    )

    assert result["content"][0]["text"] == (
        "config=model=opencode-go/deepseek-v4-flash|effort=high|mode=plan"
    )


def test_a_session_cannot_continue_through_a_different_role(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    first = bridge.delegate(task=directive(reply="one"), tool="explore", cwd=str(tmp_path))
    result = bridge.delegate(
        task=directive(reply="must not run"),
        tool="implement",
        cwd=str(tmp_path),
        sessionId=first["structuredContent"]["sessionId"],
    )

    assert result["isError"] is True
    assert "bound to role explore" in result["content"][0]["text"]


def test_read_only_refuses_when_the_agent_has_no_read_only_mode(
    bridges, tmp_path: Path
) -> None:
    """Fail closed: running unprotected is the one outcome worse than erroring."""
    client = bridges([], [])

    result = client.delegate(task=directive(reply="hi"), mode="read-only", cwd=str(tmp_path))

    assert result["isError"] is True
    assert "refusing to run a read-only delegation unprotected" in result["content"][0]["text"]


def test_an_unconfigured_bridge_never_touches_the_session_mode(
    bridges, tmp_path: Path
) -> None:
    """Agents that do ask for permission keep the pre-existing behavior exactly."""
    client = bridges([], OPENCODE_LIKE)

    result = client.delegate(
        task=directive(reply="", echo_config=True), mode="read-only", cwd=str(tmp_path)
    )

    assert result["content"][0]["text"] == (
        "config=model=opencode-go/deepseek-v4-flash|effort=high|mode=plan"
    )


def test_the_permission_policy_still_guards_a_read_only_run(bridges, tmp_path: Path) -> None:
    """Both layers, not one: an agent that DOES ask is still refused its edits."""
    client = bridges([], OPENCODE_LIKE)

    result = client.delegate(
        task=directive(
            attempts=[{"kind": "edit", "title": "Create file", "paths": [str(tmp_path / "x")]}],
            echo_granted=True,
        ),
        mode="read-only",
        cwd=str(tmp_path),
    )

    assert result["structuredContent"]["deniedToolCalls"] == ["edit: Create file"]


def test_a_blocked_write_run_is_not_told_to_retry_in_the_mode_it_used() -> None:
    """Observed live: a write delegation denied for escaping the workspace was
    advised to "re-dispatch with mode='write'", which is what it already did."""
    text = acp_bridge.final_text("", ["other: /outside"], "write")

    assert "mode='write'" not in text
    assert "outside the workspace" in text
