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


def run_loop(
    tmp_path: Path,
    responses: list[dict[str, Any]],
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "workflowPath": str(WORKFLOW),
                "args": {**LAUNCH_ARGS, **(args or {})},
                "responses": responses,
            }
        )
    )
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
