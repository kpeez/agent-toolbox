"""Behavioral tests for plugins/swe/workflows/swe-loop.js via the node stub harness."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STUB = ROOT / "tests" / "harness" / "swe_loop_stub.mjs"

LAUNCH_ARGS = {
    "specPath": "/vault/specs/0016-thing.md",
    "slug": "thing",
    "containerId": "container-1",
    "baseBranch": "worktree-thing",
    "scriptsDir": "/plugins/swe/scripts",
}


def run_loop(responses: list[dict[str, Any]], tmp_path: Path) -> dict[str, Any]:
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps({"args": LAUNCH_ARGS, "responses": responses}))
    completed = subprocess.run(
        ["node", str(STUB), str(scenario)],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    return json.loads(completed.stdout)


def call_with_label(run: dict[str, Any], label: str) -> dict[str, Any]:
    matches = [call for call in run["calls"] if call["label"] == label]
    assert matches, (
        f"no agent call labelled {label}; got {[c['label'] for c in run['calls']]}"
    )
    return matches[0]


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
    run = run_loop(
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
        tmp_path,
    )

    note = call_with_label(run, "escalation-note:KP-1")["prompt"]
    assert "Branch: knack/slice/KP-1" in note
    assert "Surviving findings:" in note
    for index, finding in enumerate(findings, start=1):
        assert f"{index}. {finding}" in note
    # The over-200-char finding reaches the note whole, never clipped to a display width.
    assert long_finding in note
    assert note.count("END") == 1

    # The run summary keeps the findings structured, not folded into the reason.
    escalation = run["result"]["escalations"][0]
    assert escalation["issue"] == "KP-1"
    assert escalation["findings"] == findings
    assert "2 finding(s) survived 2 fix rounds" in escalation["reason"]


def test_escalations_without_findings_render_the_bare_headline(tmp_path: Path) -> None:
    issue = {"id": "issue-2", "identifier": "KP-2", "title": "No result"}
    run = run_loop(
        [
            {"match": "^frontier:implement:1$", "result": {"issues": [issue]}},
            {"match": "^frontier:", "result": {"issues": []}},
            {"match": "^escalation-note:KP-2$", "result": "posted"},
            {"match": "^run-summary:", "result": "posted"},
        ],
        tmp_path,
    )

    note = call_with_label(run, "escalation-note:KP-2")["prompt"]
    assert "implementer returned no result" in note
    assert "Surviving findings:" not in note
    assert "Branch:" not in note
    assert run["result"]["escalations"][0]["findings"] == []


def test_slice_review_prompt_requires_a_file_line_anchor(tmp_path: Path) -> None:
    issue = {"id": "issue-3", "identifier": "KP-3", "title": "Anchor"}
    run = run_loop(
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
        tmp_path,
    )

    assert "file:line" in call_with_label(run, "review:KP-3")["prompt"]
