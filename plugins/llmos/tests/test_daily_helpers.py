"""Prove the llmOS-profile daily-note helpers (spec 0014 behavior 8):
`get_or_create_daily` creates from the vault's daily template with the
contract properties (Reviews category, no project, bare date title) only
when the day's note is absent, and is idempotent otherwise; `append_thought`
lands new prose under `## Thoughts` and refuses -- raising
`MachineOwnedBlock` -- any write that would touch the `llmos-activity`
marker block; `read_recent_dailies` reads the last N notes headlessly. The
obsidian-cli write backend is mocked at `mutations.run`, the same boundary
`test_obsidian_backend.py` uses; reads never touch it.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from datetime import date
from pathlib import Path

import pytest

from llmos_vault import mutations
from llmos_vault.daily import (
    MARKER_END,
    MARKER_START,
    MachineOwnedBlock,
    append_thought,
    get_or_create_daily,
    read_recent_dailies,
)
from llmos_vault.obsidian_cli import ObsidianNotRunning

DAILY_TEMPLATE_TEXT = textwrap.dedent(
    """\
    ---
    status: active
    created: "{{date:YYYY-MM-DD}}"
    updated: "{{date:YYYY-MM-DD}}"
    categories:
      - "[[Reviews]]"
    ---

    # {{date:YYYY-MM-DD}}

    ## Thoughts

    ## Projects

    <!-- llmos-activity:start -->
    <!-- llmos-activity:end -->

    ![[Daily Reviews.base#Created on day]]
    """
)


def make_vault(root: Path) -> Path:
    (root / ".obsidian").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# fake vault\n")
    (root / "templates").mkdir()
    (root / "templates" / "daily-note.md").write_text(DAILY_TEMPLATE_TEXT)
    return root


def seed_daily(root: Path, day: str, body_extra: str = "") -> Path:
    note_dir = root / "reviews" / "daily"
    note_dir.mkdir(parents=True, exist_ok=True)
    text = (
        f'---\nstatus: active\ncreated: "{day}"\nupdated: "{day}"\n'
        'categories:\n  - "[[Reviews]]"\n---\n\n'
        f"# {day}\n\n## Thoughts\n{body_extra}\n## Projects\n\n"
        f"{MARKER_START}\n"
        "- [[projects/agent-toolbox]]: seeded machine content\n"
        f"{MARKER_END}\n\n"
        "![[Daily Reviews.base#Created on day]]\n"
    )
    path = note_dir / f"{day}.md"
    path.write_text(text)
    return path


def install_fake_obsidian(monkeypatch, vault_root: Path):
    def fake_run(root, verb, *, file=None, path=None, params=None, content=None):
        assert verb == "create"
        assert path is not None
        params = params or {}
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if "template" in params:
            template_text = (root / "templates" / f"{params['template']}.md").read_text()
            day = path.rsplit("/", 1)[-1].removesuffix(".md")
            target.write_text(template_text.replace("{{date:YYYY-MM-DD}}", day))
            return f"Created: {path}\n"
        if params.get("overwrite") == "true":
            target.write_text(content)
            return f"Created: {path}\n"
        raise AssertionError(f"unexpected create params: {params}")

    monkeypatch.setattr(mutations, "run", fake_run)


def refuse_to_run(*args, **kwargs):
    pytest.fail("mutations.run must not be called")


# -- get_or_create_daily ---------------------------------------------------


def test_get_or_create_daily_creates_from_template_with_contract_properties(tmp_path, monkeypatch):
    vault = make_vault(tmp_path / "vault")
    install_fake_obsidian(monkeypatch, vault)

    note = get_or_create_daily(vault, today=date(2026, 7, 17))

    assert note.properties == {
        "status": "active",
        "created": "2026-07-17",
        "updated": "2026-07-17",
        "categories": ["[[Reviews]]"],
    }
    assert "project" not in note.properties
    assert note.body.startswith("# 2026-07-17")
    assert note.name == "2026-07-17"


def test_get_or_create_daily_is_idempotent_for_existing_note(tmp_path, monkeypatch):
    vault = make_vault(tmp_path / "vault")
    seed_daily(vault, "2026-07-15")
    monkeypatch.setattr(mutations, "run", refuse_to_run)

    note = get_or_create_daily(vault, today=date(2026, 7, 15))

    assert note.properties["created"] == "2026-07-15"
    assert note.name == "2026-07-15"


def test_get_or_create_daily_propagates_obsidian_not_running(tmp_path, monkeypatch):
    vault = make_vault(tmp_path / "vault")

    def fake_run(*args, **kwargs):
        raise ObsidianNotRunning("obsidian-cli could not reach a running Obsidian app")

    monkeypatch.setattr(mutations, "run", fake_run)

    with pytest.raises(ObsidianNotRunning):
        get_or_create_daily(vault, today=date(2026, 7, 17))


# -- append_thought ---------------------------------------------------------


def test_append_thought_lands_under_thoughts_heading(tmp_path, monkeypatch):
    vault = make_vault(tmp_path / "vault")
    seed_daily(vault, "2026-07-16", body_extra="\nExisting thought.\n")
    install_fake_obsidian(monkeypatch, vault)

    append_thought(vault, "New thought here.", today=date(2026, 7, 16))

    written = (vault / "reviews" / "daily" / "2026-07-16.md").read_text()
    thoughts_section = written.split("## Thoughts")[1].split("## Projects")[0]
    assert "Existing thought." in thoughts_section
    assert "New thought here." in thoughts_section
    assert thoughts_section.index("Existing thought.") < thoughts_section.index("New thought here.")


def test_append_thought_never_touches_or_reorders_marker_block(tmp_path, monkeypatch):
    vault = make_vault(tmp_path / "vault")
    seed_daily(vault, "2026-07-16", body_extra="\nExisting thought.\n")
    original = (vault / "reviews" / "daily" / "2026-07-16.md").read_text()
    original_marker_onward = original[original.index(MARKER_START) :]
    install_fake_obsidian(monkeypatch, vault)

    append_thought(vault, "New thought here.", today=date(2026, 7, 16))

    written = (vault / "reviews" / "daily" / "2026-07-16.md").read_text()
    assert written[written.index(MARKER_START) :] == original_marker_onward


def test_append_thought_creates_daily_note_first_if_absent(tmp_path, monkeypatch):
    vault = make_vault(tmp_path / "vault")
    install_fake_obsidian(monkeypatch, vault)

    append_thought(vault, "First thought of the day.", today=date(2026, 7, 17))

    written = (vault / "reviews" / "daily" / "2026-07-17.md").read_text()
    assert "First thought of the day." in written.split("## Thoughts")[1].split("## Projects")[0]


def test_append_thought_refuses_when_text_contains_marker_syntax(tmp_path, monkeypatch):
    vault = make_vault(tmp_path / "vault")
    seed_daily(vault, "2026-07-16")
    monkeypatch.setattr(mutations, "run", refuse_to_run)

    with pytest.raises(MachineOwnedBlock):
        append_thought(vault, f"sneaky {MARKER_START} injection", today=date(2026, 7, 16))


def test_append_thought_refuses_when_note_has_no_marker_pair(tmp_path, monkeypatch):
    vault = make_vault(tmp_path / "vault")
    note_dir = vault / "reviews" / "daily"
    note_dir.mkdir(parents=True)
    (note_dir / "2026-07-16.md").write_text(
        '---\nstatus: active\ncreated: "2026-07-16"\ncategories:\n  - "[[Reviews]]"\n---\n\n'
        "# 2026-07-16\n\n## Thoughts\n\n## Projects\n"
    )
    monkeypatch.setattr(mutations, "run", refuse_to_run)

    with pytest.raises(MachineOwnedBlock):
        append_thought(vault, "a thought", today=date(2026, 7, 16))


# -- read_recent_dailies ------------------------------------------------------


def test_read_recent_dailies_returns_last_n_most_recent_first(tmp_path):
    vault = make_vault(tmp_path / "vault")
    for day in ["2026-07-10", "2026-07-11", "2026-07-12", "2026-07-13", "2026-07-14"]:
        seed_daily(vault, day)

    notes = read_recent_dailies(vault, 3)

    assert [note.name for note in notes] == ["2026-07-14", "2026-07-13", "2026-07-12"]


def test_read_recent_dailies_stays_headless_when_obsidian_is_unreachable(tmp_path, monkeypatch):
    vault = make_vault(tmp_path / "vault")
    seed_daily(vault, "2026-07-17")

    def fake_run(argv, **kwargs):
        raise FileNotFoundError("obsidian-cli")

    monkeypatch.setattr(subprocess, "run", fake_run)

    notes = read_recent_dailies(vault, 1)

    assert notes[0].name == "2026-07-17"
    assert notes[0].properties["categories"] == ["[[Reviews]]"]


def test_read_recent_dailies_returns_empty_list_when_no_dailies_dir(tmp_path):
    vault = make_vault(tmp_path / "vault")

    assert read_recent_dailies(vault, 7) == []


# -- CLI: profile gate --------------------------------------------------------


def run_cli(vault_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    import os

    env = dict(os.environ)
    env["LLMOS_ROOT"] = str(vault_root)
    return subprocess.run(
        [sys.executable, "-m", "llmos_vault.cli", "daily", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_daily_rejects_non_llmos_vault():
    result = run_cli(Path("/unused"), "recent", "--vault", "xbrain")

    assert result.returncode != 0
    assert "llmOS-profile" in result.stderr
    assert "xbrain" in result.stderr


def test_cli_daily_recent_reads_headless_json(tmp_path):
    vault = make_vault(tmp_path / "vault")
    seed_daily(vault, "2026-07-17")

    result = run_cli(vault, "recent", "--n", "1")

    assert result.returncode == 0
    assert '"name": "2026-07-17"' in result.stdout
    assert '"[[Reviews]]"' in result.stdout
