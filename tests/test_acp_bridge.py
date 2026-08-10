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
                *(agent_command or [sys.executable, str(FAKE_AGENT), *(agent_args or [])]),
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
                continue
            response_id = frame.get("id")
            if response_id == request_id:
                return frame
            if isinstance(response_id, int):
                self._responses[response_id] = frame

    def call(self, method: str, params: dict) -> dict:
        request_id = self.start_call(method, params)
        return self.receive(request_id)

    def start_delegate(self, **arguments) -> int:
        meta = {"_meta": {"progressToken": "p1"}}
        return self.start_call(
            "tools/call", {"name": "delegate", "arguments": arguments, **meta}
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
        send({"jsonrpc": "2.0", "id": message["id"], "result": {"sessionId": session_id}})
    elif method == "session/prompt":
        directive = json.loads(message["params"]["prompt"][0]["text"])
        if directive.get("exit"):
            os._exit(7)
        if directive.get("block"):
            while True:
                time.sleep(1)
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


def wait_for_sessions(tmp_path: Path, count: int) -> list[Path]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        paths = list(tmp_path.glob("lifecycle-*.pid"))
        if len(paths) >= count:
            return paths
        time.sleep(0.01)
    raise AssertionError(f"expected {count} ACP session(s)")


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
# model-dependent `effort` option, and a `mode` option whose second value is
# read-only. Mirrors what `opencode acp` advertises.
OPENCODE_LIKE = [
    "--models", "go/luna,go/flash",
    "--efforts", "low,high,max",
    "--modes", "build,plan",
]


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
        sessionId=pid_path.stem,
    )
    assert "is not open" in continuation["content"][0]["text"]


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
        sessionId=pid_path.stem,
    )
    assert "is not open" in continuation["content"][0]["text"]


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
    blocked_pid_path = next(path for path in pid_paths if path.stem != successful_session_id)
    assert_process_stopped(blocked_pid_path)
    continued = lifecycle_bridge.delegate(
        task=directive(reply="still alive"),
        mode="read-only",
        sessionId=successful_session_id,
    )
    assert continued["content"][0]["text"] == "still alive"


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


# ---------------------------------------------------------------------------
# bridge options: model policy that lives in argv, not in a prompt
# ---------------------------------------------------------------------------


def test_bridge_options_are_split_from_the_agent_command() -> None:
    options, command = acp_bridge.split_argv(
        ["--model", "go/luna", "--effort", "high", "--read-only-mode", "plan", "opencode", "acp"]
    )

    assert options == {"model": "go/luna", "effort": "high", "read_only_mode": "plan"}
    assert command == ["opencode", "acp"]


def test_option_parsing_stops_at_the_agent_command() -> None:
    """An agent flag that looks like a bridge flag belongs to the agent."""
    options, command = acp_bridge.split_argv(["opencode", "acp", "--model", "sneaky"])

    assert options == {}
    assert command == ["opencode", "acp", "--model", "sneaky"]


def test_an_option_without_a_value_is_an_error() -> None:
    with pytest.raises(ValueError, match="--model needs a value"):
        acp_bridge.split_argv(["--model"])


def test_a_pinned_server_does_not_offer_the_model_as_a_choice() -> None:
    """The whole point of pinning: the caller is never asked which model to run."""
    pinned = acp_bridge.delegate_tool("go/luna")

    assert "model" not in pinned["inputSchema"]["properties"]
    assert "effort" not in pinned["inputSchema"]["properties"]
    assert "go/luna" in pinned["description"]
    assert "model" in acp_bridge.delegate_tool(None)["inputSchema"]["properties"]


def test_a_pinned_server_advertises_the_reduced_schema_over_the_wire(bridges) -> None:
    client = bridges(["--model", "go/luna"], OPENCODE_LIKE)

    listed = client.call("tools/list", {})["result"]["tools"]

    assert "model" not in listed[0]["inputSchema"]["properties"]


