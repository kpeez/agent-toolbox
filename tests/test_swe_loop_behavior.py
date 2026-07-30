"""Drive swe-loop.js end to end through the node stub with scripted results."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUB = ROOT / "tests" / "harness" / "swe_loop_stub.mjs"
ARGS = {
    "specPath": "/vault/specs/0016-swe-loop.md",
    "slug": "swe-loop",
    "containerId": "container-1",
    "baseBranch": "worktree-swe-loop",
    "scriptsDir": "/plugins/swe/scripts",
    "issueId": "issue-1",
}
SLICE = {"id": "issue-1", "identifier": "KP-1", "title": "one slice"}

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is required")


def run_loop(responses: dict[str, Any], tmp_path: Path) -> dict[str, Any]:
    script = tmp_path / "script.json"
    script.write_text(json.dumps({"args": ARGS, "responses": responses}))
    completed = subprocess.run(
        ["node", str(STUB), str(script)],
        capture_output=True,
        text=True,
        check=True,
    )
    run = json.loads(completed.stdout)
    assert run["error"] is None, run["error"]
    return run


def labels(run: dict[str, Any]) -> list[str]:
    return [call["label"] for call in run["journal"]]


def one_slice(**responses: Any) -> dict[str, Any]:
    """A run whose first frontier round yields KP-1 and then drains."""
    return {"frontier:implement:1": {"issues": [SLICE]}, **responses}


def test_did_not_complete_review_consumes_no_fix_round(tmp_path: Path) -> None:
    run = run_loop(
        one_slice(
            **{
                "review:KP-1": {
                    "verdict": "did-not-complete",
                    "detail": "codex run timed out",
                },
                "review:KP-1:retry": {"verdict": "pass"},
            }
        ),
        tmp_path,
    )

    called = labels(run)
    assert called.count("review:KP-1") == 1
    assert called.count("review:KP-1:retry") == 1
    # The dead review never reached a fixer, and no fix round was spent.
    assert [label for label in called if label.startswith("fix:")] == []
    assert run["result"]["slicesCompleted"] == ["KP-1"]
    assert run["result"]["escalations"] == []


def test_second_did_not_complete_escalates_without_findings(tmp_path: Path) -> None:
    run = run_loop(
        one_slice(
            **{
                "review:KP-1": {
                    "verdict": "did-not-complete",
                    "detail": "codex run timed out",
                },
                "review:KP-1:retry": {
                    "verdict": "did-not-complete",
                    "detail": "timed out again",
                },
            }
        ),
        tmp_path,
    )

    called = labels(run)
    assert called.count("review:KP-1:retry") == 1
    assert [label for label in called if label.startswith(("fix:", "merge:"))] == []
    escalations = run["result"]["escalations"]
    assert [entry["issue"] for entry in escalations] == ["KP-1"]
    reason = escalations[0]["reason"]
    assert "never completed" in reason
    assert "knack/slice/KP-1" in reason
    assert "no findings recorded" in reason
    assert "no fix round consumed" in reason
    assert run["result"]["slicesCompleted"] == []


def test_did_not_complete_re_review_does_not_increment_the_fix_round(
    tmp_path: Path,
) -> None:
    run = run_loop(
        one_slice(
            **{
                "review:KP-1": {
                    "verdict": "findings",
                    "findings": ["a.js:12 — guard the null"],
                },
                "re-review:KP-1:1": {
                    "verdict": "did-not-complete",
                    "detail": "reviewer tool failed",
                },
                "re-review:KP-1:1:retry": {"verdict": "pass"},
            }
        ),
        tmp_path,
    )

    called = labels(run)
    # One fixer ran, its re-review's non-completion cost nothing, and the second
    # fix round was never needed or spent.
    assert [label for label in called if label.startswith("fix:")] == ["fix:KP-1:1"]
    assert "re-review:KP-1:2" not in called
    assert run["result"]["slicesCompleted"] == ["KP-1"]
    assert run["result"]["escalations"] == []


def test_second_did_not_complete_re_review_escalates_with_no_findings(
    tmp_path: Path,
) -> None:
    run = run_loop(
        one_slice(
            **{
                "review:KP-1": {
                    "verdict": "findings",
                    "findings": ["a.js:12 — guard the null"],
                },
                "re-review:KP-1:1": {
                    "verdict": "did-not-complete",
                    "detail": "reviewer tool failed",
                },
                "re-review:KP-1:1:retry": None,
            }
        ),
        tmp_path,
    )

    called = labels(run)
    assert [label for label in called if label.startswith("fix:")] == ["fix:KP-1:1"]
    reason = run["result"]["escalations"][0]["reason"]
    assert "re-review after fix round 1 never completed" in reason
    assert "the retry returned no verdict" in reason
    assert run["result"]["slicesCompleted"] == []


def test_null_first_review_still_escalates_immediately(tmp_path: Path) -> None:
    run = run_loop(one_slice(**{"review:KP-1": None}), tmp_path)

    assert "review:KP-1:retry" not in labels(run)
    assert (
        run["result"]["escalations"][0]["reason"] == "slice review returned no verdict"
    )


def test_errored_spec_review_lens_is_unreviewed_and_its_findings_discarded(
    tmp_path: Path,
) -> None:
    run = run_loop(
        one_slice(
            **{
                "spec-review:missed": {
                    "error": "review tool crashed",
                    "findings": [
                        {
                            "lens": "missed",
                            "title": "partial",
                            "detail": "junk",
                            "severity": "high",
                        }
                    ],
                }
            }
        ),
        tmp_path,
    )

    called = labels(run)
    assert [label for label in called if label.startswith("file-findings")] == []
    escalations = run["result"]["escalations"]
    assert [entry["title"] for entry in escalations] == ["spec review: missed"]
    assert "unreviewed, not clean" in escalations[0]["reason"]
    assert "review tool crashed" in escalations[0]["reason"]
    assert run["result"]["cutList"] == []
