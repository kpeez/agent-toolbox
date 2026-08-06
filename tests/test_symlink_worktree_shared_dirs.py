"""Prove the EnterWorktree hook links shared local-resource dirs into a worktree.

Every case runs against a real scratch repo and a real `git worktree add` —
the defect being fixed is precisely that git does not materialize gitignored
paths in a new worktree, which no mock reproduces.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

HOOK = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "swe"
    / "hooks"
    / "symlink-worktree-shared-dirs.sh"
)

ENTRIES = ("artifacts", "data", "docs/agents")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def run_hook(worktree: Path, *, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    payload = (
        stdin
        if stdin is not None
        else json.dumps({"tool_response": {"worktreePath": str(worktree)}})
    )
    return subprocess.run(
        [str(HOOK)], input=payload, capture_output=True, text=True
    )


def build_repo(root: Path, *, ignored: tuple[str, ...] = ENTRIES) -> Path:
    """Return the main worktree of a repo laid out like this toolbox."""
    main = root / "repo"
    main.mkdir()
    git(main, "init", "-q")
    git(main, "config", "user.email", "test@example.com")
    git(main, "config", "user.name", "Test")
    lines = ["/.claude/"] + [f"/{entry}" for entry in ignored]
    (main / ".gitignore").write_text("\n".join(lines) + "\n")
    (main / "README.md").write_text("scratch\n")
    git(main, "add", "-A")
    git(main, "commit", "-qm", "init")

    (main / "artifacts").mkdir()
    (main / "artifacts" / "plot.png").write_text("png\n")
    (main / "data").mkdir()
    (main / "data" / "rows.csv").write_text("a,b\n")
    vault = root / "vault"
    vault.mkdir()
    (vault / "spec.md").write_text("spec\n")
    (main / "docs").mkdir()
    (main / "docs" / "agents").symlink_to(vault)
    return main


def add_worktree(main: Path) -> Path:
    worktree = main / ".claude" / "worktrees" / "slice"
    git(main, "worktree", "add", "-q", "-b", "slice", str(worktree))
    return worktree


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, Path]:
    main = build_repo(tmp_path.resolve())
    return main, add_worktree(main)


def test_hook_links_all_entries_in_a_real_worktree(repo: tuple[Path, Path]) -> None:
    main, worktree = repo

    result = run_hook(worktree)

    assert result.returncode == 0
    for entry in ENTRIES:
        link = worktree / entry
        assert link.is_symlink(), entry
        assert link.resolve() == (main / entry).resolve()
    assert (worktree / "artifacts" / "plot.png").read_text() == "png\n"
    assert (worktree / "docs" / "agents" / "spec.md").read_text() == "spec\n"
    assert git(worktree, "status", "--porcelain") == ""
    assert git(main, "status", "--porcelain") == ""


def test_hook_falls_back_to_cwd_field(repo: tuple[Path, Path]) -> None:
    _main, worktree = repo

    result = run_hook(worktree, stdin=json.dumps({"cwd": str(worktree)}))

    assert result.returncode == 0
    assert (worktree / "data").is_symlink()


def test_hook_skips_missing_and_existing_entries(repo: tuple[Path, Path]) -> None:
    main, worktree = repo
    (main / "data" / "rows.csv").unlink()
    (main / "data").rmdir()
    (worktree / "artifacts").mkdir()

    result = run_hook(worktree)

    assert result.returncode == 0
    assert not (worktree / "data").exists()
    assert not (worktree / "artifacts").is_symlink()
    assert (worktree / "docs" / "agents").is_symlink()
    assert run_hook(worktree).returncode == 0  # idempotent


def test_hook_never_links_a_non_gitignored_entry(tmp_path: Path) -> None:
    main = build_repo(tmp_path.resolve(), ignored=("artifacts", "docs/agents"))
    worktree = add_worktree(main)

    result = run_hook(worktree)

    assert result.returncode == 0
    assert not (worktree / "data").exists()
    assert (worktree / "artifacts").is_symlink()
    assert git(worktree, "status", "--porcelain") == ""


def test_hook_noops_outside_a_managed_worktree(repo: tuple[Path, Path]) -> None:
    main, worktree = repo

    assert run_hook(main).returncode == 0
    assert not (main / "artifacts").is_symlink()

    assert run_hook(worktree, stdin="").returncode == 0
    assert run_hook(worktree, stdin="not json").returncode == 0
    assert not (worktree / "artifacts").exists()
