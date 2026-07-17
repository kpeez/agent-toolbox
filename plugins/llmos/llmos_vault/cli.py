"""The `llmos-vault` cyclopts entry point. Every command here is a thin
wrapper: it resolves `--vault` to a root path, calls the framework-free
function that does the actual work, and prints JSON. Cyclopts renders each
command's `--help` straight from its docstring (ADR-0004 -- docstrings are
the single source of truth, no `Annotated` help duplication).
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from typing import Literal

import cyclopts

from llmos_vault.docs import write_reference
from llmos_vault.graph import get_neighbors, get_subgraph
from llmos_vault.health import summary, vault_health
from llmos_vault.mutations import (
    append_note,
    create_note,
    move_note,
    remove_property,
    set_property,
)
from llmos_vault.notes import list_notes, read_note
from llmos_vault.obsidian_cli import EXIT_OBSIDIAN_NOT_RUNNING, ObsidianNotRunning
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
def health(
    *,
    vault: Vault = "llmos",
    json: bool = False,
    qmd_collection: str = "llmos",
    stale_after_days: int = 14,
) -> None:
    """Report vault hygiene: orphans, dead-ends, unresolved wikilinks, schema
    violations, stale inbox items, and qmd index gaps.

    Use as the opening move of a vault-maintenance pass -- e.g. the nightly
    cron -- to see every hygiene defect in one headless call. Each section
    degrades independently: a missing qmd binary reports a notice instead of
    failing the whole command. Works with Obsidian closed. Exits 1 if any
    section has findings, 0 on a clean vault, so cron can branch on it.
    Do NOT use when you only need one relation on one note -- `neighbors` is
    cheaper and does not walk the whole vault.

    Example output:
        {"orphans": ["gamma"], "dead_ends": ["beta"],
         "unresolved_links": [{"referrer": "alpha", "target": "ghost"}],
         "schema_violations": [], "stale_inbox": [], "qmd_gaps": [],
         "qmd_notice": null}

    Example invocation:
        llmos-vault health --vault llmos --json

    Args:
        vault: Which registered vault to check. llmOS schema-violation
            checks run only when this is "llmos"; any other vault skips them.
        json: Emit machine-parseable JSON instead of a readable summary.
        qmd_collection: qmd collection name to check for index gaps.
        stale_after_days: Age in days after which an inbox item counts as stale.
    """
    import json as json_module

    report = vault_health(
        resolve_vault_root(vault),
        profile="llmos" if vault == "llmos" else "core",
        qmd_collection=qmd_collection,
        stale_after_days=stale_after_days,
    )
    if json:
        print(json_module.dumps(dataclasses.asdict(report), indent=2))
    else:
        print(summary(report))
    raise SystemExit(0 if report.is_clean else 1)


@app.command
def create(
    name: str, *, vault: Vault = "llmos", content: str | None = None, template: str | None = None
) -> None:
    """Create a new note, optionally from a vault template, via obsidian-cli.

    Use when an agent needs a brand-new note on disk with the app's own
    creation semantics (template expansion, conflict handling) -- e.g. filing
    a new project note. Requires Obsidian to be running.
    Do NOT use to overwrite an existing note's content -- obsidian-cli
    `create` refuses to clobber an existing file; edit it directly instead.

    Example output:
        Created: projects/agent-toolbox.md

    Example invocation:
        llmos-vault create projects/agent-toolbox --template project --vault llmos

    Args:
        name: Vault-relative note path (".md" appended if missing).
        vault: Which registered vault to create the note in.
        content: Initial body content.
        template: Name of a vault template to apply.
    """
    print(create_note(resolve_vault_root(vault), name, content=content, template=template))


@app.command
def move(note: str, to: str, *, vault: Vault = "llmos") -> None:
    """Move or rename a note via obsidian-cli, rewriting every backlink.

    Use when an agent needs to relocate or rename a note -- the sanctioned
    alternative to raw `mv`/`git mv` (ADR-0004; the PreToolUse Bash guard
    denies those inside a vault and points here). Requires Obsidian to be
    running.
    Do NOT use raw `mv`/`rm` on a vault note -- see the guard hook's message
    for why.

    Example output:
        Moved: notes/alpha.md -> archive/alpha.md

    Example invocation:
        llmos-vault move alpha archive/alpha.md --vault llmos

    Args:
        note: Note name (wikilink-style resolution) or vault-relative path.
        to: Destination folder or path.
        vault: Which registered vault the note lives in.
    """
    print(move_note(resolve_vault_root(vault), note, to))


@app.command
def append(note: str, content: str, *, vault: Vault = "llmos") -> None:
    """Append content to an existing note via obsidian-cli.

    Use when an agent needs to add content to the end of a note without
    reading and rewriting the whole file -- e.g. logging a quick note.
    Requires Obsidian to be running.
    Do NOT use for frontmatter changes -- use `set-property`.

    Example output:
        Appended to: notes/alpha.md

    Example invocation:
        llmos-vault append alpha "One more thought." --vault llmos

    Args:
        note: Note name (wikilink-style resolution) or vault-relative path.
        content: Content to append.
        vault: Which registered vault the note lives in.
    """
    print(append_note(resolve_vault_root(vault), note, content))


@app.command(name="set-property")
def property_set(note: str, key: str, value: str, *, vault: Vault = "llmos") -> None:
    """Set a property on a note via obsidian-cli.

    Use when an agent needs to set or update a single frontmatter property
    without hand-editing YAML -- e.g. flipping a status flag. Requires
    Obsidian to be running.
    `authors` is append-only: setting it merges `value` into the existing
    list instead of overwriting it.
    Do NOT use to rewrite `created` -- it is immutable and this call exits
    with an error.

    Example output:
        Set: status = active

    Example invocation:
        llmos-vault set-property alpha status active --vault llmos

    Args:
        note: Note name (wikilink-style resolution) or vault-relative path.
        key: Property name.
        value: Property value to set (or merge into `authors`).
        vault: Which registered vault the note lives in.
    """
    print(set_property(resolve_vault_root(vault), note, key, value))


@app.command(name="remove-property")
def property_remove(note: str, key: str, *, vault: Vault = "llmos") -> None:
    """Remove a property from a note via obsidian-cli.

    Use when an agent needs to delete a frontmatter property entirely --
    e.g. clearing a stale `status` flag. Requires Obsidian to be running.
    Do NOT use on `created` -- it is immutable and this call exits with an
    error.

    Example output:
        Removed: status

    Example invocation:
        llmos-vault remove-property alpha status --vault llmos

    Args:
        note: Note name (wikilink-style resolution) or vault-relative path.
        key: Property name to remove.
        vault: Which registered vault the note lives in.
    """
    print(remove_property(resolve_vault_root(vault), note, key))


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
    try:
        app()
    except ObsidianNotRunning as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(EXIT_OBSIDIAN_NOT_RUNNING)


if __name__ == "__main__":
    main()
