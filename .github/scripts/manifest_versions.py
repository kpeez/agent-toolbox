#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Fail when a plugin manifest or a catalog entry sets "version".

Claude Code keys plugin updates on that string. Without it, Claude Code uses
the marketplace commit SHA, so every commit to main is an update.
"""

import json
import sys
from pathlib import Path

MANIFESTS = (
    "plugins/*/plugin.json",
    "plugins/*/.claude-plugin/plugin.json",
    "plugins/*/.codex-plugin/plugin.json",
    "plugins/*/.antigravity-plugin/plugin.json",
    "claude-mods/*/.claude-plugin/plugin.json",
)
CATALOGS = (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json")
WHY = (
    "Without it, Claude Code updates on each commit; a hand-set version ships"
    " new content under an old version."
)


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    errors = []
    for pattern in MANIFESTS:
        for path in sorted(root.glob(pattern)):
            if "version" in json.loads(path.read_text()):
                errors.append(f'{path.relative_to(root)} sets "version"; delete it.')
    for rel in CATALOGS:
        path = root / rel
        if not path.exists():
            continue
        for entry in json.loads(path.read_text()).get("plugins", []):
            if "version" in entry:
                errors.append(
                    f'{rel} entry "{entry.get("name")}" sets "version"; delete it.'
                )
    for error in errors:
        print(f"{error} {WHY}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
