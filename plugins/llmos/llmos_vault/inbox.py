"""The llmOS-profile inbox-filing verb (spec 0014 behavior 6): every inbox
item eventually moves to a real home or is deleted, and filing it is one
ritual rather than three manual steps an agent could get out of order. Moves
via obsidian-cli so backlinks follow, stamps `categories`/`project` the same
way the destination path already implies them for the audit tooling
(`llmos_vault.schema.project_alias`), and records the filing in today's daily
note via `daily.append_thought` -- never inside the machine-owned
`llmos-activity` block, since that helper already refuses to touch it.
Ordered so a partial failure never strands the note half-filed: stamping
only runs after a successful move, and the daily-note line only after
successful stamping. A retry after a stamping failure is safe -- a note
already on disk at `destination` (filing routinely renames as well as
relocates, so the note can no longer be found under its original name) is
taken as already moved and the move step is skipped, and already-set
properties are left alone.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from llmos_vault import daily, mutations
from llmos_vault.notes import read_note
from llmos_vault.schema import SPEC_NAME, project_alias

RECOGNIZED_AREAS = frozenset({"knowledge", "projects", "sources", "archive"})
AREA_CATEGORIES = {
    "knowledge": "[[Knowledge]]",
    "sources": "[[Sources]]",
    "archive": "[[Archive]]",
}


def destination_properties(vault_root: Path, destination: str) -> dict[str, list[str]]:
    """Derive the `categories`/`project` properties a destination path implies.

    Use when a filing verb needs to know what graph properties a note's new
    home implies -- the same derivation `scripts/audit_metadata.py --fix`
    uses for specs, generalized to every recognized top-level vault area. A
    project's own landing page (`projects/<slug>/<slug>.md`) gets
    `[[Projects]]` with no self-referential `project` link, per schema.md; a
    canonical spec gets `[[Specifications]]` plus the project link; any other
    project-owned note gets the project link alone.
    Do NOT use when `destination`'s top-level folder is not one of
    `knowledge`, `projects`, `sources`, `archive` -- that raises `ValueError`
    rather than guess a category.

    Example output:
        {'categories': ['[[Specifications]]'],
         'project': ['[[projects/demo/demo|Demo]]']}

    Example invocation:
        from llmos_vault.inbox import destination_properties
        destination_properties(vault_root, "projects/demo/specs/0001-thing.md")

    Args:
        vault_root: Root directory of the llmOS vault.
        destination: Vault-relative destination path (".md" appended if
            missing).

    Raises:
        ValueError: `destination`'s top-level folder is not a recognized
            filing area.
    """
    target = destination if destination.endswith(".md") else f"{destination}.md"
    parts = Path(target).parts
    area = parts[0] if parts else ""
    if area not in RECOGNIZED_AREAS:
        raise ValueError(
            f"destination '{destination}' is outside the recognized vault filing "
            f"areas ({', '.join(sorted(RECOGNIZED_AREAS))})"
        )
    if area != "projects":
        return {"categories": [AREA_CATEGORIES[area]]}

    if len(parts) < 2:
        raise ValueError(f"destination '{destination}' names no project slug")
    slug = parts[1]
    if len(parts) == 3 and parts[-1] == f"{slug}.md":
        return {"categories": ["[[Projects]]"]}

    project_link = f"[[projects/{slug}/{slug}|{project_alias(vault_root, slug)}]]"
    if "specs" in parts and SPEC_NAME.fullmatch(Path(target).name):
        return {"categories": ["[[Specifications]]"], "project": [project_link]}
    return {"project": [project_link]}


def file_inbox_item(
    vault_root: Path,
    note: str,
    destination: str,
    *,
    provider: str | None = None,
    today: date | None = None,
) -> str:
    """File an inbox note to its destination: move it via obsidian-cli
    (backlinks follow), stamp the destination-derived `categories`/`project`
    properties, append `provider` to `authors`, and record the filing in
    today's daily note.

    Use when an inbox capture has a real home -- the sanctioned ritual so an
    agent never files a note half-way (a raw move with no property stamp, or
    a stamp with no daily-note record). Requires Obsidian to be running.
    Ordered so a failure never strands the note: the move must succeed before
    any property is stamped, and stamping must succeed before the daily-note
    line is appended. Safe to re-run after a failure partway through -- a
    note already on disk at `destination` is taken as already moved and is
    not moved again, and `authors` never gains a duplicate.
    Do NOT use when `destination`'s top-level folder is not `knowledge`,
    `projects`, `sources`, or `archive` -- rejected with `ValueError` before
    any move is attempted.

    Example output:
        'Filed: capture-1 -> knowledge/some-note.md\\n'

    Example invocation:
        from llmos_vault.inbox import file_inbox_item
        file_inbox_item(vault_root, "capture-1", "knowledge/some-note.md", provider="claude")

    Args:
        vault_root: Root directory of the llmOS vault.
        note: Note name (wikilink-style resolution) or vault-relative path
            of the inbox item to file.
        destination: Vault-relative destination path (".md" appended if
            missing).
        provider: Acting provider name to append to `authors`; omitted if None.
        today: Date to record the filing under in the daily note; defaults
            to today.

    Raises:
        ValueError: `destination` is outside the recognized filing areas.
        ObsidianNotRunning: obsidian-cli could not reach a running app.
    """
    dest_rel = destination if destination.endswith(".md") else f"{destination}.md"
    properties_to_stamp = destination_properties(vault_root, dest_rel)

    destination_path = vault_root / dest_rel
    if not destination_path.exists():
        mutations.move_note(vault_root, note, dest_rel)

    current = read_note(vault_root, dest_rel)
    for key, values in properties_to_stamp.items():
        if key not in current.properties:
            mutations.set_property_list(vault_root, dest_rel, key, values)
    if provider:
        mutations.set_property(vault_root, dest_rel, "authors", provider)

    thought = f"Filed `{note}` from inbox -> `{dest_rel}`."
    daily.append_thought(vault_root, thought, today=today)

    return f"Filed: {note} -> {dest_rel}\n"
