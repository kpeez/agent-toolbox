"""Behavior tests for plugins/swe/workflows/swe-loop.js, via the node stub harness.

Each test scripts the agent results the conductor would receive and asserts on
what it did with them: which calls it made, how long it waited, and what the run
summary says.
"""

from __future__ import annotations

import json
import shutil
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

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is required")

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


def labels(result: dict[str, Any]) -> list[str]:
    return [call["label"] for call in result["calls"]]


def workable_calls(result: dict[str, Any]) -> list[str]:
    return [
        call["label"]
        for call in result["calls"]
        if call["label"].startswith("workable:")
    ]


def workable_escalation(result: dict[str, Any]) -> str:
    escalations = [
        e for e in result["summary"]["escalations"] if e["title"] == "workable query"
    ]
    assert len(escalations) == 1, result["summary"]["escalations"]
    return escalations[0]["reason"]


# ---- the launcher slices; the conductor starts at the workable query ---------


def test_the_run_starts_at_the_workable_query_with_no_slicer_agent(
    tmp_path: Path,
) -> None:
    """Slicing belongs to /start-loop: in every observed run the slices were on
    the tracker before launch, so the conductor's first act is the workable
    query — a slicer agent here would re-do the launcher's work."""
    result = run_loop(tmp_path, [{"match": "^workable:", "result": {"issues": []}}])

    called = labels(result)
    assert called[0].startswith("workable:")
    assert [label for label in called if label.startswith("slice:")] == []


# ---- workable-query retry and error reporting -------------------------------------


def test_workable_null_result_retries_with_backoff_then_escalates(
    tmp_path: Path,
) -> None:
    result = run_loop(tmp_path, [{"match": "^workable:", "result": None}])

    assert len(workable_calls(result)) == 3
    assert result["sleeps"] == [30000, 120000]
    assert "after 3 attempts" in workable_escalation(result)
    assert result["summary"]["slicesCompleted"] == []


def test_workable_null_result_recovers_on_a_retry(tmp_path: Path) -> None:
    """Two dead agent calls do not kill the run: the third answers and the loop proceeds."""
    result = run_loop(
        tmp_path,
        [
            {"match": "^workable:", "result": None, "times": 2},
            {"match": "^workable:", "result": {"issues": []}},
        ],
    )

    assert len(workable_calls(result)) == 3
    assert result["sleeps"] == [30000, 120000]
    assert [
        e for e in result["summary"]["escalations"] if e["title"] == "workable query"
    ] == []
    assert any("drained" in line for line in result["logs"])


def test_workable_error_result_escalates_without_retry(tmp_path: Path) -> None:
    """A result carrying `error` is the tracker's own answer — deterministic, not transient."""
    result = run_loop(
        tmp_path,
        [
            {
                "match": "^workable:",
                "result": {"issues": [], "error": "GraphQL response missing data"},
            }
        ],
    )

    assert len(workable_calls(result)) == 1
    assert result["sleeps"] == []
    assert workable_escalation(result) == "GraphQL response missing data"


def test_workable_error_text_is_verbatim_and_unclipped(tmp_path: Path) -> None:
    long_error = "API Error: 529 Overloaded. " + "the upstream detail continues " * 20
    result = run_loop(
        tmp_path,
        [{"match": "^workable:", "result": {"issues": [], "error": long_error}}],
    )

    assert workable_escalation(result) == long_error
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
        [{"match": "^workable:", "result": {"issues": [], "error": error_text}}],
    )

    reason = workable_escalation(result)
    assert reason.startswith(error_text)
    assert "auth failure" in reason


@pytest.mark.parametrize("error_text", NON_AUTH_ERRORS)
def test_no_auth_hint_for_non_auth_errors(tmp_path: Path, error_text: str) -> None:
    result = run_loop(
        tmp_path,
        [{"match": "^workable:", "result": {"issues": [], "error": error_text}}],
    )

    assert workable_escalation(result) == error_text


# ---- escalation comments carry the findings ---------------------------------


