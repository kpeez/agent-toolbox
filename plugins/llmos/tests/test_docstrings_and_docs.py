"""Prove the docs pipeline (spec 0014 behavior 10): the committed
`references/commands.md` and the skill's verb table match what regenerating
from the live command tree produces, so agents never read stale verb docs.
"""

from __future__ import annotations

from pathlib import Path

from llmos_vault.cli import DEFAULT_REFERENCE_PATH, DEFAULT_SKILL_PATH, app
from llmos_vault.docs import write_reference


def test_committed_reference_matches_regeneration(tmp_path: Path):
    regenerated_reference = tmp_path / "commands.md"
    regenerated_skill = tmp_path / "SKILL.md"
    regenerated_skill.write_text(DEFAULT_SKILL_PATH.read_text())

    write_reference(app, regenerated_reference, regenerated_skill)

    assert regenerated_reference.read_text() == DEFAULT_REFERENCE_PATH.read_text(), (
        "references/commands.md is stale -- run `uv run llmos-vault docs` to regenerate"
    )


def test_committed_skill_table_matches_regeneration(tmp_path: Path):
    regenerated_reference = tmp_path / "commands.md"
    regenerated_skill = tmp_path / "SKILL.md"
    regenerated_skill.write_text(DEFAULT_SKILL_PATH.read_text())

    write_reference(app, regenerated_reference, regenerated_skill)

    assert regenerated_skill.read_text() == DEFAULT_SKILL_PATH.read_text(), (
        "the skill's verb table is stale -- run `uv run llmos-vault docs` to regenerate"
    )
