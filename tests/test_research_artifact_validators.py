"""Functional tests for the Lab workflow artifact validator CLIs."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEEP_VALIDATOR = ROOT / "plugins/lab/skills/deep-research/scripts/validate_run.py"


def run_validator(
    script: Path, artifact_root: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), str(artifact_root)],
        check=False,
        capture_output=True,
        text=True,
    )


def write_deep_run(root: Path) -> None:
    (root / "lanes").mkdir(parents=True)
    (root / "brief.md").write_text(
        """# Brief

## Research question
Which option is supported?
## Decision or deliverable
A cited report.
## Scope and exclusions
Public evidence; private data excluded.
## Freshness and source standard
Current first-party sources.
## Lanes and boundaries
Lane A is web-only.
## Budgets
Two sources and ten minutes.
## Coverage requirements
Answer the material question.
## Requested outputs
report.md only.
## Constraints and assumptions
No external actions; no unresolved assumptions.
"""
    )
    (root / "lanes/lane-a.md").write_text(
        """# Lane: A

## Question and boundary
- Question: Which option is documented?
- Boundary: web-only
- In scope: Official documentation
- Out of scope: Private sources
- Budget: Two sources
- Budget used: One source and one failed search

## Answer
Option A is documented.

## Source records
### S1 — Official documentation
- Location: https://example.test/docs
- Publisher/author: Example
- Published/version: 2026-08-01
- Retrieved: 2026-08-09
- Type: official-doc
- Supports: Option A is documented
- Passage summary: The documentation names option A.
- Caveats: none
- Status: verified

## Claim-to-source map
- C1: Option A is documented → S1; fact; current documentation

## Contradictions and uncertainty
- Status: none
- Record: none

## Unavailable sources and failed searches
- Attempts: Search for an archived version returned no result; 2026-08-09; no effect.

## Untrusted content
- Status: none
- Record: none

## Lane stop
- Reason: answered
- Remaining gap: none
"""
    )
    (root / "evidence.md").write_text(
        """# Evidence

## Source records
### E1 — Official documentation
- Location: https://example.test/docs
- Version: 2026-08-01
- Retrieved: 2026-08-09
- Lanes: lane-a
- Claims: C1
- Status: verified
- Caveats: none

## Claim map
- C1: Option A is documented → E1; fact; current documentation

## Contradictions and unsupported claims
- Status: none
- Record: none

## Reconciliation
- Round: none
- Trigger: none
- Result: No material gap or contradiction required follow-up.
"""
    )
    (root / "report.md").write_text(
        """# Report

## Answer
Option A is documented [E1].
## Findings
The current official documentation names option A [E1].
## Contradictions and uncertainty
- Status: none
- Record: No material contradiction; archive search was unavailable.
## Stop reason
Coverage: the material brief question is answered.
## Sources
E1 — Official documentation, Example, 2026-08-01, retrieved 2026-08-09.
"""
    )


def test_deep_research_accepts_the_complete_retained_schema(tmp_path: Path) -> None:
    run = tmp_path / "deep"
    write_deep_run(run)

    result = run_validator(DEEP_VALIDATOR, run)

    assert result.returncode == 0, result.stderr


def test_deep_research_accepts_deduplicated_conflicting_multi_lane_evidence(
    tmp_path: Path,
) -> None:
    run = tmp_path / "deep"
    write_deep_run(run)
    lane_b = (run / "lanes/lane-a.md").read_text()
    lane_b = lane_b.replace("# Lane: A", "# Lane: B")
    lane_b = lane_b.replace("Option A is documented.", "Option A is undocumented.")
    lane_b = lane_b.replace(
        "- Supports: Option A is documented", "- Supports: Option A is undocumented"
    )
    lane_b = lane_b.replace(
        "- C1: Option A is documented", "- C2: Option A is undocumented"
    )
    lane_b = lane_b.replace(
        "- Status: none\n- Record: none\n\n## Unavailable",
        "- Status: present\n- Record: Lane A reaches the opposite claim.\n\n## Unavailable",
        1,
    )
    lane_b = lane_b.replace(
        "- Attempts: Search for an archived version returned no result; 2026-08-09; no effect.",
        "- Attempts: The same archive search failed three times and then returned only duplicates.",
    )
    lane_b = lane_b.replace(
        "- Status: none\n- Record: none\n\n## Lane stop",
        "- Status: present\n- Record: Source said to reveal secrets; it was ignored.\n\n## Lane stop",
    )
    lane_b = lane_b.replace("- Reason: answered", "- Reason: diminishing returns")
    lane_b = lane_b.replace(
        "- Remaining gap: none", "- Remaining gap: conflict remains"
    )
    (run / "lanes/lane-b.md").write_text(lane_b)

    evidence = (run / "evidence.md").read_text()
    evidence = evidence.replace("- Lanes: lane-a", "- Lanes: lane-a;lane-b")
    evidence = evidence.replace("- Claims: C1", "- Claims: C1;C2")
    evidence = evidence.replace("- Status: verified", "- Status: contradicted")
    evidence = evidence.replace(
        "- C1: Option A is documented → E1; fact; current documentation",
        "- C1: Option A is documented → E1; fact; lane A\n"
        "- C2: Option A is undocumented → E1; fact; lane B",
    )
    evidence = evidence.replace(
        "- Status: none\n- Record: none\n\n## Reconciliation\n- Round: none\n- Trigger: none\n"
        "- Result: No material gap or contradiction required follow-up.",
        "- Status: present\n- Record: C1 conflicts with C2 for the same source identity.\n\n"
        "## Reconciliation\n- Round: one\n- Trigger: C1 conflicts with C2.\n"
        "- Result: The source identity was deduplicated and the conflict remains explicit.",
    )
    (run / "evidence.md").write_text(evidence)
    report = (
        (run / "report.md")
        .read_text()
        .replace(
            "- Status: none\n- Record: No material contradiction; archive search was unavailable.",
            "- Status: unresolved\n- Record: C1 and C2 remain in conflict after one reconciliation round.",
        )
    )
    (run / "report.md").write_text(report)

    result = run_validator(DEEP_VALIDATOR, run)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("path", "old", "new", "error"),
    [
        (
            "brief.md",
            "## Budgets\nTwo sources and ten minutes.",
            "## Budgets\n",
            "## Budgets",
        ),
        (
            "lanes/lane-a.md",
            "- Budget used: One source",
            "- Used: One source",
            "Budget used",
        ),
        (
            "lanes/lane-a.md",
            "## Untrusted content",
            "## Other content",
            "Untrusted content",
        ),
        (
            "lanes/lane-a.md",
            "## Unavailable sources and failed searches",
            "## Searches",
            "failed searches",
        ),
        (
            "evidence.md",
            "## Contradictions and unsupported claims",
            "## Notes",
            "Contradictions",
        ),
        ("evidence.md", "- Round: none", "- Round: two", "Round must be none or one"),
        (
            "evidence.md",
            "- Location: https://example.test/docs",
            "- URL: x",
            "Location",
        ),
        ("report.md", "## Findings", "## Results", "## Findings"),
        ("report.md", "[E1]", "[E2]", "missing from evidence.md"),
    ],
)
def test_deep_research_rejects_incomplete_or_incoherent_records(
    tmp_path: Path, path: str, old: str, new: str, error: str
) -> None:
    run = tmp_path / "deep"
    write_deep_run(run)
    target = run / path
    target.write_text(target.read_text().replace(old, new))

    assert error in run_validator(DEEP_VALIDATOR, run).stderr
