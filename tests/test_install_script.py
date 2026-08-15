"""install.sh must register plugin skills where opencode will find them."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts" / "install.sh"


def plugin_skill_dirs() -> list[Path]:
    return sorted(
        skill_file.parent
        for skill_file in (ROOT / "plugins").glob("*/skills/*/SKILL.md")
    )


def run_install(home: Path) -> None:
    """Run the installer against a throwaway HOME. Every path it writes is
    under $HOME, so this exercises the real script without touching the box."""
    result = subprocess.run(
        ["bash", str(INSTALL)],
        env={"HOME": str(home), "PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    return home


def test_every_plugin_skill_is_linked_into_the_opencode_scan_path(home: Path) -> None:
    """opencode reads ~/.agents/skills/**/SKILL.md and follows symlinks, but
    cannot read the Claude Code plugin marketplace that delivers these skills."""
    run_install(home)

    linked = home / ".agents" / "skills"
    sources = plugin_skill_dirs()
    assert sources, "no plugin skills found to link"

    for source in sources:
        entry = linked / source.name
        assert entry.is_symlink(), f"{source.name} is not linked into ~/.agents/skills"
        assert entry.resolve() == source
        assert (entry / "SKILL.md").is_file()


def test_install_leaves_skills_owned_by_other_installers_alone(home: Path) -> None:
    """`npx skills` installs into this same tree and tracks what it owns in
    .skill-lock.json, so the installer must replace its own links by name
    rather than wiping the directory."""
    foreign = home / ".agents" / "skills" / "from-npx"
    foreign.mkdir(parents=True)
    (foreign / "SKILL.md").write_text("---\nname: from-npx\ndescription: x\n---\n")
    lock = home / ".agents" / ".skill-lock.json"
    lock.write_text('{"version": 3, "skills": {}}\n')

    run_install(home)

    assert (foreign / "SKILL.md").is_file()
    assert lock.read_text() == '{"version": 3, "skills": {}}\n'


def test_install_updates_codex_global_instructions(home: Path) -> None:
    instructions = home / ".codex" / "AGENTS.md"
    instructions.parent.mkdir(parents=True)
    instructions.write_text("stale\n")

    run_install(home)

    assert instructions.read_bytes() == (ROOT / "AGENTS.md").read_bytes()


def test_install_repairs_a_link_left_dangling_by_a_deleted_source(home: Path) -> None:
    """A stale ~/.agents/skills/maintain-llmos pointing into the removed llmOS
    tree is silently skipped by opencode; re-running must heal it."""
    linked = home / ".agents" / "skills"
    linked.mkdir(parents=True)
    (linked / "maintain-llmos").symlink_to(home / "gone" / "maintain-llmos")
    assert not (linked / "maintain-llmos").exists()

    run_install(home)

    entry = linked / "maintain-llmos"
    assert entry.is_symlink()
    assert (entry / "SKILL.md").is_file()


def global_hooks_path(home: Path) -> str:
    return subprocess.run(
        ["git", "config", "--global", "core.hooksPath"],
        env={"HOME": str(home), "PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_install_wires_the_global_git_hooks_dispatcher(home: Path) -> None:
    """Codex and plain `git worktree add` load no plugin hooks, so worktree
    linking must ride a global git post-checkout hook."""
    run_install(home)

    hooks_dir = home / ".config" / "git" / "hooks"
    dispatch = ROOT / "plugins" / "swe" / "hooks" / "git-hooks-dispatch.sh"
    for name in ("post-checkout", "pre-commit", "pre-push"):
        link = hooks_dir / name
        assert link.is_symlink(), name
        assert link.resolve() == dispatch
    assert global_hooks_path(home) == str(hooks_dir)


def test_install_keeps_a_foreign_core_hookspath(home: Path) -> None:
    """A hooksPath the user set themselves must never be clobbered."""
    (home / ".gitconfig").write_text("[core]\n\thooksPath = /somewhere/else\n")

    run_install(home)

    assert global_hooks_path(home) == "/somewhere/else"


def test_install_is_idempotent(home: Path) -> None:
    run_install(home)
    before = sorted(path.name for path in (home / ".agents" / "skills").iterdir())

    run_install(home)

    assert (
        sorted(path.name for path in (home / ".agents" / "skills").iterdir()) == before
    )
