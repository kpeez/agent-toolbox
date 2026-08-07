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


AUTH_ERRORS = ["tracker query failed: HTTP 401 Unauthorized"]
NON_AUTH_ERRORS = ["API Error: 529 Overloaded"]


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
                    "branch": "batch/KP-1",
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
            {"match": "^ship:", "result": {"prUrls": ["https://example.test/pr/1"]}},
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
                        "branch": f"batch/KP-{n}",
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
                            "stackBranch": branch,
                        }
                        # Three unbatched slices are three batches of one, so
                        # each lands on its own stack branch.
                        for n, branch in ((1, "worktree-stub"), (2, "stack/2"), (3, "stack/3"))
                    ]
                },
            },
            {"match": "^review:assembled$", "result": {"verdict": "pass"}},
            {"match": "^ship:", "result": {"prUrls": ["https://example.test/pr/1"]}},
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
        assert f"batch/KP-{n} → stack branch" in prompt


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
                        "branch": f"batch/KP-{n}",
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
            {"match": "^ship:", "result": {"prUrls": ["https://example.test/pr/1"]}},
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
                    "branch": "batch/KP-1",
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
            {"match": "^ship:", "result": {"prUrls": ["https://example.test/pr/1"]}},
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
                "branch": "batch/KP-1",
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
        {"match": "^ship:", "result": {"prUrls": ["https://example.test/pr/1"]}},
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
                        "branch": f"batch/KP-{n}",
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
            {"match": "^ship:", "result": {"prUrls": ["https://example.test/pr/1"]}},
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
    # Verbatim, on its own line, and the agent is forbidden to improvise.
    assert f"\n    {command}\n" in with_cmd
    assert "construct no other query" in with_cmd
    assert "improvised tracker calls" in with_cmd
    # The command applies the marker rules itself, so the agent returns its
    # output rather than re-reading every issue's comments — one Bash call a
    # round instead of a comment query per issue.
    assert "Do not read\ntracker comments" in with_cmd
    assert "return them unchanged" in with_cmd


# ---- dependency stack become a stacked pull request -------------------------
# A round's workable set is an antichain, and the next round is unblocked by it,
# so consecutive rounds are exactly the layers of a stack. These tests pin that
# mapping: which branch each round settles into, what implementers branch from,
# and that a one-round run is indistinguishable from the pre-stack behavior.


def run_waves(
    tmp_path: Path,
    rounds: int,
    *,
    first_workable: dict[str, Any] | None = None,
    stack: list[str] | None = None,
) -> dict[str, Any]:
    """Script `rounds` rounds of one slice each, every slice merging cleanly."""
    landed = stack or ["worktree-stub", *[f"stack/{n}" for n in range(2, rounds + 1)]]
    responses: list[dict[str, Any]] = []
    for r in range(1, rounds + 1):
        issue = {"id": f"issue-{r}", "identifier": f"KP-{r}", "title": f"slice {r}"}
        payload = {"issues": [issue]}
        if r == 1 and first_workable:
            payload = {**payload, **first_workable}
        responses.append(
            {"match": f"^workable:implement:{r}$", "result": payload},
        )
    responses.append({"match": "^workable:", "result": {"issues": []}})
    for r in range(1, rounds + 1):
        responses.append(
            {
                "match": f"^implement:KP-{r}$",
                "result": {
                    "status": "DONE",
                    "branch": f"batch/KP-{r}",
                    "summary": f"KP-{r} landed",
                },
            }
        )
        responses.append(
            {
                "match": f"^settle:implement:{r}$",
                "result": {
                    "results": [
                        {
                            "identifier": f"KP-{r}",
                            "merged": True,
                            "stateUpdated": True,
                            "detail": "merged",
                            "stackBranch": landed[r - 1],
                        }
                    ]
                },
            }
        )
    responses += [
        {"match": "^review:assembled$", "result": {"verdict": "pass"}},
        {"match": "^ship:", "result": {"prUrls": ["https://example.test/pr/1"]}},
        {"match": "^run-summary:", "result": "posted"},
    ]
    return run_loop(tmp_path, responses, default_result=None)


