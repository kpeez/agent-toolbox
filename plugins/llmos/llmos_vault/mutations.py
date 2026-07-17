"""Mutation verbs: thin wrappers over `obsidian_cli.run` (ADR-0004 -- writes
always shell out to the live app so backlinks get rewritten; this module
never touches vault files directly). Property mutations reuse
`frontmatter.set_scalar`/`append_unique` to decide *what* to write (`created`
stays immutable, `authors` stays append-only) even though the actual file
write happens file-side, through obsidian-cli.
"""

from __future__ import annotations

from pathlib import Path

from llmos_vault import frontmatter
from llmos_vault.notes import read_note
from llmos_vault.obsidian_cli import run


def create_note(
    vault_root: Path,
    name: str,
    *,
    content: str | None = None,
    template: str | None = None,
) -> str:
    """Create a new note, optionally from a vault template, via obsidian-cli.

    Use when an agent needs a brand-new note on disk with the app's own
    creation semantics (template expansion, conflict handling) -- e.g. filing
    a new project note.
    Do NOT use when you want to overwrite an existing note's content --
    obsidian-cli `create` refuses to clobber an existing file; edit it
    directly instead.

    Example output:
        'Created: projects/agent-toolbox.md\\n'

    Example invocation:
        create_note(vault_root, "projects/agent-toolbox", template="project")

    Args:
        vault_root: Root directory of the vault to create the note in.
        name: Vault-relative note path (".md" appended if missing).
        content: Initial body content; multi-line content is staged through
            a temp file rather than shell-quoted inline.
        template: Name of a vault template to apply.

    Raises:
        ObsidianNotRunning: obsidian-cli could not reach a running app.
    """
    target_path = name if name.endswith(".md") else f"{name}.md"
    params = {"template": template} if template is not None else {}
    return run(vault_root, "create", path=target_path, params=params, content=content)


def move_note(vault_root: Path, note: str, to: str) -> str:
    """Move or rename a note via obsidian-cli, rewriting every backlink.

    Use when an agent needs to relocate or rename a note -- the sanctioned
    alternative to raw `mv`/`git mv` (ADR-0004; the PreToolUse Bash guard
    denies those inside a vault and points here) because Obsidian's
    `alwaysUpdateLinks` rewrites every wikilink pointing at the note.
    Do NOT use when you'd reach for raw `mv`/`rm` on a vault note -- see the
    guard hook's message for why.

    Example output:
        'Moved: notes/alpha.md -> archive/alpha.md\\n'

    Example invocation:
        move_note(vault_root, "alpha", "archive/alpha.md")

    Args:
        vault_root: Root directory of the vault the note lives in.
        note: Note name (wikilink-style resolution) or vault-relative path.
        to: Destination folder or path.

    Raises:
        ObsidianNotRunning: obsidian-cli could not reach a running app.
    """
    return run(vault_root, "move", file=note, params={"to": to})


def append_note(vault_root: Path, note: str, content: str) -> str:
    """Append content to an existing note via obsidian-cli.

    Use when an agent needs to add content to the end of a note without
    reading and rewriting the whole file -- e.g. logging a quick note.
    Do NOT use when changing frontmatter -- use `set_property`.

    Example output:
        'Appended to: notes/alpha.md\\n'

    Example invocation:
        append_note(vault_root, "alpha", "One more thought.")

    Args:
        vault_root: Root directory of the vault the note lives in.
        note: Note name (wikilink-style resolution) or vault-relative path.
        content: Content to append; multi-line content is staged through a
            temp file rather than shell-quoted inline.

    Raises:
        ObsidianNotRunning: obsidian-cli could not reach a running app.
    """
    return run(vault_root, "append", file=note, content=content)


def overwrite_note(vault_root: Path, name: str, content: str) -> str:
    """Replace an existing note's full content via obsidian-cli
    `create ... overwrite`.

    Use when a verb has computed a note's entire new body itself (a headless
    read plus a Python-side edit) and needs to write it back in one shot --
    e.g. `daily.append_thought` inserting a paragraph under a heading while
    leaving the rest of the file, including any machine-owned block,
    byte-identical.
    Do NOT use when you only need to add text to the end of a note without
    recomputing the rest of it -- use `append_note` instead.

    Example output:
        'Created: reviews/daily/2026-07-17.md\\n'

    Example invocation:
        overwrite_note(vault_root, "reviews/daily/2026-07-17.md", full_text)

    Args:
        vault_root: Root directory of the vault the note lives in.
        name: Note name (wikilink-style resolution) or vault-relative path.
        content: Full replacement content for the note.

    Raises:
        ObsidianNotRunning: obsidian-cli could not reach a running app.
    """
    target_path = name if name.endswith(".md") else f"{name}.md"
    return run(
        vault_root,
        "create",
        path=target_path,
        params={"overwrite": "true"},
        content=content,
    )


def _assert_mutable_property(key: str) -> None:
    """Reuse `frontmatter.set_scalar`'s immutable-`created` guard without
    touching a real properties dict -- the throwaway dict is discarded."""
    frontmatter.set_scalar({}, key, "")


def set_property(vault_root: Path, note: str, key: str, value: str) -> str:
    """Set a property on a note via obsidian-cli.

    Use when an agent needs to set or update a single frontmatter property
    without hand-editing YAML -- e.g. flipping a status flag.
    `authors` is append-only: setting it merges `value` into the existing
    list (reusing `frontmatter.append_unique`) instead of overwriting it.
    Do NOT use when rewriting `created` -- it is immutable (reuses
    `frontmatter.set_scalar`'s guard) and this call raises `ValueError`.

    Example output:
        'Set: status = active\\n'

    Example invocation:
        set_property(vault_root, "alpha", "status", "active")

    Args:
        vault_root: Root directory of the vault the note lives in.
        note: Note name (wikilink-style resolution) or vault-relative path.
        key: Property name.
        value: Property value to set (or merge into `authors`).

    Raises:
        ValueError: `key` is "created" (immutable).
        ObsidianNotRunning: obsidian-cli could not reach a running app.
    """
    _assert_mutable_property(key)
    if key == "authors":
        current = read_note(vault_root, note).properties
        merged = frontmatter.append_unique(dict(current), key, value)
        values = merged[key]
        assert isinstance(values, list)
        return run(
            vault_root,
            "property:set",
            file=note,
            params={"name": key, "value": ",".join(values), "type": "list"},
        )
    return run(vault_root, "property:set", file=note, params={"name": key, "value": value})


def remove_property(vault_root: Path, note: str, key: str) -> str:
    """Remove a property from a note via obsidian-cli.

    Use when an agent needs to delete a frontmatter property entirely --
    e.g. clearing a stale `status` flag.
    Do NOT use when targeting `created` -- it is immutable (reuses
    `frontmatter.set_scalar`'s guard) and this call raises `ValueError`.

    Example output:
        'Removed: status\\n'

    Example invocation:
        remove_property(vault_root, "alpha", "status")

    Args:
        vault_root: Root directory of the vault the note lives in.
        note: Note name (wikilink-style resolution) or vault-relative path.
        key: Property name to remove.

    Raises:
        ValueError: `key` is "created" (immutable).
        ObsidianNotRunning: obsidian-cli could not reach a running app.
    """
    _assert_mutable_property(key)
    return run(vault_root, "property:remove", file=note, params={"name": key})