def test_exhausted_fix_rounds_carry_findings_verbatim_into_the_run_summary(
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
        "tests/test_swe_loop_behavior.py:1 — no test drives the review through every fix round",
    ]
    issue = {"id": "issue-1", "identifier": "KP-1", "title": "Carry findings"}
    result = run_loop(
        tmp_path,
        [
            {"match": "^workable:implement:1$", "result": {"issues": [issue]}},
            {"match": "^workable:", "result": {"issues": []}},
            {
                "match": "^implement:KP-1$",
                "result": {
                    "status": "DONE",
                    "branch": "slice/KP-1",
                    "summary": "landed",
                },
            },
            {
                "match": "^settle:",
                "result": {
                    "results": [
                        {
                            "identifier": "KP-1",
                            "merged": True,
                            "stateUpdated": True,
                            "detail": "merged",
                        }
                    ]
                },
            },
            {"match": "^fix:", "result": "applied"},
            {
                "match": "^(review|re-review):",
                "result": {"verdict": "findings", "findings": findings},
            },
            # No file-findings response: the re-entry cannot file, so the
            # findings fall through to the escalation this test pins.
            {"match": "^ship:", "result": {"prUrl": "https://example.test/pr/1"}},
            {"match": "^run-summary:", "result": "posted"},
        ],
        default_result=None,
    )

    # Two fix rounds ran, then the findings survived.
    assert [label for label in labels(result) if label.startswith("fix:")] == [
        "fix:1",
        "fix:2",
    ]
    escalation = result["summary"]["escalations"][-1]
    assert escalation["issue"] is None
    assert escalation["findings"] == findings
    assert "2 finding(s) survived 2 fix rounds" in escalation["reason"]

    # The run summary is the durable tracker record, so the over-200-char
    # finding must reach it whole rather than clipped to a display width.
    summary_prompt = call_with_label(result, "run-summary:stub-run")["prompt"]
    assert long_finding in summary_prompt
    assert summary_prompt.count("END") == 1


