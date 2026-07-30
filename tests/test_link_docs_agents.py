"""Prove the worktree hook repairs the gitignored `docs/agents` symlink.

Every case runs against a real scratch repo and a real `git worktree add` —
the defect being fixed is precisely that git does not materialize gitignored
paths in a new worktree, which no mock reproduces.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

HOOK = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "swe"
    / "hooks"
    / "link-docs-agents.sh"
)


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def run_hook(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(HOOK)], cwd=cwd, capture_output=True, text=True)


def build_repo(root: Path, *, ignore_docs_agents: bool = True) -> tuple[Path, Path]:
    """Return (main worktree, vault) for a repo laid out like this toolbox."""
    vault = root / "vault"
    (vault / "specs").mkdir(parents=True)
    (vault / "specs" / "0001-example.md").write_text("spec\n")

    main = root / "repo"
    main.mkdir()
    git(main, "init", "-q")
    git(main, "config", "user.email", "test@example.com")
    git(main, "config", "user.name", "Test")
    ignored = ["/.claude/"] + (["/docs/agents"] if ignore_docs_agents else [])
    (main / ".gitignore").write_text("\n".join(ignored) + "\n")
    (main / "README.md").write_text("scratch\n")
    git(main, "add", "-A")
    git(main, "commit", "-qm", "init")

    (main / "docs").mkdir()
    (main / "docs" / "agents").symlink_to(vault)
    return main, vault


def add_worktree(main: Path) -> Path:
    worktree = main / ".claude" / "worktrees" / "slice"
    git(main, "worktree", "add", "-q", "-b", "slice", str(worktree))
    return worktree


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    main, vault = build_repo(tmp_path.resolve())
    return main, vault, add_worktree(main)


def test_hook_links_docs_agents_in_a_real_worktree(
    repo: tuple[Path, Path, Path],
) -> None:
    main, vault, worktree = repo
    assert not (worktree / "docs" / "agents").exists()

    result = run_hook(worktree)

    assert result.returncode == 0
    link = worktree / "docs" / "agents"
    assert link.is_symlink()
    assert link.resolve() == vault.resolve()
    assert (link / "specs" / "0001-example.md").read_text() == "spec\n"
    assert (
        subprocess.run(
            ["git", "check-ignore", "-q", "docs/agents"], cwd=worktree
        ).returncode
        == 0
    )
    assert git(main, "status", "--porcelain") == ""


def test_hook_resolves_a_relative_symlink_target(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    main, vault = build_repo(root)
    (main / "docs" / "agents").unlink()
    (main / "docs" / "agents").symlink_to(Path("..") / ".." / "vault")
    worktree = add_worktree(main)

    result = run_hook(worktree)

    assert result.returncode == 0
    link = worktree / "docs" / "agents"
    raw_target = Path(link.readlink())
    assert raw_target.is_absolute()
    assert link.resolve() == vault.resolve()


def test_hook_is_idempotent_and_noops_in_main_worktree(
    repo: tuple[Path, Path, Path],
) -> None:
    main, vault, worktree = repo

    assert run_hook(worktree).returncode == 0
    first = (worktree / "docs" / "agents").readlink()
    assert run_hook(worktree).returncode == 0
    assert (worktree / "docs" / "agents").readlink() == first

    before = (main / "docs" / "agents").readlink()
    assert run_hook(main).returncode == 0
    assert (main / "docs" / "agents").readlink() == before


def test_hook_noops_when_main_worktree_has_no_docs_agents(tmp_path: Path) -> None:
    main, _vault = build_repo(tmp_path.resolve())
    (main / "docs" / "agents").unlink()
    worktree = add_worktree(main)

    result = run_hook(worktree)

    assert result.returncode == 0
    assert not (worktree / "docs").exists()


def test_hook_noops_outside_a_git_repo(tmp_path: Path) -> None:
    outside = tmp_path.resolve() / "not-a-repo"
    outside.mkdir()

    result = run_hook(outside)

    assert result.returncode == 0
    assert list(outside.iterdir()) == []


def test_hook_unlinks_a_non_gitignored_link_and_exits_zero(tmp_path: Path) -> None:
    main, _vault = build_repo(tmp_path.resolve(), ignore_docs_agents=False)
    worktree = add_worktree(main)

    result = run_hook(worktree)

    assert result.returncode == 0
    assert not (worktree / "docs" / "agents").is_symlink()
    assert "not gitignored" in result.stderr
