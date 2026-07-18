#!/usr/bin/env python3
"""Generate both marketplace catalogs from the plugins/ directory on disk.

The two files are hand-read by different harnesses -- Claude reads
`.claude-plugin/marketplace.json`, Codex reads `.agents/plugins/marketplace.json`
(falling back to the Claude file only when the .agents one is absent). They
carry the same plugin roster in different schemas, so hand-maintaining both is
how they drift: a plugin listed in one and missing from the other silently
breaks install on that harness.

So the roster is DERIVED here, never hand-written. A plugin *is* a
`plugins/<name>/` dir with a `.claude-plugin/plugin.json`; add or remove a dir
and both catalogs follow on the next run. The only hand-maintained inputs are
the repo-level header and the per-plugin defaults below -- constants today
because every plugin shares them. If a plugin ever needs its own category or
policy, add the field to its `plugin.json` and read it here, keeping
`plugin.json` the single source of truth.

Run `python scripts/gen-marketplaces.py`, then commit the result. CI regenerates
and fails on any diff (`git diff --exit-code`), so drift cannot be committed.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_DIR = REPO_ROOT / "plugins"
CLAUDE_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
AGENTS_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"

# --- Hand-maintained inputs (the only facts not derived from plugins/) --------
MARKETPLACE_NAME = "agent-toolbox"
DESCRIPTION = (
    "Portable skills, agents, and spec-driven workflow for AI coding agents, "
    "split into installable plugins"
)
OWNER = {"name": "Kyle Puhger", "email": "krpuhger@gmail.com"}
DEFAULT_POLICY = {"installation": "AVAILABLE", "authentication": "ON_USE"}
DEFAULT_CATEGORY = "Productivity"


def plugin_names() -> list[str]:
    names = [
        json.loads((d / ".claude-plugin" / "plugin.json").read_text())["name"]
        for d in PLUGINS_DIR.iterdir()
        if (d / ".claude-plugin" / "plugin.json").is_file()
    ]
    if not names:
        raise SystemExit(f"no plugins found under {PLUGINS_DIR}")
    return sorted(names)


def claude_catalog(names: list[str]) -> dict:
    return {
        "name": MARKETPLACE_NAME,
        "description": DESCRIPTION,
        "owner": OWNER,
        "plugins": [{"name": n, "source": f"./plugins/{n}"} for n in names],
    }


def agents_catalog(names: list[str]) -> dict:
    return {
        "name": MARKETPLACE_NAME,
        "interface": {"displayName": MARKETPLACE_NAME},
        "plugins": [
            {
                "name": n,
                "source": {"source": "local", "path": f"./plugins/{n}"},
                "policy": DEFAULT_POLICY,
                "category": DEFAULT_CATEGORY,
            }
            for n in names
        ],
    }


def write(path: Path, catalog: dict) -> None:
    path.write_text(json.dumps(catalog, indent=2) + "\n")
    print(f"wrote {path.relative_to(REPO_ROOT)} ({len(catalog['plugins'])} plugins)")


def main() -> None:
    names = plugin_names()
    write(CLAUDE_MARKETPLACE, claude_catalog(names))
    write(AGENTS_MARKETPLACE, agents_catalog(names))


if __name__ == "__main__":
    main()