def test_escalations_without_findings_render_the_bare_headline(tmp_path: Path) -> None:
    issue = {"id": "issue-2", "identifier": "KP-2", "title": "No result"}
    result = run_loop(
        tmp_path,
        [
            {"match": "^workable:implement:1$", "result": {"issues": [issue]}},
            {"match": "^workable:", "result": {"issues": []}},
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


def test_review_prompt_requires_a_file_line_anchor(tmp_path: Path) -> None:
    issue = {"id": "issue-3", "identifier": "KP-3", "title": "Anchor"}
    result = run_loop(
        tmp_path,
        [
            {"match": "^workable:implement:1$", "result": {"issues": [issue]}},
            {"match": "^workable:", "result": {"issues": []}},
            {
                "match": "^implement:KP-3$",
                "result": {
                    "status": "DONE",
                    "branch": "slice/KP-3",
                    "summary": "landed",
                },
            },
            {
                "match": "^settle:",
                "result": {
                    "results": [
                        {
                            "identifier": "KP-3",
                            "merged": True,
                            "stateUpdated": True,
                            "detail": "merged",
                        }
                    ]
                },
            },
            {"match": "^review:assembled$", "result": {"verdict": "pass"}},
            {"match": "^ship:", "result": {"prUrl": "https://example.test/pr/1"}},
            {"match": "^run-summary:", "result": "posted"},
        ],
        default_result=None,
    )

    assert "file:line" in call_with_label(result, "review:assembled")["prompt"]


def test_one_settle_agent_merges_and_marks_the_whole_round(tmp_path: Path) -> None:
    issues = [
        {"id": f"issue-{n}", "identifier": f"KP-{n}", "title": f"slice {n}"}
        for n in (1, 2, 3)
    ]
    result = run_loop(
        tmp_path,
        [
            {"match": "^workable:implement:1$", "result": {"issues": issues}},
            {"match": "^workable:", "result": {"issues": []}},
            *[
                {
                    "match": f"^implement:KP-{n}$",
                    "result": {
                        "status": "DONE",
                        "branch": f"slice/KP-{n}",
                        "summary": f"KP-{n} landed",
                    },
                }
                for n in (1, 2, 3)
            ],
            {
                "match": "^settle:",
                "result": {
                    "results": [
                        {
                            "identifier": f"KP-{n}",
                            "merged": True,
                            "stateUpdated": True,
                            "detail": "merged",
                        }
                        for n in (1, 2, 3)
                    ]
                },
            },
            {"match": "^review:assembled$", "result": {"verdict": "pass"}},
            {"match": "^ship:", "result": {"prUrl": "https://example.test/pr/1"}},
            {"match": "^run-summary:", "result": "posted"},
        ],
        default_result=None,
    )

    called = labels(result)
    # Three slices settle through exactly one agent, not one merge plus one
    # marker agent each: that fan-out was 7M cache reads of deterministic work.
    assert [label for label in called if label.startswith("settle:")] == [
        "settle:implement:1"
    ]
    assert [label for label in called if label.startswith(("merge:", "mark:"))] == []
    assert result["summary"]["slicesCompleted"] == ["KP-1", "KP-2", "KP-3"]

    prompt = call_with_label(result, "settle:implement:1")["prompt"]
    for n in (1, 2, 3):
        assert f"KP-{n} on slice/KP-{n}" in prompt


def test_an_unmerged_slice_escalates_while_the_round_continues(
    tmp_path: Path,
) -> None:
    issues = [
        {"id": "issue-1", "identifier": "KP-1", "title": "conflicts"},
        {"id": "issue-2", "identifier": "KP-2", "title": "clean"},
    ]
    result = run_loop(
        tmp_path,
        [
            {"match": "^workable:implement:1$", "result": {"issues": issues}},
            {"match": "^workable:", "result": {"issues": []}},
            *[
                {
                    "match": f"^implement:KP-{n}$",
                    "result": {
                        "status": "DONE",
                        "branch": f"slice/KP-{n}",
                        "summary": "landed",
                    },
                }
                for n in (1, 2)
            ],
            {
                "match": "^settle:",
                "result": {
                    "results": [
                        {
                            "identifier": "KP-1",
                            "merged": False,
                            "stateUpdated": False,
                            "detail": "conflict in datasets.py could not be resolved",
                        },
                        {
                            "identifier": "KP-2",
                            "merged": True,
                            "stateUpdated": True,
                            "detail": "merged",
                        },
                    ]
                },
            },
            {"match": "^escalation-note:KP-1$", "result": "posted"},
            {"match": "^review:assembled$", "result": {"verdict": "pass"}},
            {"match": "^ship:", "result": {"prUrl": "https://example.test/pr/1"}},
            {"match": "^run-summary:", "result": "posted"},
        ],
        default_result=None,
    )

    assert result["summary"]["slicesCompleted"] == ["KP-2"]
    escalation = result["summary"]["escalations"][0]
    assert escalation["issue"] == "KP-1"
    assert "conflict in datasets.py" in escalation["reason"]


def test_a_failed_state_write_is_logged_not_escalated(
    tmp_path: Path,
) -> None:
    """git decides what is merged, so a tracker state write that fails costs
    visibility, not correctness. This used to escalate, back when a missing
    marker really could make a resumed run repeat the slice."""
    issue = {"id": "issue-1", "identifier": "KP-1", "title": "merged but unsynced"}
    result = run_loop(
        tmp_path,
        [
            {"match": "^workable:implement:1$", "result": {"issues": [issue]}},
            {"match": "^workable:", "result": {"issues": []}},
            {
                "match": "^implement:KP-1$",
                "result": {
                    "status": "DONE",
                    "branch": "slice/KP-1",
                    "summary": "landed",
                },
            },
            {
                "match": "^settle:",
                "result": {
                    "results": [
                        {
                            "identifier": "KP-1",
                            "merged": True,
                            "stateUpdated": False,
                            "detail": "merged; state write rejected",
                        }
                    ]
                },
            },
            {"match": "^review:assembled$", "result": {"verdict": "pass"}},
            {"match": "^ship:", "result": {"prUrl": "https://example.test/pr/1"}},
            {"match": "^run-summary:", "result": "posted"},
        ],
        default_result=None,
    )

    assert result["summary"]["slicesCompleted"] == ["KP-1"]
    assert result["summary"]["escalations"] == []
    assert any("tracker under-reports this slice" in line for line in result["logs"])


# ---- did-not-complete slice reviews -----------------------------------------


SLICE = {"id": "issue-1", "identifier": "KP-1", "title": "one slice"}


def one_slice(*responses: dict[str, Any]) -> list[dict[str, Any]]:
    """A run whose first workable round yields KP-1 and then drains.

    Test-specific responses come first so they win over the happy-path
    fallbacks that answer whatever the test did not script.
    """
    return [
        {"match": "^workable:implement:1$", "result": {"issues": [SLICE]}},
        *responses,
        {"match": "^workable:", "result": {"issues": []}},
        {
            "match": "^implement:KP-1$",
            "result": {
                "status": "DONE",
                "branch": "slice/KP-1",
                "summary": "KP-1 implemented",
            },
        },
        {
            "match": "^settle:",
            "result": {
                "results": [
                    {
                        "identifier": "KP-1",
                        "merged": True,
                        "stateUpdated": True,
                        "detail": "merged",
                    }
                ]
            },
        },
        {"match": "^(review|re-review):", "result": {"verdict": "pass"}},
        {"match": "^ship:", "result": {"prUrl": "https://example.test/pr/1"}},
    ]


def run_one_slice(tmp_path: Path, *responses: dict[str, Any]) -> dict[str, Any]:
    return run_loop(tmp_path, one_slice(*responses))


def test_did_not_complete_review_consumes_no_fix_round(tmp_path: Path) -> None:
    run = run_one_slice(
        tmp_path,
        {
            "match": "^review:assembled$",
            "result": {"verdict": "did-not-complete", "detail": "codex run timed out"},
        },
        {"match": "^review:assembled:retry$", "result": {"verdict": "pass"}},
    )

    called = labels(run)
    assert called.count("review:assembled") == 1
    assert called.count("review:assembled:retry") == 1
    # The dead review never reached a fixer, and no fix round was spent.
    assert [label for label in called if label.startswith("fix:")] == []
    assert run["summary"]["slicesCompleted"] == ["KP-1"]
    assert run["summary"]["escalations"] == []


def test_second_did_not_complete_escalates_without_findings(tmp_path: Path) -> None:
    run = run_one_slice(
        tmp_path,
        {
            "match": "^review:assembled$",
            "result": {"verdict": "did-not-complete", "detail": "codex run timed out"},
        },
        {
            "match": "^review:assembled:retry$",
            "result": {"verdict": "did-not-complete", "detail": "timed out again"},
        },
    )

    called = labels(run)
    assert called.count("review:assembled:retry") == 1
    assert [label for label in called if label.startswith("fix:")] == []
    escalations = run["summary"]["escalations"]
    assert [entry["title"] for entry in escalations] == ["assembled review"]
    reason = escalations[0]["reason"]
    assert "never completed" in reason
    assert "worktree-stub is unreviewed" in reason
    assert "no findings recorded" in reason
    assert "no fix round consumed" in reason
    assert escalations[0]["findings"] == []
    # The slices themselves merged before review, so they are not lost by an
    # unreviewable branch — the branch is flagged unreviewed instead.
    assert run["summary"]["slicesCompleted"] == ["KP-1"]


def test_did_not_complete_re_review_does_not_increment_the_fix_round(
    tmp_path: Path,
) -> None:
    run = run_one_slice(
        tmp_path,
        {
            "match": "^review:assembled$",
            "result": {"verdict": "findings", "findings": ["a.js:12 — guard the null"]},
        },
        {
            "match": "^re-review:1$",
            "result": {"verdict": "did-not-complete", "detail": "reviewer tool failed"},
        },
        {"match": "^re-review:1:retry$", "result": {"verdict": "pass"}},
    )

    called = labels(run)
    # One fixer ran, its re-review's non-completion cost nothing, and the second
    # fix round was never needed or spent.
    assert [label for label in called if label.startswith("fix:")] == ["fix:1"]
    assert "re-review:2" not in called
    assert run["summary"]["escalations"] == []


def test_second_did_not_complete_re_review_escalates_with_no_findings(
    tmp_path: Path,
) -> None:
    run = run_one_slice(
        tmp_path,
        {
            "match": "^review:assembled$",
            "result": {"verdict": "findings", "findings": ["a.js:12 — guard the null"]},
        },
        {
            "match": "^re-review:1$",
            "result": {"verdict": "did-not-complete", "detail": "reviewer tool failed"},
        },
        {"match": "^re-review:1:retry$", "result": None},
    )

    called = labels(run)
    assert [label for label in called if label.startswith("fix:")] == ["fix:1"]
    reason = run["summary"]["escalations"][0]["reason"]
    assert "re-review after fix round 1 never completed" in reason
    assert "the retry returned no verdict" in reason


def test_null_first_review_still_escalates_immediately(tmp_path: Path) -> None:
    run = run_one_slice(tmp_path, {"match": "^review:assembled$", "result": None})

    assert "review:assembled:retry" not in labels(run)
    assert (
        run["summary"]["escalations"][0]["reason"]
        == "assembled review returned no verdict"
    )


def test_the_run_reviews_the_assembled_work_once_not_per_slice(
    tmp_path: Path,
) -> None:
    issues = [
        {"id": f"issue-{n}", "identifier": f"KP-{n}", "title": f"slice {n}"}
        for n in (1, 2)
    ]
    result = run_loop(
        tmp_path,
        [
            {"match": "^workable:implement:1$", "result": {"issues": issues}},
            {"match": "^workable:", "result": {"issues": []}},
            *[
                {
                    "match": f"^implement:KP-{n}$",
                    "result": {
                        "status": "DONE",
                        "branch": f"slice/KP-{n}",
                        "summary": "landed",
                    },
                }
                for n in (1, 2)
            ],
            {
                "match": "^settle:",
                "result": {
                    "results": [
                        {
                            "identifier": f"KP-{n}",
                            "merged": True,
                            "stateUpdated": True,
                            "detail": "merged",
                        }
                        for n in (1, 2)
                    ]
                },
            },
            {"match": "^review:assembled$", "result": {"verdict": "pass"}},
            {"match": "^ship:", "result": {"prUrl": "https://example.test/pr/1"}},
            {"match": "^run-summary:", "result": "posted"},
        ],
        default_result=None,
    )

    # Two slices, one review: the same lines are never read by a per-slice
    # reviewer and then again by a lens panel.
    review_calls = [
        label for label in labels(result) if label.startswith(("review:", "re-review:"))
    ]
    assert review_calls == ["review:assembled"]
    assert [label for label in labels(result) if label.startswith("spec-review")] == []


# ---- workableCmd launch arg -------------------------------------------------


SCRIPTS_DIR = "/opt/plugins/swe/scripts"
CONTAINER_ID = "CID"
WORKABLE_CMD_ARGS = {
    "specPath": "docs/agents/specs/0016-x.md",
    "slug": "x",
    "containerId": CONTAINER_ID,
    "baseBranch": "integration",
    "scriptsDir": SCRIPTS_DIR,
}
# A workable-query failure stops the loop after one round, which is all these tests
# need: the prompt the conductor emitted before asking.
WORKABLE_FAILS = [{"match": "^workable:", "result": {"issues": [], "error": "boom"}}]

# The reference-driven workable prompt, verbatim. Pinned here so a change to the
# workableCmd path that also perturbs the no-workableCmd path is loud: in-flight
# runs launched without the argument must keep getting exactly this text.
REFERENCE_WORKABLE_PROMPT = """Report this run's workable slices as JSON.

Tracker: resolve this repo's tracker per the to-issues skill — an "Issue tracker:" line in the repo's AGENTS.md/CLAUDE.md wins, else the skill's selection ladder — then follow the matching reference in /opt/plugins/swe/skills/to-issues/references/ for every tracker operation.

1. Compute the workable set of container CID per the
   reference's "swe-loop workable set" section — issues with no ready-for-human
   label that are not done and whose every blocker IS done, each as
   {id, identifier, title}. Scripts the reference names live in /opt/plugins/swe/scripts.
   If the query FAILS (auth, network, missing credential, non-zero script
   exit), put the failure text in the "error" field and return an empty issues
   list -- an empty list with no error means the run is finished, so never
   report a failure that way.
2. Run `git branch --merged integration` and read every branch it lists
   named slice/<identifier>. Those slices are merged into this run's
   integration branch, which is what "done in this run" means — their tracker
   state does not advance until the run's PR lands, so never judge it from the
   tracker alone.
3. An issue counts as DONE when its tracker state is closed OR its identifier
   appears in that merged list. Drop a done issue, and treat a done blocker as
   satisfied rather than as still blocking. Skipping the second half is what
   makes a dependency chain stall after its first slice.
4. Return the surviving issues."""


def workable_prompt(transcript: dict[str, Any]) -> str:
    return next(
        call["prompt"]
        for call in transcript["calls"]
        if call["label"].startswith("workable:")
    )


def test_workable_cmd_appears_verbatim_and_absence_keeps_reference_prompt(
    tmp_path: Path,
) -> None:
    command = (
        f"uv run {SCRIPTS_DIR}/linear_tracker.py workable --container {CONTAINER_ID}"
    )

    with_cmd = workable_prompt(
        run_loop(
            tmp_path,
            WORKABLE_FAILS,
            args={**WORKABLE_CMD_ARGS, "workableCmd": command},
        )
    )
    without_cmd = workable_prompt(
        run_loop(tmp_path, WORKABLE_FAILS, args=WORKABLE_CMD_ARGS)
    )

    # Verbatim, on its own line, and the agent is forbidden to improvise.
    assert f"\n    {command}\n" in with_cmd
    assert "construct no other query" in with_cmd
    assert "improvised tracker calls" in with_cmd
    # The command applies the marker rules itself, so the agent returns its
    # output rather than re-reading every issue's comments — one Bash call a
    # round instead of a comment query per issue.
    assert "Do not read\ntracker comments" in with_cmd
    assert "return them unchanged" in with_cmd

    assert without_cmd == REFERENCE_WORKABLE_PROMPT
    assert command not in without_cmd


def test_both_workable_paths_unblock_dependents_of_a_finished_slice(
    tmp_path: Path,
) -> None:
    """A merged slice's tracker state does not advance until the run's PR lands,
    so a workable query that reads blockers by state alone strands every dependent
    slice — the stall that cost both observed runs a manual relaunch."""
    without_cmd = workable_prompt(
        run_loop(tmp_path, WORKABLE_FAILS, args=WORKABLE_CMD_ARGS)
    )
    assert "treat a done blocker as\n   satisfied" in without_cmd
    assert "stall after its first slice" in without_cmd

    with_cmd = workable_prompt(
        run_loop(
            tmp_path,
            WORKABLE_FAILS,
            args={
                **WORKABLE_CMD_ARGS,
                "workableCmd": "linear_tracker.py workable --container CID",
            },
        )
    )
    assert "unblocked their dependents" in with_cmd


def test_workable_cmd_is_opaque_data_not_a_tracker_name(tmp_path: Path) -> None:
    transcript = run_loop(
        tmp_path,
        WORKABLE_FAILS,
        args={**WORKABLE_CMD_ARGS, "workableCmd": "sh -c 'echo []'"},
    )

    assert "sh -c 'echo []'" in workable_prompt(transcript)


def test_non_string_workable_cmd_is_rejected_at_launch(tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match="non-string workableCmd"):
        run_loop(
            tmp_path,
            WORKABLE_FAILS,
            args={**WORKABLE_CMD_ARGS, "workableCmd": ["a", "b"]},
        )
