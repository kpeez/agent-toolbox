"""Behavior tests for plugins/swe/workflows/swe-loop.js, via the node stub harness.

Each test scripts the agent results the conductor would receive and asserts on
what it did with them: which calls it made, how long it waited, and what the run
summary says.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUB = ROOT / "tests" / "harness" / "swe_loop_stub.mjs"
WORKFLOW = ROOT / "plugins" / "swe" / "workflows" / "swe-loop.js"

LAUNCH_ARGS = {
    "specPath": "/tmp/spec.md",
    "slug": "stub-run",
    "containerId": "container-1",
    "baseBranch": "worktree-stub",
    "scriptsDir": "/opt/swe/scripts",
}

# Sentinel meaning "omit defaultResult from the config" (the harness then
# answers unmatched labels with {}). Pass default_result=None to make
# unmatched labels answer null — a dead agent call.
_UNSET = object()


def run_loop(
    tmp_path: Path,
    responses: list[dict[str, Any]],
    args: dict[str, Any] | None = None,
    default_result: Any = _UNSET,
) -> dict[str, Any]:
    config_body: dict[str, Any] = {
        "workflowPath": str(WORKFLOW),
        "args": {**LAUNCH_ARGS, **(args or {})},
        "responses": responses,
    }
    if default_result is not _UNSET:
        config_body["defaultResult"] = default_result
    config = tmp_path / "config.json"
    config.write_text(json.dumps(config_body))
    proc = subprocess.run(
        ["node", str(STUB), str(config)],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    result = json.loads(proc.stdout)
    assert result["error"] is None, result["error"]
    return result


def call_with_label(result: dict[str, Any], label: str) -> dict[str, Any]:
    matches = [call for call in result["calls"] if call["label"] == label]
    assert matches, (
        f"no agent call labelled {label}; got {[c['label'] for c in result['calls']]}"
    )
    return matches[0]


def frontier_calls(result: dict[str, Any]) -> list[str]:
    return [
        call["label"]
        for call in result["calls"]
        if call["label"].startswith("frontier:")
    ]


def frontier_escalation(result: dict[str, Any]) -> str:
    escalations = [
        e for e in result["summary"]["escalations"] if e["title"] == "frontier query"
    ]
    assert len(escalations) == 1, result["summary"]["escalations"]
    return escalations[0]["reason"]


# ---- frontier retry and error reporting -------------------------------------


def test_frontier_null_result_retries_with_backoff_then_escalates(
    tmp_path: Path,
) -> None:
    result = run_loop(tmp_path, [{"match": "^frontier:", "result": None}])

    assert len(frontier_calls(result)) == 3
    assert result["sleeps"] == [30000, 120000]
    assert "after 3 attempts" in frontier_escalation(result)
    assert result["summary"]["slicesCompleted"] == []


def test_frontier_null_result_recovers_on_a_retry(tmp_path: Path) -> None:
    """Two dead agent calls do not kill the run: the third answers and the loop proceeds."""
    result = run_loop(
        tmp_path,
        [
            {"match": "^frontier:", "result": None, "times": 2},
            {"match": "^frontier:", "result": {"issues": []}},
        ],
    )

    assert len(frontier_calls(result)) == 3
    assert result["sleeps"] == [30000, 120000]
    assert [
        e for e in result["summary"]["escalations"] if e["title"] == "frontier query"
    ] == []
    assert any("drained" in line for line in result["logs"])


def test_frontier_error_result_escalates_without_retry(tmp_path: Path) -> None:
    """A result carrying `error` is the tracker's own answer — deterministic, not transient."""
    result = run_loop(
        tmp_path,
        [
            {
                "match": "^frontier:",
                "result": {"issues": [], "error": "GraphQL response missing data"},
            }
        ],
    )

    assert len(frontier_calls(result)) == 1
    assert result["sleeps"] == []
    assert frontier_escalation(result) == "GraphQL response missing data"


def test_frontier_error_text_is_verbatim_and_unclipped(tmp_path: Path) -> None:
    long_error = "API Error: 529 Overloaded. " + "the upstream detail continues " * 20
    result = run_loop(
        tmp_path,
        [{"match": "^frontier:", "result": {"issues": [], "error": long_error}}],
    )

    assert frontier_escalation(result) == long_error
    assert len(long_error) > 200


AUTH_ERRORS = [
    "LINEAR_API_KEY is not set",
    "tracker query failed: HTTP 401 Unauthorized",
    "HTTP 403",
    "missing credential for the tracker CLI",
    "login required",
]
NON_AUTH_ERRORS = [
    "API Error: 529 Overloaded",
    "network timeout after 30s",
    "GraphQL response missing data",
    "prompt exceeded the max tokens for this model",
]