def test_a_single_wave_run_settles_and_ships_exactly_as_before(
    tmp_path: Path,
) -> None:
    result = run_waves(tmp_path, 1)

    settle = call_with_label(result, "settle:implement:1")["prompt"]
    assert "stack branch worktree-stub" in settle
    assert "created from" not in settle
    # One batch is not a stack: the run must not reach for gh stack at all.
    ship = call_with_label(result, "ship:stub-run")["prompt"]
    assert "gh stack link" not in ship
    assert "Ship the finished work on worktree-stub." in ship


def test_a_later_round_settles_into_a_wave_stacked_on_the_one_below(
    tmp_path: Path,
) -> None:
    result = run_waves(tmp_path, 3)

    second = call_with_label(result, "settle:implement:2")["prompt"]
    # Cutting the batch from the batch below is what makes it contain every layer
    # underneath, which the PR base chaining depends on.
    assert "stack branch stack/2, created from worktree-stub" in second
    third = call_with_label(result, "settle:implement:3")["prompt"]
    assert "stack branch stack/3, created from stack/2" in third


def test_implementers_branch_from_the_current_wave_tip(tmp_path: Path) -> None:
    result = run_waves(tmp_path, 3)

    assert "from worktree-stub" in call_with_label(result, "implement:KP-1")["prompt"]
    assert "from worktree-stub" in call_with_label(result, "implement:KP-2")["prompt"]
    # Round 3 branches off the batch round 2 opened, not off the integration
    # branch: a slice cut from below its dependencies rebuilds work it needs.
    assert "from stack/2" in call_with_label(result, "implement:KP-3")["prompt"]


def test_review_and_ship_target_the_top_of_the_stack(tmp_path: Path) -> None:
    result = run_waves(tmp_path, 2)

    assert "stack/2" in call_with_label(result, "review:assembled")["prompt"]
    ship = call_with_label(result, "ship:stub-run")["prompt"]
    assert "STACK MODE" in ship
    # The conductor names the stack and their order; the host-specific commands
    # stay in ship-pr, which is what keeps this file tracker- and forge-agnostic.
    assert "1. worktree-stub\n2. stack/2" in ship
    assert result["summary"]["prUrls"] == ["https://example.test/pr/1"]


def test_waves_left_by_an_earlier_session_are_adopted_before_settling(
    tmp_path: Path,
) -> None:
    # A cold resume (no resumeFromRunId) has no memory of the layers a previous
    # session opened; git is the only record. Settling into batch 1 on top of an
    # existing stack/3 would bury three layers of published work.
    result = run_waves(tmp_path, 1, first_workable={"topStackBranch": "stack/3"}, stack=["stack/4"])

    settle = call_with_label(result, "settle:implement:1")["prompt"]
    assert "stack branch stack/4, created from stack/3" in settle
    ship = call_with_label(result, "ship:stub-run")["prompt"]
    assert "1. worktree-stub\n2. stack/2\n3. stack/3\n4. stack/4" in ship


# ---- batching: one implementer per story, not per issue -------------------
# Spawning a subagent costs its whole context load, a worktree and a merge
# before it edits a line. A sweep that files 41 findings across 7 milestones
# must cost 7 implementers, not 41 -- and the milestone is also the boundary a
# reviewer reads, so the same batching sets the pull requests.

B1 = "B1 Tracking correctness"
B2 = "B2 Output durability & schema"


def batched_issues() -> list[dict[str, Any]]:
    grouped = [(432, B1), (439, B1), (433, B2), (438, B2), (445, B2)]
    return [
        {"id": f"issue-{n}", "identifier": f"KP-{n}", "title": f"finding {n}", "batch": g}
        for n, g in grouped
    ]


