"""Headless note reads: parse a note's frontmatter and body straight off
disk, no Obsidian dependency (ADR-0004 -- reads are always safe with the app
closed, including for the nightly cron).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from llmos_vault.frontmatter import Property
from llmos_vault.links import build_index, read_frontmatter, resolve_note


@dataclass(frozen=True)
class Note:
    path: Path
    name: str
    properties: dict[str, Property]
    body: str


def read_note(vault_root: Path, name_or_path: str) -> Note:
    """Read one note's frontmatter and body straight off disk.

    Use when an agent needs a note's current content or properties -- to
    inspect before editing, or to script a decision on a property value.
    Works with Obsidian closed.
    Do NOT use when you need every note in the vault -- use `list_notes`,
    it walks the tree once instead of resolving names one at a time.

    Example output:
        Note(path=PosixPath('/vault/notes/alpha.md'), name='alpha',
             properties={'topics': ['gardening']}, body='# Alpha\\n...')

    Example invocation:
        llmos-vault read alpha --vault llmos

    Args:
        vault_root: Root directory of the vault to read from.
        name_or_path: Note basename (wikilink-style) or vault-relative path.
    """
    index = build_index(vault_root)
    path = resolve_note(index, name_or_path)
    properties, body = read_frontmatter(path)
    return Note(path=path, name=path.stem, properties=properties, body=body)


def list_notes(vault_root: Path) -> list[Note]:
    """List every note in the vault with its parsed frontmatter and body.

    Use when an agent needs to enumerate or scan all notes -- e.g. finding
    every note missing a property before scripting a bulk decision.
    Do NOT use when you already know which note you want -- use `read_note`,
    it skips parsing the rest of the vault.

    Example output:
        [Note(path=PosixPath('/vault/notes/alpha.md'), name='alpha',
              properties={'topics': ['gardening']}, body='# Alpha\\n...'), ...]

    Example invocation:
        llmos-vault list --vault llmos

    Args:
        vault_root: Root directory of the vault to enumerate.
    """
    index = build_index(vault_root)
    notes = []
    for path in index.paths:
        properties, body = read_frontmatter(path)
        notes.append(Note(path=path, name=path.stem, properties=properties, body=body))
    return notes
