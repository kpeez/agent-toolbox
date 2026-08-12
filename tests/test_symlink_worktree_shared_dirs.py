"""Prove the worktree hook links shared local-resource dirs into a worktree.

Every case runs against a real scratch repo and a real `git worktree add` —
the defect being fixed is precisely that git does not materialize gitignored
paths in a new worktree, which no mock reproduces.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
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

ENTRIES = ("artifacts", "data", "docs/agents", "runs")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def run_hook(
    cwd: Path,
    *,
    stdin: str = "",
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the hook as the harness does. cwd is explicit: with empty stdin the
    script falls back to the process cwd, which must never be this repo."""
    return subprocess.run(
        [str(HOOK)],
        cwd=cwd,
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
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
    (main / "runs").mkdir()
    (main / "runs" / "run-1.log").write_text("loss=0\n")
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


def test_enter_worktree_payload_links_all_entries(repo: tuple[Path, Path]) -> None:
    main, worktree = repo
    payload = json.dumps({"tool_response": {"worktreePath": str(worktree)}})

    result = run_hook(main, stdin=payload)

    assert result.returncode == 0
    for entry in ENTRIES:
        link = worktree / entry
        assert link.is_symlink(), entry
        assert link.resolve() == (main / entry).resolve()
    assert (worktree / "artifacts" / "plot.png").read_text() == "png\n"
    assert (worktree / "docs" / "agents" / "spec.md").read_text() == "spec\n"
    assert git(worktree, "status", "--porcelain") == ""
    assert git(main, "status", "--porcelain") == ""


def test_session_start_in_worktree_links_via_cwd(repo: tuple[Path, Path]) -> None:
    main, worktree = repo

    assert run_hook(worktree, stdin=json.dumps({"cwd": str(worktree)})).returncode == 0
    assert (worktree / "data").is_symlink()

    for entry in ENTRIES:
        (worktree / entry).unlink()
    assert run_hook(worktree).returncode == 0  # no stdin: process-cwd fallback
    assert (worktree / "data").is_symlink()


def test_relative_docs_agents_target_resolves_through_the_chain(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    main = build_repo(root)
    (main / "docs" / "agents").unlink()
    (main / "docs" / "agents").symlink_to(Path("..") / ".." / "vault")
    worktree = add_worktree(main)

    assert run_hook(worktree).returncode == 0
    link = worktree / "docs" / "agents"
    assert link.resolve() == (root / "vault").resolve()
    assert (link / "spec.md").read_text() == "spec\n"


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


def test_hook_does_not_dereference_a_racing_destination(
    repo: tuple[Path, Path], tmp_path: Path
) -> None:
    main, worktree = repo
    real_ln = shutil.which("gln") or shutil.which("ln")
    assert real_ln is not None
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    shim = shim_dir / "ln"
    src = main / "data"
    dst = worktree / "data"
    shim.write_text(
        "#!/bin/sh\n"
        f"if [ \"$3\" = {shlex.quote(str(dst))} ]; then\n"
        f"  {shlex.quote(real_ln)} -s {shlex.quote(str(src))} \"$3\"\n"
        "fi\n"
        f"exec {shlex.quote(real_ln)} \"$@\"\n"
    )
    shim.chmod(0o755)
    env = os.environ | {"PATH": f"{shim_dir}:{os.environ['PATH']}"}

    result = run_hook(worktree, env=env)

    assert result.returncode == 0
    assert dst.is_symlink()
    assert sorted(path.name for path in src.iterdir()) == ["rows.csv"]


def test_hook_never_links_a_non_gitignored_entry(tmp_path: Path) -> None:
    main = build_repo(tmp_path.resolve(), ignored=("artifacts", "docs/agents"))
    worktree = add_worktree(main)

    result = run_hook(worktree)

    assert result.returncode == 0
    assert not (worktree / "data").exists()
    assert (worktree / "artifacts").is_symlink()
    assert git(worktree, "status", "--porcelain") == ""


def test_hook_noops_in_main_worktree_and_outside_git(tmp_path: Path) -> None:
    main = build_repo(tmp_path.resolve())

    assert run_hook(main).returncode == 0
    assert not (main / "artifacts").is_symlink()

    outside = tmp_path.resolve() / "not-a-repo"
    outside.mkdir()
    assert run_hook(outside).returncode == 0
    assert run_hook(outside, stdin="not json").returncode == 0
    assert list(outside.iterdir()) == []
