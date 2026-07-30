"""Behavior of the swe-loop conductor, driven through the node stub harness."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUB = ROOT / "tests" / "harness" / "swe_loop_stub.mjs"
WORKFLOW = ROOT / "plugins" / "swe" / "workflows" / "swe-loop.js"

SCRIPTS_DIR = "/opt/plugins/swe/scripts"
CONTAINER_ID = "CID"
LAUNCH_ARGS = {
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
FRONTIER_FAILS = [{"label": "frontier:", "result": {"issues": [], "error": "boom"}}]

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


def run_loop(tmp_path: Path, args: dict, results: list[dict]) -> dict:
    scenario = tmp_path / "scenario.json"
    scenario.write_text(
        json.dumps({"workflowPath": str(WORKFLOW), "args": args, "results": results})
    )
    completed = subprocess.run(
        ["node", str(STUB), str(scenario)],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def frontier_prompt(transcript: dict) -> str:
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
        run_loop(tmp_path, {**LAUNCH_ARGS, "frontierCmd": command}, FRONTIER_FAILS)
    )
    without_cmd = frontier_prompt(run_loop(tmp_path, LAUNCH_ARGS, FRONTIER_FAILS))

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
        {**LAUNCH_ARGS, "frontierCmd": "sh -c 'echo []'"},
        FRONTIER_FAILS,
    )

    assert "sh -c 'echo []'" in frontier_prompt(transcript)


def test_non_string_frontier_cmd_is_rejected_at_launch(tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match="non-string frontierCmd"):
        run_loop(tmp_path, {**LAUNCH_ARGS, "frontierCmd": ["a", "b"]}, FRONTIER_FAILS)