@pytest.mark.parametrize("error_text", AUTH_ERRORS)
def test_auth_hint_appears_for_auth_signature_errors(
    tmp_path: Path, error_text: str
) -> None:
    result = run_loop(
        tmp_path,
        [{"match": "^frontier:", "result": {"issues": [], "error": error_text}}],
    )

    reason = frontier_escalation(result)
    assert reason.startswith(error_text)
    assert "auth failure" in reason


@pytest.mark.parametrize("error_text", NON_AUTH_ERRORS)
def test_no_auth_hint_for_non_auth_errors(tmp_path: Path, error_text: str) -> None:
    result = run_loop(
        tmp_path,
        [{"match": "^frontier:", "result": {"issues": [], "error": error_text}}],
    )

    assert frontier_escalation(result) == error_text


# ---- escalation comments carry the findings ---------------------------------


def test_exhausted_fix_rounds_comment_carries_findings_and_branch(
    tmp_path: Path,
) -> None:
    # Longer than clip()'s 200-char ceiling, so an accidental clip() around the
    # findings truncates this string and fails the assertions below.
    long_finding = (
        "plugins/swe/workflows/swe-loop.js:462 — the escalation names only the finding "
        "count and drops the detail that makes it actionable. "
        + ("detail " * 40)
        + "END"
    )
    assert len(long_finding) > 200
    findings = [
        long_finding,
        "tests/test_swe_loop_behavior.py:1 — no test drives a slice through every fix round",
    ]
    issue = {"id": "issue-1", "identifier": "KP-1", "title": "Carry findings"}
    result = run_loop(
        tmp_path,
        [
            {"match": "^frontier:implement:1$", "result": {"issues": [issue]}},
            {"match": "^frontier:", "result": {"issues": []}},
            {
                "match": "^implement:KP-1$",
                "result": {
                    "status": "DONE",
                    "branch": "knack/slice/KP-1",
                    "summary": "landed",
                },
            },
            {"match": "^fix:KP-1", "result": "applied"},
            {
                "match": "review:KP-1",
                "result": {"verdict": "findings", "findings": findings},
            },
            {"match": "^escalation-note:KP-1$", "result": "posted"},
            {"match": "^run-summary:", "result": "posted"},
        ],
        default_result=None,
    )

    note = call_with_label(result, "escalation-note:KP-1")["prompt"]
    assert "Branch: knack/slice/KP-1" in note
    assert "Surviving findings:" in note
    for index, finding in enumerate(findings, start=1):
        assert f"{index}. {finding}" in note
    # The over-200-char finding reaches the note whole, never clipped to a display width.
    assert long_finding in note
    assert note.count("END") == 1

    # The run summary keeps the findings structured, not folded into the reason.
    escalation = result["summary"]["escalations"][0]
    assert escalation["issue"] == "KP-1"
    assert escalation["findings"] == findings
    assert "2 finding(s) survived 2 fix rounds" in escalation["reason"]


def test_escalations_without_findings_render_the_bare_headline(tmp_path: Path) -> None:
    issue = {"id": "issue-2", "identifier": "KP-2", "title": "No result"}
    result = run_loop(
        tmp_path,
        [
            {"match": "^frontier:implement:1$", "result": {"issues": [issue]}},
            {"match": "^frontier:", "result": {"issues": []}},
            {"match": "^escalation-note:KP-2$", "result": "posted"},
            {"match": "^run-summary:", "result": "posted"},
        ],
        default_result=None,
    )

    note = call_with_label(result, "escalation-note:KP-2")["prompt"]
    assert "implementer returned no result" in note
    assert "Surviving findings:" not in note
    assert "Branch:" not in note
    assert result["summary"]["escalations"][0]["findings"] == []


def test_slice_review_prompt_requires_a_file_line_anchor(tmp_path: Path) -> None:
    issue = {"id": "issue-3", "identifier": "KP-3", "title": "Anchor"}
    result = run_loop(
        tmp_path,
        [
            {"match": "^frontier:implement:1$", "result": {"issues": [issue]}},
            {"match": "^frontier:", "result": {"issues": []}},
            {
                "match": "^implement:KP-3$",
                "result": {
                    "status": "DONE",
                    "branch": "knack/slice/KP-3",
                    "summary": "landed",
                },
            },
            {"match": "^review:KP-3$", "result": {"verdict": "pass"}},
            {"match": "^merge:KP-3$", "result": {"merged": True, "detail": "merged"}},
            {"match": "^mark:KP-3$", "result": "posted"},
            {"match": "^spec-review:", "result": {"findings": []}},
            {"match": "^ship:", "result": {"prUrl": "https://example.test/pr/1"}},
            {"match": "^run-summary:", "result": "posted"},
        ],
        default_result=None,
    )

    assert "file:line" in call_with_label(result, "review:KP-3")["prompt"]


