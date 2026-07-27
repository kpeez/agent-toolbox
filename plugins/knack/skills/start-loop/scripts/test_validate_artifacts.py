"""Prove validate_artifacts.py catches the documentation drift it exists for.

Agents in the knack workflow publish specs and issues as free-form markdown.
Nothing stopped a spec's status from jumping draft -> done without ever
passing through review, or an issue from shipping with an empty acceptance
criteria section -- both look fine at a glance and both make the artifact
useless to whoever reads it next. This script is the gate graph nodes run
before publishing; these tests prove it actually blocks those two failure
modes (and their neighbors) rather than rubber-stamping anything that parses.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("validate_artifacts.py")

VALID_SPEC = """---
status: draft
desc: a sample spec
---

# Sample spec

Body text.
"""

APPROVED_ACTIVE_SPEC = """---
status: active
desc: a sample spec
---

# Sample spec

<!-- knack:spec-approved -->

Body text.
"""

VALID_ISSUE = """# Sample issue

## What to build

A thing.

## Acceptance criteria

- [ ] it works
- [x] it is tested

## Scope

In scope: the thing.

## Blocked by

Nothing.
"""


def run_spec(path: Path, *, previous_status: str | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT), "spec", str(path)]
    if previous_status is not None:
        command += ["--previous-status", previous_status]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def run_issue(arg: str, *, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT), "issue", arg]
    return subprocess.run(command, capture_output=True, text=True, check=False, input=stdin)


def test_valid_draft_spec_passes(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text(VALID_SPEC)

    result = run_spec(spec)

    assert result.returncode == 0, result.stdout
    assert result.stdout == ""


def test_missing_frontmatter_fails(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text("# No frontmatter here\n")

    result = run_spec(spec)

    assert result.returncode != 0
    assert "missing YAML frontmatter" in result.stdout


def test_unknown_status_fails(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text(VALID_SPEC.replace("status: draft", "status: bogus"))

    result = run_spec(spec)

    assert result.returncode != 0
    assert "unknown status: bogus" in result.stdout


def test_illegal_transition_fails(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text(APPROVED_ACTIVE_SPEC.replace("status: active", "status: review"))

    result = run_spec(spec, previous_status="draft")

    assert result.returncode != 0
    assert "illegal transition: draft -> review" in result.stdout


def test_forward_one_step_transition_passes(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text(APPROVED_ACTIVE_SPEC)

    result = run_spec(spec, previous_status="draft")

    assert result.returncode == 0, result.stdout


def test_same_status_transition_passes(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text(VALID_SPEC)

    result = run_spec(spec, previous_status="draft")

    assert result.returncode == 0, result.stdout


def test_any_status_to_archived_passes(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text(VALID_SPEC.replace("status: draft", "status: archived"))

    result = run_spec(spec, previous_status="review")

    assert result.returncode == 0, result.stdout


def test_backward_transition_fails(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text(APPROVED_ACTIVE_SPEC)

    result = run_spec(spec, previous_status="review")

    assert result.returncode != 0
    assert "illegal transition: review -> active" in result.stdout


def test_transition_away_from_archived_fails(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text(APPROVED_ACTIVE_SPEC)

    result = run_spec(spec, previous_status="archived")

    assert result.returncode != 0
    assert "illegal transition: archived -> active" in result.stdout


def test_unknown_previous_status_with_archived_target_fails(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text(VALID_SPEC.replace("status: draft", "status: archived"))

    result = run_spec(spec, previous_status="bogus")

    assert result.returncode != 0
    assert "unknown previous status: bogus" in result.stdout


def test_empty_desc_fails(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text(VALID_SPEC.replace("desc: a sample spec", "desc:"))

    result = run_spec(spec)

    assert result.returncode != 0
    assert "missing frontmatter key: desc" in result.stdout


def test_unclosed_frontmatter_fails(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text("---\nstatus: draft\ndesc: a sample spec\n")

    result = run_spec(spec)

    assert result.returncode != 0
    assert "unclosed YAML frontmatter" in result.stdout
    assert "block never closes" in result.stdout


def test_missing_file_path_fails_cleanly(tmp_path: Path) -> None:
    spec = tmp_path / "does-not-exist.md"

    result = run_spec(spec)

    assert result.returncode != 0
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    assert len(result.stderr.strip().splitlines()) == 1


@pytest.mark.parametrize("status", ["active", "review", "done"])
def test_missing_marker_fails(tmp_path: Path, status: str) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text(VALID_SPEC.replace("status: draft", f"status: {status}"))

    result = run_spec(spec)

    assert result.returncode != 0
    assert f"missing approval marker for status={status}" in result.stdout


def test_archived_without_marker_passes(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text(VALID_SPEC.replace("status: draft", "status: archived"))

    result = run_spec(spec)

    assert result.returncode == 0, result.stdout


def test_marker_not_required_on_draft_status(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text(VALID_SPEC)

    result = run_spec(spec)

    assert result.returncode == 0, result.stdout


def test_valid_issue_body_passes(tmp_path: Path) -> None:
    issue = tmp_path / "issue.md"
    issue.write_text(VALID_ISSUE)

    result = run_issue(str(issue))

    assert result.returncode == 0, result.stdout
    assert result.stdout == ""


def test_missing_section_heading_fails(tmp_path: Path) -> None:
    issue = tmp_path / "issue.md"
    issue.write_text(VALID_ISSUE.replace("## Scope\n\nIn scope: the thing.\n\n", ""))

    result = run_issue(str(issue))

    assert result.returncode != 0
    assert "missing section heading: ## Scope" in result.stdout


def test_acceptance_criteria_without_checklist_item_fails(tmp_path: Path) -> None:
    issue = tmp_path / "issue.md"
    issue.write_text(VALID_ISSUE.replace("- [ ] it works\n- [x] it is tested\n", "Nothing checked off.\n"))

    result = run_issue(str(issue))

    assert result.returncode != 0
    assert "Acceptance criteria section has no checklist items" in result.stdout


def test_stdin_mode_reads_issue_from_dash() -> None:
    result = run_issue("-", stdin=VALID_ISSUE)

    assert result.returncode == 0, result.stdout
    assert result.stdout == ""