def run_batched(
    tmp_path: Path, issues: list[dict[str, Any]], settle: list[dict[str, Any]]
) -> dict[str, Any]:
    return run_loop(
        tmp_path,
        [
            {"match": "^workable:implement:1$", "result": {"issues": issues}},
            {"match": "^workable:", "result": {"issues": []}},
            {
                "match": "^implement:",
                "result": {"status": "DONE", "branch": "", "summary": "landed"},
            },
            {"match": "^settle:", "result": {"results": settle}},
            {"match": "^review:assembled$", "result": {"verdict": "pass"}},
            {"match": "^ship:", "result": {"prUrls": ["https://example.test/pr/1"]}},
            {"match": "^run-summary:", "result": "posted"},
        ],
        default_result=None,
    )


def settled(*pairs: tuple[int, str]) -> list[dict[str, Any]]:
    return [
        {
            "identifier": f"KP-{n}",
            "merged": True,
            "stateUpdated": True,
            "detail": "merged",
            "stackBranch": branch,
        }
        for n, branch in pairs
    ]


def test_slices_sharing_a_batch_go_to_one_implementer(
    tmp_path: Path,
) -> None:
    result = run_batched(
        tmp_path,
        batched_issues(),
        settled(
            (432, "worktree-stub"),
            (439, "worktree-stub"),
            (433, "stack/2"),
            (438, "stack/2"),
            (445, "stack/2"),
        ),
    )

    # Five findings, two milestones, two implementers.
    implementers = [label for label in labels(result) if label.startswith("implement:")]
    assert implementers == [f"implement:{B1}", f"implement:{B2}"]

    prompt = call_with_label(result, f"implement:{B2}")["prompt"]
    assert "implement 3 related slices" in prompt
    for n in (433, 438, 445):
        assert f"KP-{n}" in prompt
    # All three identifiers stay in the branch name: it is the only trace a
    # resumed run has of what this batch already finished.
    assert "batch/KP-433-KP-438-KP-445-b2-output-durability-schema" in prompt
    assert result["summary"]["slicesCompleted"] == [
        "KP-432",
        "KP-439",
        "KP-433",
        "KP-438",
        "KP-445",
    ]


def test_each_batch_lands_on_its_own_stack_branch_within_one_round(
    tmp_path: Path,
) -> None:
    result = run_batched(
        tmp_path,
        batched_issues(),
        settled(
            (432, "worktree-stub"),
            (439, "worktree-stub"),
            (433, "stack/2"),
            (438, "stack/2"),
            (445, "stack/2"),
        ),
    )

    # Two batches unblocked at the same moment are still two stories, so one
    # round produces two stacked pull requests rather than one mixed diff.
    settle = call_with_label(result, "settle:implement:1")["prompt"]
    assert "stack branch worktree-stub" in settle
    assert "stack branch stack/2, created from worktree-stub" in settle
    ship = call_with_label(result, "ship:stub-run")["prompt"]
    assert "1. worktree-stub\n2. stack/2" in ship


def test_a_large_batch_is_never_split(tmp_path: Path) -> None:
    issues = [
        {
            "id": f"issue-{n}",
            "identifier": f"KP-{n}",
            "title": f"finding {n}",
            "batch": "B6 Data, eval & utils bugs",
        }
        for n in range(1, 11)
    ]
    result = run_batched(
        tmp_path, issues, settled(*[(n, "worktree-stub") for n in range(1, 11)])
    )

    # Ten slices in one batch is a spec that should have been split. Chunking
    # them here would hide that behind two half-named pull requests, so the
    # batch stays whole and the scoping failure stays visible.
    implementers = [label for label in labels(result) if label.startswith("implement:")]
    assert implementers == ["implement:B6 Data, eval & utils bugs"]
    assert "implement 10 related slices" in call_with_label(result, implementers[0])["prompt"]
