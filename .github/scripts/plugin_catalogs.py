#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Fail when a marketplace catalog and the plugin folders disagree.

- The Claude catalog lists every folder in plugins/ and claude-mods/.
- The Codex catalog lists every folder in plugins/, and nothing else.
- Each entry points at a folder whose manifest for that host has the
  entry's name.
- All manifests of one plugin have the same name.
"""

import json
import sys
from pathlib import Path

CATALOGS = {
    ".claude-plugin/marketplace.json": (
        ".claude-plugin/plugin.json",
        ["plugins", "claude-mods"],
    ),
    ".agents/plugins/marketplace.json": (".codex-plugin/plugin.json", ["plugins"]),
}
MANIFESTS = [".claude-plugin", ".codex-plugin", ".antigravity-plugin", "."]


def plugin_folders(*roots: str) -> list[Path]:
    return sorted(p for root in roots for p in Path().glob(f"{root}/*") if p.is_dir())


errors = []
for catalog, (manifest, roots) in CATALOGS.items():
    listed = {}
    for entry in json.loads(Path(catalog).read_text())["plugins"]:
        source = (
            entry["source"]
            if isinstance(entry["source"], str)
            else entry["source"]["path"]
        )
        folder = Path(source).as_posix()
        listed[folder] = entry["name"]
        path = Path(folder, manifest)
        if not path.is_file():
            errors.append(
                f"{catalog}: {entry['name']} points at {folder}, which has no {manifest}"
            )
        elif (name := json.loads(path.read_text()).get("name")) != entry["name"]:
            errors.append(f"{catalog}: entry {entry['name']} names {path} '{name}'")
    folders = {p.as_posix() for p in plugin_folders(*roots)}
    for folder in sorted(folders - listed.keys()):
        errors.append(f"{catalog}: add an entry for {folder}")
    for folder in sorted(listed.keys() - folders):
        errors.append(
            f"{catalog}: remove the entry for {folder}, which is not under {' or '.join(roots)}/"
        )

for plugin in plugin_folders("plugins", "claude-mods"):
    names = {
        f"{d}/plugin.json": json.loads(m.read_text()).get("name")
        for d in MANIFESTS
        if (m := plugin / d / "plugin.json").is_file()
    }
    if len(set(names.values())) > 1:
        errors.append(f"{plugin}: manifests disagree on name: {names}")

print("\n".join(errors) or "Catalogs and plugin manifests agree.")
sys.exit(1 if errors else 0)
