"""Keep plugin skills, manifests, documentation, and references in sync."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_REFERENCE = re.compile(r"`/([a-z][a-z0-9-]+)`")
README_ROW = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|")
ALLOWED_HOST_COMMANDS = {"goal", "code-review", "clear"}


def plugin_directories() -> list[Path]:
    return sorted(path for path in (ROOT / "plugins").iterdir() if path.is_dir())


def plugin_skill_files() -> list[Path]:
    return sorted(
        skill_file
        for plugin in plugin_directories()
        for skill_file in (plugin / "skills").glob("*/SKILL.md")
    )


def all_skill_files() -> list[Path]:
    return plugin_skill_files() + sorted((ROOT / "skills").glob("*/SKILL.md"))


def frontmatter_name(skill_file: Path) -> str | None:
    text = skill_file.read_text()
    match = re.match(r"^---\n(.*?)\n---(?:\n|$)", text, re.DOTALL)
    if match is None:
        return None
    name = re.search(r"^name:\s*(.+?)\s*$", match.group(1), re.MULTILINE)
    return name.group(1) if name else None


def readme_skill_names() -> set[str]:
    lines = (ROOT / "README.md").read_text().splitlines()
    section_start = next(
        index for index, line in enumerate(lines) if line == "## Skills"
    )
    section_end = next(
        (
            index
            for index in range(section_start + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    return {
        match.group(1)
        for line in lines[section_start:section_end]
        if (match := README_ROW.match(line))
    }


SWE_LOOP = ROOT / "plugins" / "swe" / "workflows" / "swe-loop.js"


def test_swe_loop_routes_worker_roles_through_the_roles_map() -> None:
    text = SWE_LOOP.read_text()

    routable = re.search(r"ROUTABLE_ROLES = \[([^\]]+)\]", text)
    assert routable is not None
    declared = set(re.findall(r"'([a-z-]+)'", routable.group(1)))
    routed = set(re.findall(r"agentTypeFor\('([a-z-]+)'\)", text))
    assert routed == declared == {"planner", "implementer", "reviewer", "publisher"}

    # A hardcoded agentType in any quoting style would bypass the roles arg.
    assert re.findall(r"agentType:\s*['\"`]swe:", text) == []


def test_swe_loop_stays_tracker_agnostic() -> None:
    # Tracker mechanics live in the to-issues tracker references
    # (references/issue-tracker-*.md); the loop's runner skill and conductor
    # dispatch through them at runtime and never name a tracker themselves.
    start_loop = ROOT / "plugins" / "swe" / "skills" / "start-loop" / "SKILL.md"
    offenders = [
        (path.name, match)
        for path in (SWE_LOOP, start_loop)
        for match in re.findall(r"linear|github", path.read_text(), re.IGNORECASE)
    ]

    assert offenders == []


def test_swe_hooks_register_worktree_link_script() -> None:
    hooks = json.loads((ROOT / "plugins" / "swe" / "hooks" / "hooks.json").read_text())
    command = '"$CLAUDE_PLUGIN_ROOT"/hooks/symlink-worktree-shared-dirs.sh'

    subagent = hooks["hooks"]["SubagentStart"]
    assert [entry.get("matcher") for entry in subagent] == [None]
    assert [hook["command"] for entry in subagent for hook in entry["hooks"]] == [
        command
    ]

    session = hooks["hooks"]["SessionStart"]
    assert [entry["matcher"] for entry in session] == ["startup|resume"]
    assert [hook["command"] for entry in session for hook in entry["hooks"]] == [
        command
    ]

    post_tool = hooks["hooks"]["PostToolUse"]
    enter_worktree = [
        entry for entry in post_tool if entry.get("matcher") == "EnterWorktree"
    ]
    assert [
        hook["command"] for entry in enter_worktree for hook in entry["hooks"]
    ] == [command]

    script = ROOT / "plugins" / "swe" / "hooks" / "symlink-worktree-shared-dirs.sh"
    assert script.is_file()
    assert script.stat().st_mode & 0o111


def test_frontmatter_names_match_skill_directories() -> None:
    mismatches = [
        (
            skill_file.relative_to(ROOT),
            frontmatter_name(skill_file),
            skill_file.parent.name,
        )
        for skill_file in all_skill_files()
        if frontmatter_name(skill_file) != skill_file.parent.name
    ]

    assert mismatches == []


def test_plugin_manifest_versions_match() -> None:
    mismatches: list[tuple[str, str | None, str | None]] = []

    for plugin in plugin_directories():
        claude_manifest = plugin / ".claude-plugin" / "plugin.json"
        codex_manifest = plugin / ".codex-plugin" / "plugin.json"
        claude_version = (
            json.loads(claude_manifest.read_text()).get("version")
            if claude_manifest.is_file()
            else None
        )
        codex_version = (
            json.loads(codex_manifest.read_text()).get("version")
            if codex_manifest.is_file()
            else None
        )
        if claude_version != codex_version or claude_version is None:
            mismatches.append((plugin.name, claude_version, codex_version))

    assert mismatches == []


def test_readme_skills_table_matches_plugin_skills() -> None:
    expected = {skill_file.parent.name for skill_file in plugin_skill_files()}

    assert readme_skill_names() == expected


def test_backtick_skill_references_are_live() -> None:
    known_skills = {
        skill_file.parent.name for skill_file in all_skill_files()
    } | ALLOWED_HOST_COMMANDS
    targets = [ROOT / "README.md", ROOT / "AGENTS.md"]
    targets.extend(sorted((ROOT / "plugins").rglob("*.md")))
    dead_references = [
        (markdown.relative_to(ROOT), reference)
        for markdown in targets
        for reference in sorted(set(SKILL_REFERENCE.findall(markdown.read_text())))
        if reference not in known_skills
    ]

    assert dead_references == []
