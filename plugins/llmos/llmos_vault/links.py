"""Wikilink extraction, vault-file indexing, and Obsidian-style name
resolution -- the pieces `read_note` and the link graph share (ADR-0004:
reads never touch the app, so this walks the vault directory tree itself
instead of asking Obsidian for its resolved link cache).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from llmos_vault.frontmatter import Property, parse

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


@dataclass(frozen=True)
class VaultIndex:
    root: Path
    paths: list[Path]
    by_stem: dict[str, list[Path]]


def build_index(vault_root: Path) -> VaultIndex:
    """Walk `vault_root` once and index every markdown note by basename.

    Use when resolving wikilinks or note-name arguments against a vault --
    every read/graph verb builds one index per invocation rather than
    re-walking the tree on each lookup. Works with Obsidian closed; it never
    reads anything but the files on disk.
    Do NOT use when you already hold an index for this vault_root in the
    same call -- reuse it instead of rebuilding.

    Example output:
        VaultIndex(root=PosixPath('/vault'), paths=[PosixPath('/vault/notes/alpha.md')],
                   by_stem={'alpha': [PosixPath('/vault/notes/alpha.md')]})

    Example invocation:
        from llmos_vault.links import build_index
        index = build_index(Path("/path/to/vault"))

    Args:
        vault_root: Root directory of the vault to index.
    """
    paths = sorted(p for p in vault_root.rglob("*.md") if ".obsidian" not in p.parts)
    by_stem: dict[str, list[Path]] = {}
    for path in paths:
        by_stem.setdefault(path.stem.lower(), []).append(path)
    return VaultIndex(root=vault_root, paths=paths, by_stem=by_stem)


def extract_wikilinks(text: str) -> list[str]:
    """Extract raw wikilink targets from markdown text or a frontmatter value.

    Use when collecting a note's outgoing links from its body or from a
    frontmatter property value (aliases and `#anchor`s are stripped, so
    `[[Note#Section|label]]` yields `Note`).
    Do NOT use when you need resolved vault paths -- pair the result with
    `resolve_link` or `resolve_note`.

    Example output:
        ['Some Other Note']

    Example invocation:
        from llmos_vault.links import extract_wikilinks
        extract_wikilinks("see [[Some Other Note]]")

    Args:
        text: Markdown body text or a single frontmatter property value.
    """
    return [match.group(1).strip() for match in WIKILINK_RE.finditer(text)]


def resolve_note(index: VaultIndex, target: str) -> Path:
    """Resolve a user-supplied note name or path to exactly one vault file.

    Use when resolving the note argument a human or agent typed -- `read_note`
    and every CLI verb that takes a note name call this so a typo or an
    ambiguous basename fails loudly with the vault-relative candidates listed,
    mirroring Obsidian's own basename-match / qualified-path semantics.
    Do NOT use when resolving a wikilink found inside vault content -- use
    `resolve_link`, which reports ambiguity as unresolved instead of exiting.

    Example output:
        PosixPath('/path/to/vault/notes/alpha.md')

    Example invocation:
        from llmos_vault.links import build_index, resolve_note
        resolve_note(build_index(vault_root), "alpha")

    Args:
        index: Vault index built by `build_index`.
        target: Note basename (wikilink-style) or vault-relative path.
    """
    direct = _direct_path(index, target)
    if direct is not None:
        return direct
    matches = index.by_stem.get(_stem(target), [])
    if not matches:
        sys.exit(f"no note named '{target}' found in vault '{index.root}'")
    if len(matches) > 1:
        candidates = ", ".join(str(p.relative_to(index.root)) for p in matches)
        sys.exit(f"'{target}' is ambiguous, matches: {candidates}")
    return matches[0]


def resolve_link(index: VaultIndex, target: str) -> Path | None:
    """Resolve one wikilink target found in vault content; never raises.

    Use when building the link graph (`get_neighbors`/`get_subgraph`) -- a
    link to a missing, renamed, or ambiguous note must be reported as
    unresolved, not crash the whole command.
    Do NOT use when resolving a note argument typed by a human or agent --
    use `resolve_note`, which fails loudly with candidates on ambiguity
    instead of silently treating it as unresolved.

    Example output:
        None

    Example invocation:
        from llmos_vault.links import build_index, resolve_link
        resolve_link(build_index(vault_root), "Some Other Note")

    Args:
        index: Vault index built by `build_index`.
        target: Raw wikilink target text, as returned by `extract_wikilinks`.
    """
    direct = _direct_path(index, target)
    if direct is not None:
        return direct
    matches = index.by_stem.get(_stem(target), [])
    return matches[0] if len(matches) == 1 else None


def read_frontmatter(path: Path) -> tuple[dict[str, Property], str]:
    """Parse a vault file's frontmatter and body, tolerating notes that have
    none (a bare-body note parses as empty properties, full text as body).

    Use when walking arbitrary vault files -- `list_notes` and the link
    graph read every markdown file, and not every note (or root file like
    AGENTS.md) carries a frontmatter block.
    Do NOT use when the note is known to require frontmatter -- call
    `llmos_vault.frontmatter.parse` directly so a missing block still raises.

    Example output:
        ({'topics': ['gardening']}, '# Alpha\\n...')

    Example invocation:
        from llmos_vault.links import read_frontmatter
        read_frontmatter(Path("/path/to/vault/notes/alpha.md"))

    Args:
        path: Path to a markdown file inside the vault.
    """
    text = path.read_text()
    try:
        return parse(text)
    except ValueError:
        return {}, text


def _stem(target: str) -> str:
    """The by_stem lookup key for a name argument: `.md` stripped (so a bare
    basename typed with its extension, `note.md`, still resolves) and
    lowercased to match the index."""
    return (target[:-3] if target.endswith(".md") else target).lower()


def _direct_path(index: VaultIndex, target: str) -> Path | None:
    stem = target[:-3] if target.endswith(".md") else target
    if "/" not in stem:
        return None
    candidate = (index.root / stem).with_suffix(".md")
    return candidate if candidate in set(index.paths) else None
