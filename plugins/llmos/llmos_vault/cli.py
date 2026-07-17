"""The `llmos-vault` cyclopts entry point. Every command here is a thin
wrapper: it resolves `--vault` to a root path, calls the framework-free
function that does the actual work, and prints JSON. Cyclopts renders each
command's `--help` straight from its docstring (ADR-0004 -- docstrings are
the single source of truth, no `Annotated` help duplication).
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Literal

import cyclopts

from llmos_vault.docs import write_reference
from llmos_vault.graph import get_neighbors, get_subgraph
from llmos_vault.notes import list_notes, read_note
from llmos_vault.root import resolve_vault_root

Vault = Literal["llmos", "xbrain"]

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REFERENCE_PATH = PLUGIN_ROOT / "skills" / "vault-cli" / "references" / "commands.md"
DEFAULT_SKILL_PATH = PLUGIN_ROOT / "skills" / "vault-cli" / "SKILL.md"

app = cyclopts.App(
    name="llmos-vault",
    help="Headless read and link-graph verbs for the llmOS and xbrain vaults.",
)


@app.command
def read(note: str, *, vault: Vault = "llmos") -> None:
    """Print one note's frontmatter and body as JSON.

    Use when an agent needs a note's current content or properties -- to
    inspect before editing, or to script a decision on a property value.
    Works with Obsidian closed.
    Do NOT use when you need every note in the vault -- use `list`, it walks
    the tree once instead of resolving names one at a time.

    Example output:
        {"name": "alpha", "path": "/vault/notes/alpha.md",
         "properties": {"topics": ["gardening"]}, "body": "# Alpha\\n..."}

    Example invocation:
        llmos-vault read alpha --vault llmos

    Args:
        note: Note basename (wikilink-style) or vault-relative path.
        vault: Which registered vault to read from.
    """
    note_obj = read_note(resolve_vault_root(vault), note)
    print(
        json.dumps(
            {
                "name": note_obj.name,
                "path": str(note_obj.path),
                "properties": note_obj.properties,
                "body": note_obj.body,
            },
            indent=2,
        )
    )


@app.command(name="list")
def list_(*, vault: Vault = "llmos") -> None:
    """Print every note in the vault with its frontmatter and body as JSON.

    Use when an agent needs to enumerate or scan all notes -- e.g. finding
    every note missing a property before scripting a bulk decision.
    Do NOT use when you already know which note you want -- use `read`, it
    skips parsing the rest of the vault.

    Example output:
        [{"name": "alpha", "path": "/vault/notes/alpha.md",
          "properties": {"topics": ["gardening"]}, "body": "# Alpha\\n..."}]

    Example invocation:
        llmos-vault list --vault llmos

    Args:
        vault: Which registered vault to enumerate.
    """
    notes = list_notes(resolve_vault_root(vault))
    print(
        json.dumps(
            [
                {
                    "name": n.name,
                    "path": str(n.path),
                    "properties": n.properties,
                    "body": n.body,
                }
                for n in notes
            ],
            indent=2,
        )
    )


@app.command
def neighbors(note: str, *, vault: Vault = "llmos") -> None:
    """Print one note's outgoing links, backlinks, and shared-topic siblings.

    Use when an agent needs a note's local link neighborhood -- e.g. before
    editing a note, to see what already points at it or shares its topics.
    Works with Obsidian closed; the graph is built fresh from disk.
    Do NOT use when you need more than one hop out -- use `subgraph`.

    Example output:
        {"note": "alpha", "outgoing": ["beta"], "unresolved_outgoing": ["ghost"],
         "backlinks": ["delta"], "topic_siblings": ["beta", "gamma"]}

    Example invocation:
        llmos-vault neighbors alpha --vault llmos

    Args:
        note: Note basename (wikilink-style) or vault-relative path.
        vault: Which registered vault to read from.
    """
    print(json.dumps(dataclasses.asdict(get_neighbors(resolve_vault_root(vault), note)), indent=2))


@app.command
def subgraph(note: str, *, vault: Vault = "llmos", depth: int = 1) -> None:
    """Print the transitive neighborhood of a note out to `depth` hops as JSON.

    Use when an agent needs the broader cluster around a note -- e.g. to
    scope a rename's blast radius, or to see a topic's full note cluster.
    Unresolved wikilinks are listed, never raised as errors.
    Do NOT use when you only need the immediate neighbors -- `neighbors` is
    cheaper and returns the same one-hop data without traversal.

    Example output:
        {"root": "alpha", "nodes": ["alpha", "beta", "delta", "gamma"],
         "unresolved": ["ghost"],
         "edges": [["alpha", "beta", "link"], ["delta", "alpha", "link"]]}

    Example invocation:
        llmos-vault subgraph alpha --vault llmos --depth 2

    Args:
        note: Note basename (wikilink-style) or vault-relative path.
        vault: Which registered vault to read from.
        depth: Number of hops to traverse outward from the note.
    """
    print(
        json.dumps(
            dataclasses.asdict(get_subgraph(resolve_vault_root(vault), note, depth=depth)),
            indent=2,
        )
    )


@app.command
def docs(
    *,
    reference: Path = DEFAULT_REFERENCE_PATH,
    skill: Path = DEFAULT_SKILL_PATH,
) -> None:
    """Regenerate the router skill's command reference from this CLI's tree.

    Use when a command's docstring changes or a new verb is registered --
    run this so `references/commands.md` and the skill's verb table match
    the live command tree before committing; the staleness test regenerates
    to a temp file and diffs to enforce this automatically.
    Do NOT use when you only want to preview the output without writing it
    -- call `llmos_vault.docs.render_reference(app)` directly.

    Example output:
        wrote plugins/llmos/skills/vault-cli/references/commands.md

    Example invocation:
        llmos-vault docs

    Args:
        reference: Path to write the full command reference to.
        skill: Path to the router skill's SKILL.md, whose verb table gets
            replaced in place.
    """
    write_reference(app, reference, skill)
    print(f"wrote {reference}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
