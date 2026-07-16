#!/usr/bin/env python3
"""Validate the agent-toolbox skill set for drift. Exit nonzero on any failure.

Checks:
  1. Every SKILL.md frontmatter `name:` matches its directory name.
  2. README skills table and the actual skill directories are in 1:1 agreement.
  3. Each plugin's Claude and Codex manifest versions match.
  4. No SKILL.md / README / AGENTS references a `/skill` that doesn't exist
     (and isn't a known host command).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
PLUGINS = ("knack", "lab")

# Host/harness commands referenced in prose that are not knack/lab skills.
EXTERNAL_COMMANDS = {
    "goal", "code-review", "review", "security-review", "run", "verify",
    "init", "loop", "schedule", "clear", "doctor", "model",
}

SKILL_REF = re.compile(r"`/([a-z][a-z0-9-]+)`")
README_ROW = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|")

failures: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def frontmatter_name(skill_md: Path) -> str | None:
    text = skill_md.read_text()
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else ""
    for line in block.splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
    return None


def skill_dirs() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for plugin in PLUGINS:
        base = ROOT / "plugins" / plugin / "skills"
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            if (d / "SKILL.md").is_file():
                found[d.name] = d
    return found


def check_name_matches_dir(dirs: dict[str, Path]) -> None:
    for name, d in dirs.items():
        fm = frontmatter_name(d / "SKILL.md")
        if fm != name:
            fail(f"name/dir mismatch: {d}/SKILL.md has name={fm!r}, dir is {name!r}")


def check_readme_inventory(dirs: dict[str, Path]) -> None:
    readme = (ROOT / "README.md").read_text().splitlines()
    listed = {m.group(1) for line in readme if (m := README_ROW.match(line))}
    for name in dirs:
        if name not in listed:
            fail(f"skill {name!r} exists but is missing from the README skills table")
    for name in listed:
        if name not in dirs:
            fail(f"README skills table lists {name!r} but no such skill directory exists")


def check_manifest_versions() -> None:
    for plugin in PLUGINS:
        claude = ROOT / "plugins" / plugin / ".claude-plugin" / "plugin.json"
        codex = ROOT / "plugins" / plugin / ".codex-plugin" / "plugin.json"
        if not (claude.is_file() and codex.is_file()):
            fail(f"{plugin}: missing a plugin manifest")
            continue
        cv = json.loads(claude.read_text()).get("version")
        xv = json.loads(codex.read_text()).get("version")
        if cv != xv:
            fail(f"{plugin}: version mismatch (claude={cv}, codex={xv})")


def check_skill_refs(dirs: dict[str, Path]) -> None:
    known = set(dirs) | EXTERNAL_COMMANDS
    targets = [ROOT / "README.md", ROOT / "AGENTS.md"]
    targets += sorted((ROOT / "plugins").rglob("*.md"))
    for md in targets:
        if "/specs/" in str(md):
            continue
        for ref in sorted(set(SKILL_REF.findall(md.read_text()))):
            if ref not in known:
                rel = md.relative_to(ROOT)
                fail(f"dead skill reference `/{ref}` in {rel}")


def main() -> int:
    if not (ROOT / "plugins").is_dir():
        print(f"FAIL: could not locate repo root from {ROOT}", file=sys.stderr)
        return 2
    dirs = skill_dirs()
    check_name_matches_dir(dirs)
    check_readme_inventory(dirs)
    check_manifest_versions()
    check_skill_refs(dirs)

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        print(f"\n{len(failures)} issue(s) found across {len(dirs)} skills.")
        return 1
    print(f"PASS: {len(dirs)} skills validated — no drift.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
