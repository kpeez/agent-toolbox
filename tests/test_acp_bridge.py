"""The ACP bridge: permission policy, and the protocol path end to end.

The policy tests matter most. Copilot has no OS-level sandbox, so `mode` is
only meaningful because this bridge answers the agent's permission requests --
if the policy leaks, "read-only delegation" is a lie told to the caller.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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


def test_write_allows_an_edit_inside_the_workspace(tmp_path: Path) -> None:
    target = tmp_path / "src" / "main.py"
    target.parent.mkdir()

    assert allowed(outcome("write", "edit", str(tmp_path), paths=[str(target)]))


def test_write_rejects_an_edit_outside_the_workspace(tmp_path: Path) -> None:
    outside = tmp_path.parent / "elsewhere.txt"

    assert not allowed(outcome("write", "edit", str(tmp_path / "repo"), paths=[str(outside)]))


def test_write_rejects_when_any_location_escapes(tmp_path: Path) -> None:
    """One bad path in a batch poisons the whole call; it is one approval."""
    workspace = tmp_path / "repo"
    workspace.mkdir()
    paths = [str(workspace / "ok.py"), str(tmp_path / "escape.py")]

    assert not allowed(outcome("write", "edit", str(workspace), paths=paths))


def test_write_rejects_an_edit_through_a_symlink_out_of_the_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (tmp_path / "secrets").mkdir()
    (workspace / "link").symlink_to(tmp_path / "secrets")

    result = outcome("write", "edit", str(workspace), paths=[str(workspace / "link" / "k.env")])

    assert not allowed(result)


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
    text = acp_bridge.final_text("", ["edit: Create file"], "read-only")

    assert "edit: Create file" in text
    assert "read-only" in text


def test_the_agents_own_answer_is_returned_untouched() -> None:
    assert acp_bridge.final_text("  6  ", [], "read-only") == "6"


# ---------------------------------------------------------------------------
# protocol path, over a real subprocess speaking ACP
# ---------------------------------------------------------------------------


class BridgeClient:
    """Drives acp_bridge.py over stdio the way Claude Code drives an MCP server."""

    def __init__(self, cwd: Path) -> None:
        self.process = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "plugins" / "swe" / "mcp" / "acp_bridge.py"),
                sys.executable,
                str(FAKE_AGENT),
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

    def call(self, method: str, params: dict) -> dict:
        self._next_id += 1
        request_id = self._next_id
        assert self.process.stdin is not None
        self.process.stdin.write(
            json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            + "\n"
        )
        self.process.stdin.flush()
        assert self.process.stdout is not None
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError(f"bridge exited while waiting for {method}")
            frame = json.loads(line)
            if frame.get("method") == "notifications/progress":
                self.progress.append(frame["params"]["message"])
                continue
            if frame.get("id") == request_id:
                return frame

    def delegate(self, **arguments) -> dict:
        meta = {"_meta": {"progressToken": "p1"}}
        response = self.call(
            "tools/call", {"name": "delegate", "arguments": arguments, **meta}
        )
        return response["result"]

    def close(self) -> None:
        self.process.terminate()
        self.process.wait(timeout=10)


@pytest.fixture
def bridge(tmp_path: Path):
    client = BridgeClient(tmp_path)
    yield client
    client.close()


def directive(**payload) -> str:
    return json.dumps(payload)


def test_the_bridge_advertises_only_the_delegate_tool(bridge: BridgeClient) -> None:
    listed = bridge.call("tools/list", {})["result"]["tools"]

    assert [tool["name"] for tool in listed] == ["delegate"]
    assert listed[0]["inputSchema"]["required"] == ["task", "mode"]


def test_a_delegation_returns_the_agents_answer_and_its_session(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    result = bridge.delegate(
        task=directive(reply="the answer is 6"), mode="read-only", cwd=str(tmp_path)
    )

    assert result["content"][0]["text"] == "the answer is 6"
    assert result["structuredContent"]["sessionId"] == "fake-session-1"
    assert result["structuredContent"]["stopReason"] == "end_turn"


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


def test_tool_calls_are_reported_as_progress(bridge: BridgeClient, tmp_path: Path) -> None:
    """Progress is what keeps a long delegation off the stdio idle timeout."""
    bridge.delegate(
        task=directive(attempts=[{"kind": "read", "title": "Reading files"}], reply="ok"),
        mode="read-only",
        cwd=str(tmp_path),
    )

    assert "Reading files" in bridge.progress


def test_a_session_can_be_continued_by_id(bridge: BridgeClient, tmp_path: Path) -> None:
    first = bridge.delegate(task=directive(reply="one"), mode="read-only", cwd=str(tmp_path))
    session_id = first["structuredContent"]["sessionId"]

    second = bridge.delegate(
        task=directive(reply="two"), mode="read-only", sessionId=session_id
    )

    assert second["structuredContent"]["sessionId"] == session_id
    assert second["content"][0]["text"] == "two"


def test_an_unknown_session_is_an_error_the_caller_can_see(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    result = bridge.delegate(
        task=directive(reply="hi"), mode="read-only", sessionId="never-opened"
    )

    assert result["isError"] is True
    assert "never-opened" in result["content"][0]["text"]


def test_an_unknown_mode_is_rejected_before_the_agent_runs(
    bridge: BridgeClient, tmp_path: Path
) -> None:
    result = bridge.delegate(task=directive(reply="hi"), mode="yolo", cwd=str(tmp_path))

    assert result["isError"] is True
    assert "yolo" in result["content"][0]["text"]
