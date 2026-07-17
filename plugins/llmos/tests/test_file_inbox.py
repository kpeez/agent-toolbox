"""Prove the llmOS-profile inbox-filing verb (spec 0014 behavior 6):
`file_inbox_item` moves an inbox note via obsidian-cli (mocked subprocess,
the same boundary `test_obsidian_backend.py`/`test_daily_helpers.py` use),
stamps `categories`/`project` derived from the destination path the same way
`scripts/audit_metadata.py --fix` does for specs, appends the acting
provider to `authors`, and appends a filed-note line to today's daily note
outside the `llmos-activity` markers. A destination outside the recognized
vault areas (knowledge, projects, sources, archive) is rejected before any
move. A retry after a stamping failure completes stamping and the daily line
without re-moving the note or duplicating `authors`.
"""

from __future__ import annotations

import textwrap
from datetime import date
from pathlib import Path

import pytest

from llmos_vault import frontmatter, mutations
from llmos_vault.inbox import destination_properties, file_inbox_item
from llmos_vault.notes import read_note
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
    """
)


def make_vault(root: Path) -> Path:
    (root / ".obsidian").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# fake vault\n")
    (root / "templates").mkdir()
    (root / "templates" / "daily-note.md").write_text(DAILY_TEMPLATE_TEXT)
    return root


def seed_inbox_note(root: Path, name: str, extra_frontmatter: str = "") -> Path:
    inbox = root / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    path = inbox / f"{name}.md"
    path.write_text(f"---\ncreated: 2026-07-16\n{extra_frontmatter}---\n\n# {name}\n")
    return path


def seed_project_landing(root: Path, slug: str, title: str) -> None:
    landing = root / "projects" / slug / f"{slug}.md"
    landing.parent.mkdir(parents=True, exist_ok=True)
    landing.write_text(f"---\nstatus: active\ncreated: 2026-07-01\n---\n\n# {title}\n")


def _resolve_target(root: Path, file) -> Path:
    direct = root / (file if file.endswith(".md") else f"{file}.md")
    if direct.exists():
        return direct
    stem = Path(file).stem
    matches = [p for p in root.rglob(f"{stem}.md") if ".obsidian" not in p.parts]
    if len(matches) != 1:
        raise AssertionError(f"cannot resolve fake target for {file!r}: {matches}")
    return matches[0]


def install_fake_obsidian(monkeypatch, vault_root: Path, calls: list[tuple] | None = None):
    def fake_run(root, verb, *, file=None, path=None, params=None, content=None):
        if calls is not None:
            calls.append((verb, file, path, params))
        params = params or {}
        if verb == "move":
            source = _resolve_target(root, file)
            dest = root / params["to"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(source.read_text())
            source.unlink()
            return f"Moved: {file} -> {params['to']}\n"
        if verb == "property:set":
            target = _resolve_target(root, file)
            properties, body = frontmatter.parse(target.read_text())
            if params.get("type") == "list":
                properties[params["name"]] = params["value"].split(",")
            else:
                properties[params["name"]] = params["value"]
            target.write_text(frontmatter.serialize(properties, body))
            return f"Set: {params['name']} = {params['value']}\n"
        if verb == "create":
            assert path is not None
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
        raise AssertionError(f"unexpected fake obsidian-cli call: {verb} {params}")

    monkeypatch.setattr(mutations, "run", fake_run)


def refuse_to_run(*args, **kwargs):
    pytest.fail("mutations.run must not be called")


# -- destination_properties -------------------------------------------------


def test_destination_properties_knowledge(tmp_path):
    vault = make_vault(tmp_path / "vault")

    result = destination_properties(vault, "knowledge/some-note.md")

    assert result == {"categories": ["[[Knowledge]]"]}


def test_destination_properties_sources(tmp_path):
    vault = make_vault(tmp_path / "vault")

    result = destination_properties(vault, "sources/some-source.md")

    assert result == {"categories": ["[[Sources]]"]}


def test_destination_properties_archive(tmp_path):
    vault = make_vault(tmp_path / "vault")

    result = destination_properties(vault, "archive/old-note.md")

    assert result == {"categories": ["[[Archive]]"]}


def test_destination_properties_project_landing_page_omits_self_link(tmp_path):
    vault = make_vault(tmp_path / "vault")
    seed_project_landing(vault, "demo", "Demo")

    result = destination_properties(vault, "projects/demo/demo.md")

    assert result == {"categories": ["[[Projects]]"]}


def test_destination_properties_project_spec_stamps_specifications_and_project(tmp_path):
    vault = make_vault(tmp_path / "vault")
    seed_project_landing(vault, "demo", "Demo")

    result = destination_properties(vault, "projects/demo/specs/0001-thing.md")

    assert result == {
        "categories": ["[[Specifications]]"],
        "project": ["[[projects/demo/demo|Demo]]"],
    }


def test_destination_properties_project_other_note_stamps_project_only(tmp_path):
    vault = make_vault(tmp_path / "vault")
    seed_project_landing(vault, "demo", "Demo")

    result = destination_properties(vault, "projects/demo/handoff.md")

    assert result == {"project": ["[[projects/demo/demo|Demo]]"]}


def test_destination_properties_falls_back_to_slug_when_landing_page_missing(tmp_path):
    vault = make_vault(tmp_path / "vault")

    result = destination_properties(vault, "projects/demo/handoff.md")

    assert result == {"project": ["[[projects/demo/demo|demo]]"]}


def test_destination_properties_rejects_unrecognized_area(tmp_path):
    vault = make_vault(tmp_path / "vault")

    with pytest.raises(ValueError, match="recognized vault filing areas"):
        destination_properties(vault, "templates/something.md")


# -- file_inbox_item ----------------------------------------------------------


def test_file_inbox_item_moves_stamps_and_appends_daily_line(tmp_path, monkeypatch):
    vault = make_vault(tmp_path / "vault")
    seed_inbox_note(vault, "capture-1")
    calls: list[tuple] = []
    install_fake_obsidian(monkeypatch, vault, calls)

    result = file_inbox_item(
        vault, "capture-1", "knowledge/some-note.md", provider="claude", today=date(2026, 7, 17)
    )

    assert "capture-1" in result
    assert "knowledge/some-note.md" in result
    assert [c[0] for c in calls if c[0] == "move"] == ["move"]

    filed = read_note(vault, "knowledge/some-note.md")
    assert filed.properties["categories"] == ["[[Knowledge]]"]
    assert filed.properties["authors"] == ["claude"]
    assert not (vault / "inbox" / "capture-1.md").exists()

    daily_note = (vault / "reviews" / "daily" / "2026-07-17.md").read_text()
    thoughts_section = daily_note.split("## Thoughts")[1].split("## Projects")[0]
    assert "capture-1" in thoughts_section
    assert "knowledge/some-note.md" in thoughts_section


def test_file_inbox_item_stamps_project_and_categories_for_spec_destination(tmp_path, monkeypatch):
    vault = make_vault(tmp_path / "vault")
    seed_project_landing(vault, "demo", "Demo")
    seed_inbox_note(vault, "capture-2")
    install_fake_obsidian(monkeypatch, vault)

    file_inbox_item(
        vault, "capture-2", "projects/demo/specs/0001-thing.md", today=date(2026, 7, 17)
    )

    filed = read_note(vault, "projects/demo/specs/0001-thing.md")
    assert filed.properties["categories"] == ["[[Specifications]]"]
    assert filed.properties["project"] == ["[[projects/demo/demo|Demo]]"]


def test_file_inbox_item_rejects_unrecognized_destination_before_any_move(tmp_path, monkeypatch):
    vault = make_vault(tmp_path / "vault")
    seed_inbox_note(vault, "capture-1")
    monkeypatch.setattr(mutations, "run", refuse_to_run)

    with pytest.raises(ValueError, match="recognized vault filing areas"):
        file_inbox_item(vault, "capture-1", "templates/something.md")

    assert (vault / "inbox" / "capture-1.md").exists()


def test_file_inbox_item_propagates_obsidian_not_running_on_move(tmp_path, monkeypatch):
    vault = make_vault(tmp_path / "vault")
    seed_inbox_note(vault, "capture-1")

    def fake_run(*args, **kwargs):
        raise ObsidianNotRunning("obsidian-cli could not reach a running Obsidian app")

    monkeypatch.setattr(mutations, "run", fake_run)

    with pytest.raises(ObsidianNotRunning):
        file_inbox_item(vault, "capture-1", "knowledge/some-note.md")

    assert (vault / "inbox" / "capture-1.md").exists()


def test_file_inbox_item_retry_after_stamping_failure_completes_without_removing_or_duplicating(
    tmp_path, monkeypatch
):
    vault = make_vault(tmp_path / "vault")
    seed_inbox_note(vault, "capture-1")
    calls: list[tuple] = []
    install_fake_obsidian(monkeypatch, vault, calls)

    real_run = mutations.run

    def failing_on_first_property_set(root, verb, **kwargs):
        if verb == "property:set":
            raise RuntimeError("simulated obsidian-cli failure mid-stamp")
        return real_run(root, verb, **kwargs)

    monkeypatch.setattr(mutations, "run", failing_on_first_property_set)

    with pytest.raises(RuntimeError, match="simulated obsidian-cli failure mid-stamp"):
        file_inbox_item(
            vault, "capture-1", "knowledge/some-note.md", provider="claude", today=date(2026, 7, 17)
        )

    assert not (vault / "inbox" / "capture-1.md").exists()
    assert (vault / "knowledge" / "some-note.md").exists()
    move_calls_before_retry = [c for c in calls if c[0] == "move"]
    assert len(move_calls_before_retry) == 1

    install_fake_obsidian(monkeypatch, vault, calls)

    result = file_inbox_item(
        vault, "capture-1", "knowledge/some-note.md", provider="claude", today=date(2026, 7, 17)
    )

    assert "knowledge/some-note.md" in result
    move_calls_total = [c for c in calls if c[0] == "move"]
    assert len(move_calls_total) == 1, "retry must not re-move an already-filed note"

    filed = read_note(vault, "knowledge/some-note.md")
    assert filed.properties["categories"] == ["[[Knowledge]]"]
    assert filed.properties["authors"] == ["claude"]

    daily_note = (vault / "reviews" / "daily" / "2026-07-17.md").read_text()
    thoughts_section = daily_note.split("## Thoughts")[1].split("## Projects")[0]
    assert thoughts_section.count("capture-1") == 1
