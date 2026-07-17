"""The vault link graph: outgoing links, backlinks, and shared-topic
siblings, built by walking the vault fresh on every call (ADR-0004 --
headless reads, safe for the nightly cron with Obsidian closed). A note's
`topics` frontmatter property is the sibling key; it is a generic vault
convention, not an llmOS-specific schema assumption, so the same code path
serves any vault selected via `--vault`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from llmos_vault.links import (
    VaultIndex,
    build_index,
    extract_wikilinks,
    read_frontmatter,
    resolve_link,
    resolve_note,
)


@dataclass(frozen=True)
class Neighbors:
    note: str
    outgoing: list[str]
    unresolved_outgoing: list[str]
    backlinks: list[str]
    topic_siblings: list[str]


@dataclass(frozen=True)
class Subgraph:
    root: str
    nodes: list[str]
    unresolved: list[str]
    edges: list[tuple[str, str, str]]


def get_neighbors(vault_root: Path, name_or_path: str) -> Neighbors:
    """Get one note's outgoing links, backlinks, and shared-topic siblings.

    Use when an agent needs a note's local link neighborhood -- e.g. before
    editing a note, to see what already points at it or shares its topics.
    Works with Obsidian closed; the graph is built fresh from disk.
    Do NOT use when you need more than one hop out -- use `get_subgraph`.

    Example output:
        Neighbors(note='alpha', outgoing=['beta'], unresolved_outgoing=['ghost'],
                  backlinks=['delta'], topic_siblings=['beta', 'gamma'])

    Example invocation:
        llmos-vault neighbors alpha --vault llmos

    Args:
        vault_root: Root directory of the vault to read from.
        name_or_path: Note basename (wikilink-style) or vault-relative path.
    """
    index = build_index(vault_root)
    path = resolve_note(index, name_or_path)
    outgoing, unresolved = _outgoing(index, path)
    backlinks = _backlinks(index, path)
    siblings = _topic_siblings(index, path)
    return Neighbors(
        note=path.stem,
        outgoing=sorted({p.stem for p in outgoing}),
        unresolved_outgoing=sorted(set(unresolved)),
        backlinks=sorted({p.stem for p in backlinks}),
        topic_siblings=sorted({p.stem for p in siblings}),
    )


def get_subgraph(vault_root: Path, name_or_path: str, depth: int = 1) -> Subgraph:
    """Get the transitive neighborhood of a note out to `depth` hops.

    Use when an agent needs the broader cluster around a note -- e.g. to
    scope a rename's blast radius, or to see a topic's full note cluster.
    Traverses the same three relations as `get_neighbors` (outgoing links,
    backlinks, shared-topic siblings) at each hop; unresolved wikilinks are
    collected, never raised as errors.
    Do NOT use when you only need the immediate neighbors -- `get_neighbors`
    is cheaper and returns the same one-hop data without traversal.

    Example output:
        Subgraph(root='alpha', nodes=['alpha', 'beta', 'delta', 'gamma'],
                 unresolved=['ghost'],
                 edges=[('alpha', 'beta', 'link'), ('delta', 'alpha', 'link'),
                        ('alpha', 'gamma', 'topic_sibling')])

    Example invocation:
        llmos-vault subgraph alpha --vault llmos --depth 2

    Args:
        vault_root: Root directory of the vault to read from.
        name_or_path: Note basename (wikilink-style) or vault-relative path.
        depth: Number of hops to traverse outward from the note.
    """
    index = build_index(vault_root)
    root_path = resolve_note(index, name_or_path)
    visited = {root_path}
    frontier = {root_path}
    edges: set[tuple[str, str, str]] = set()
    unresolved: set[str] = set()

    for _ in range(depth):
        next_frontier: set[Path] = set()
        for path in frontier:
            outgoing, unresolved_targets = _outgoing(index, path)
            unresolved.update(unresolved_targets)
            for target in outgoing:
                edges.add((path.stem, target.stem, "link"))
                if target not in visited:
                    next_frontier.add(target)
            for source in _backlinks(index, path):
                edges.add((source.stem, path.stem, "link"))
                if source not in visited:
                    next_frontier.add(source)
            for sibling in _topic_siblings(index, path):
                first, second = sorted((path.stem, sibling.stem))
                edges.add((first, second, "topic_sibling"))
                if sibling not in visited:
                    next_frontier.add(sibling)
        if not next_frontier:
            break
        visited |= next_frontier
        frontier = next_frontier

    return Subgraph(
        root=root_path.stem,
        nodes=sorted(p.stem for p in visited),
        unresolved=sorted(unresolved),
        edges=sorted(edges),
    )


def _linked_targets(path: Path) -> list[str]:
    properties, body = read_frontmatter(path)
    targets = extract_wikilinks(body)
    for value in properties.values():
        for item in value if isinstance(value, list) else [value]:
            targets.extend(extract_wikilinks(item))
    return targets


def _outgoing(index: VaultIndex, path: Path) -> tuple[list[Path], list[str]]:
    resolved: list[Path] = []
    unresolved: list[str] = []
    for target in _linked_targets(path):
        hit = resolve_link(index, target)
        if hit is None:
            unresolved.append(target)
        elif hit != path:
            resolved.append(hit)
    return resolved, unresolved


def _backlinks(index: VaultIndex, path: Path) -> list[Path]:
    return [
        other
        for other in index.paths
        if other != path
        and any(resolve_link(index, target) == path for target in _linked_targets(other))
    ]


def _topics_of(path: Path) -> set[str]:
    properties, _ = read_frontmatter(path)
    topics = properties.get("topics", [])
    if isinstance(topics, list):
        return set(topics)
    return {topics} if topics else set()


def _topic_siblings(index: VaultIndex, path: Path) -> list[Path]:
    topics = _topics_of(path)
    if not topics:
        return []
    return [other for other in index.paths if other != path and topics & _topics_of(other)]