def test_a_pinned_server_rejects_a_caller_supplied_model(bridges, tmp_path: Path) -> None:
    """Silently honouring it would let a role run on a model it was not routed to."""
    client = bridges(["--model", "go/luna"], OPENCODE_LIKE)

    result = client.delegate(
        task=directive(reply="hi"), mode="read-only", cwd=str(tmp_path), model="go/flash"
    )

    assert result["isError"] is True
    assert "pinned to model go/luna" in result["content"][0]["text"]


def test_the_pinned_model_is_selected_before_its_effort_variant(bridges, tmp_path: Path) -> None:
    """Effort values are model-dependent, so the order is load-bearing, not style."""
    client = bridges(["--model", "go/luna", "--effort", "max"], OPENCODE_LIKE)

    result = client.delegate(
        task=directive(reply="", echo_config=True), mode="write", cwd=str(tmp_path)
    )

    assert result["content"][0]["text"].startswith("config=model=go/luna|effort=max")


def test_an_unavailable_model_surfaces_instead_of_running_the_default(
    bridges, tmp_path: Path
) -> None:
    """Falling through to the agent's default would break the cost routing silently."""
    client = bridges(["--model", "go/not-a-model"], OPENCODE_LIKE)

    result = client.delegate(task=directive(reply="hi"), mode="read-only", cwd=str(tmp_path))

    assert result["isError"] is True
    assert "model not found: go/not-a-model" in result["content"][0]["text"]


def test_an_unavailable_effort_surfaces_too(bridges, tmp_path: Path) -> None:
    client = bridges(["--model", "go/luna", "--effort", "ludicrous"], OPENCODE_LIKE)

    result = client.delegate(task=directive(reply="hi"), mode="read-only", cwd=str(tmp_path))

    assert result["isError"] is True
    assert "effort not found: ludicrous" in result["content"][0]["text"]


def test_a_caller_supplied_model_still_works_on_an_unpinned_server(
    bridges, tmp_path: Path
) -> None:
    """Pinning is opt-in; the generic delegate contract is unchanged without it."""
    client = bridges([], OPENCODE_LIKE)

    result = client.delegate(
        task=directive(reply="", echo_config=True),
        mode="write",
        cwd=str(tmp_path),
        model="go/flash",
        effort="low",
    )

    assert result["content"][0]["text"] == "config=model=go/flash|effort=low"


# ---------------------------------------------------------------------------
# read-only for an agent that does not ask before writing
# ---------------------------------------------------------------------------


def test_read_only_selects_the_agents_own_read_only_session_mode(
    bridges, tmp_path: Path
) -> None:
    """OpenCode auto-approves in-workspace edits, so the kind policy never sees
    them; its own read-only mode is the only thing that actually stops them."""
    client = bridges(["--read-only-mode", "plan"], OPENCODE_LIKE)

    result = client.delegate(
        task=directive(reply="", echo_config=True), mode="read-only", cwd=str(tmp_path)
    )

    assert result["content"][0]["text"] == "config=mode=plan"


def test_write_restores_the_mode_the_session_opened_in(bridges, tmp_path: Path) -> None:
    """A read-only session continued for a write would otherwise stay muzzled."""
    client = bridges(["--read-only-mode", "plan"], OPENCODE_LIKE)

    first = client.delegate(task=directive(reply="one"), mode="read-only", cwd=str(tmp_path))
    result = client.delegate(
        task=directive(reply="", echo_config=True),
        mode="write",
        sessionId=first["structuredContent"]["sessionId"],
    )

    assert result["content"][0]["text"] == "config=mode=plan|mode=build"


def test_read_only_refuses_when_the_agent_has_no_read_only_mode(
    bridges, tmp_path: Path
) -> None:
    """Fail closed: running unprotected is the one outcome worse than erroring."""
    client = bridges(["--read-only-mode", "plan"], [])

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

    assert result["content"][0]["text"] == "config="


def test_the_permission_policy_still_guards_a_read_only_run(bridges, tmp_path: Path) -> None:
    """Both layers, not one: an agent that DOES ask is still refused its edits."""
    client = bridges(["--read-only-mode", "plan"], OPENCODE_LIKE)

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