# ---- frontierCmd launch arg -------------------------------------------------


SCRIPTS_DIR = "/opt/plugins/swe/scripts"
CONTAINER_ID = "CID"
FRONTIER_CMD_ARGS = {
    "specPath": "docs/agents/specs/0016-x.md",
    "slug": "x",
    "containerId": CONTAINER_ID,
    "baseBranch": "integration",
    "scriptsDir": SCRIPTS_DIR,
    # Resume: the slice phase is skipped, so the frontier call is the first one.
    "issueId": "ISSUE-1",
}
# A frontier failure stops the loop after one round, which is all these tests
# need: the prompt the conductor emitted before asking.
FRONTIER_FAILS = [{"match": "^frontier:", "result": {"issues": [], "error": "boom"}}]

# The reference-driven frontier prompt, verbatim. Pinned here so a change to the
# frontierCmd path that also perturbs the no-frontierCmd path is loud: in-flight
# runs launched without the argument must keep getting exactly this text.
REFERENCE_FRONTIER_PROMPT = """Report this run's workable slices as JSON.

Tracker: resolve this repo's tracker per the to-issues skill — an "Issue tracker:" line in the repo's AGENTS.md/CLAUDE.md wins, else the skill's selection ladder — then follow the matching reference in /opt/plugins/swe/skills/to-issues/references/ for every tracker operation.

1. Compute the workable frontier of container CID per the
   reference's "swe-loop frontier" section — open issues with no open blocker
   and no ready-for-human label, each as {id, identifier, title}. Scripts the
   reference names live in /opt/plugins/swe/scripts. If the query FAILS (auth, network,
   missing credential, non-zero script exit), put the failure text in the
   "error" field and return an empty issues list -- an empty list with no
   error means the run is finished, so never report a failure that way.
2. For each returned issue read its tracker comments per the reference.
3. DROP every issue whose comments contain the literal marker
   <!-- knack:slice-complete --> — that slice is already implemented on a branch in
   this run even though its tracker state has not advanced yet.
4. Return the surviving issues."""


def frontier_prompt(transcript: dict[str, Any]) -> str:
    return next(
        call["prompt"]
        for call in transcript["calls"]
        if call["label"].startswith("frontier:")
    )


def test_frontier_cmd_appears_verbatim_and_absence_keeps_reference_prompt(
    tmp_path: Path,
) -> None:
    command = f"uv run {SCRIPTS_DIR}/frontier.py --project {CONTAINER_ID}"

    with_cmd = frontier_prompt(
        run_loop(
            tmp_path,
            FRONTIER_FAILS,
            args={**FRONTIER_CMD_ARGS, "frontierCmd": command},
        )
    )
    without_cmd = frontier_prompt(
        run_loop(tmp_path, FRONTIER_FAILS, args=FRONTIER_CMD_ARGS)
    )

    # Verbatim, on its own line, and the agent is forbidden to improvise.
    assert f"\n       {command}\n" in with_cmd
    assert "construct no other query" in with_cmd
    assert "improvised tracker calls" in with_cmd
    # Steps 2-4 still follow the tracker reference either way.
    for step in ("2. For each returned issue", "3. DROP every issue", "4. Return the"):
        assert step in with_cmd

    assert without_cmd == REFERENCE_FRONTIER_PROMPT
    assert command not in without_cmd


def test_frontier_cmd_is_opaque_data_not_a_tracker_name(tmp_path: Path) -> None:
    transcript = run_loop(
        tmp_path,
        FRONTIER_FAILS,
        args={**FRONTIER_CMD_ARGS, "frontierCmd": "sh -c 'echo []'"},
    )

    assert "sh -c 'echo []'" in frontier_prompt(transcript)


def test_non_string_frontier_cmd_is_rejected_at_launch(tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match="non-string frontierCmd"):
        run_loop(
            tmp_path,
            FRONTIER_FAILS,
            args={**FRONTIER_CMD_ARGS, "frontierCmd": ["a", "b"]},
        )
