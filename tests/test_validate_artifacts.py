"""Tests for the spec frontmatter rules in plugins/swe/scripts/validate_artifacts.py.

Approval, execution mode, and the tracker container all moved out of HTML
comments in the body and into frontmatter, so the validator is what keeps them
present and well-formed.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "swe" / "scripts" / "validate_artifacts.py"
TEMPLATES = ROOT / "plugins" / "swe" / "skills" / "write-spec" / "templates.md"

spec_loader = importlib.util.spec_from_file_location("validate_artifacts", SCRIPT)
assert spec_loader and spec_loader.loader
validator = importlib.util.module_from_spec(spec_loader)
spec_loader.loader.exec_module(validator)


def spec_text(**keys: str | None) -> str:
    frontmatter = {"status": "review", "desc": "a spec"} | keys
    lines = "\n".join(f"{k}: {v}" for k, v in frontmatter.items() if v is not None)
    return f"---\n{lines}\n---\n\n# A spec\n"


def violations(**keys: str | None) -> list[str]:
    return validator.validate_spec(spec_text(**keys), None)


PUBLISHED = {
    "approved": "true",
    "tracker": "linear",
    "tracker_container": "c-1",
}


def test_a_published_spec_with_every_key_is_clean() -> None:
    assert violations(**PUBLISHED) == []


def test_a_draft_needs_neither_approval_nor_container() -> None:
    assert violations(status="draft") == []


def test_a_published_spec_without_approval_is_rejected() -> None:
    found = violations(**{**PUBLISHED, "approved": None})
    assert any("missing approval for status=review" in v for v in found)


def test_approval_must_be_true_not_merely_present() -> None:
    found = violations(**{**PUBLISHED, "approved": "false"})
    assert any("missing approval" in v for v in found)


def test_a_published_spec_without_a_container_is_rejected() -> None:
    found = validator.validate_spec(spec_text(approved="true"), None)
    assert any("missing tracker_container" in v for v in found)


def test_tracker_and_container_must_be_set_together() -> None:
    found = violations(**{**PUBLISHED, "tracker": None})
    assert any("must be set together" in v for v in found)


def test_an_unknown_tracker_is_rejected() -> None:
    found = violations(**{**PUBLISHED, "tracker": "jira"})
    assert any("invalid tracker" in v for v in found)


def test_an_unknown_execution_mode_is_rejected() -> None:
    found = violations(**{**PUBLISHED, "execution_mode": "yolo"})
    assert any("invalid execution_mode" in v for v in found)


def test_both_execution_modes_are_accepted() -> None:
    for mode in ("autonomous", "review-gated"):
        assert violations(**{**PUBLISHED, "execution_mode": mode}) == []


def test_an_archived_spec_is_exempt_from_approval() -> None:
    """It may be an abandoned draft that was never approved at all."""
    assert violations(status="archived") == []


def spec_with_tasks(tasks_block: str) -> str:
    return f"---\nstatus: draft\ndesc: a spec\n---\n\n## Tasks\n\n{tasks_block}\n"


def test_a_well_formed_tasks_section_passes() -> None:
    tasks = (
        "- [ ] T1: Add the widget — a one-line brief\n"
        "- [ ] T2: Wire it up — a brief (after: T1)\n"
    )
    assert validator.validate_spec(spec_with_tasks(tasks), None) == []


def test_a_malformed_task_line_is_rejected() -> None:
    found = validator.validate_spec(
        spec_with_tasks("- [ ] T1 missing the colon and brief\n"), None
    )
    assert any("malformed task line" in v for v in found)


def test_a_dangling_after_reference_is_rejected() -> None:
    found = validator.validate_spec(
        spec_with_tasks("- [ ] T1: Add the widget — a brief (after: T9)\n"), None
    )
    assert any("dangling 'after' reference" in v and "T9" in v for v in found)


def test_a_spec_without_a_tasks_section_still_passes() -> None:
    assert violations(status="draft") == []


def test_a_duplicate_task_id_is_rejected() -> None:
    tasks = (
        "- [ ] T1: Add the widget — a brief\n"
        "- [ ] T1: Add it again — a different brief\n"
    )
    found = validator.validate_spec(spec_with_tasks(tasks), None)
    assert any("duplicate task id" in v and "T1" in v for v in found)


def test_a_self_referential_after_is_rejected() -> None:
    found = validator.validate_spec(
        spec_with_tasks("- [ ] T2: Wire it up — a brief (after: T2)\n"), None
    )
    assert any("self-referential" in v and "T2" in v for v in found)


def test_a_brief_with_a_parenthetical_passes() -> None:
    tasks = "- [ ] T1: Add widget — brief (see ADR-0014)\n"
    assert validator.validate_spec(spec_with_tasks(tasks), None) == []


def test_a_brief_with_a_parenthetical_and_a_trailing_after_passes() -> None:
    tasks = "- [ ] T2: Add widget — brief (see ADR-0014) (after: T1)\n"
    found = validator.validate_spec(
        f"---\nstatus: draft\ndesc: a spec\n---\n\n## Tasks\n\n"
        f"- [ ] T1: First — a brief\n{tasks}\n",
        None,
    )
    assert found == []


def test_a_tasks_section_before_the_divider_with_design_after_passes() -> None:
    """The template's actual shape: `## Tasks` sits before the `---` zone
    divider, and a `## Design` heading follows the divider. The guidance
    comment and the divider itself must not be mistaken for task lines."""
    body = (
        "---\nstatus: draft\ndesc: a spec\n---\n\n"
        "## Validation\n\n<!-- commands/tests that prove the goal -->\n\n"
        "## Tasks\n\n"
        "<!-- Parsed by the start-loop run procedure: one implementer subagent per task.\n"
        "     - [ ] T1: <title> — <one-line brief>\n"
        "     - [ ] T2: <title> — <brief> (after: T1)\n"
        '     Task ids are T<n>; optional "(after: Tm[, Tk])" declares dependencies. -->\n\n'
        "---\n\n"
        "## Design\n\n<!-- architecture, key components -->\n"
    )
    assert validator.validate_spec(body, None) == []


def test_prose_mentioning_the_tasks_heading_does_not_hijack_the_section() -> None:
    """A `## Tasks` mention inside prose (e.g. a Scope bullet in backticks)
    must not be mistaken for the real heading, since it isn't line-anchored."""
    body = (
        "---\nstatus: draft\ndesc: a spec\n---\n\n"
        "## Scope\n\n"
        "- Parses the spec's `## Tasks` section (not this text)\n\n"
        "## Tasks\n\n"
        "- [ ] T1: Add the widget — a one-line brief\n"
    )
    assert validator.validate_spec(body, None) == []


def test_an_acceptance_criteria_section_with_a_divider_still_validates() -> None:
    """`extract_section`'s shared `---` terminator is scoped to Tasks; an issue's
    Acceptance criteria section may contain its own horizontal rule without
    truncating the checklist that follows it."""
    body = (
        "## What to build\n\nA widget.\n\n"
        "## Acceptance criteria\n\n"
        "Some context.\n\n---\n\n"
        "- [ ] It works\n\n"
        "## Scope\n\nIn scope.\n\n"
        "## Blocked by\n\nNothing.\n"
    )
    assert validator.validate_issue(body) == []


def test_the_actual_template_body_validates_clean() -> None:
    """Run the validator against write-spec's own template body, not a
    reconstructed fixture."""
    text = TEMPLATES.read_text()
    match = re.search(
        r'<template file="docs/agents/specs/NNNN-<slug>\.md">\n(.*?)</template>',
        text,
        re.DOTALL,
    )
    assert match is not None
    assert validator.validate_spec(match.group(1), None) == []
