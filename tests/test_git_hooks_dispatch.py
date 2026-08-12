"""Prove the global git-hook dispatcher covers non-Claude worktree creation.

core.hooksPath replaces a repo's .git/hooks wholesale, so the dispatcher must
both link shared dirs on `git worktree add` (the reason it exists) and re-run
the repo's own hooks (pre-commit, git-lfs) it would otherwise hide. Every case
drives real git commands through a hooks dir laid out exactly as install.sh
lays it out: hook names symlinked to the dispatcher.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from test_symlink_worktree_shared_dirs import ENTRIES, add_worktree, build_repo, git

DISPATCH = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "swe"
    / "hooks"
    / "git-hooks-dispatch.sh"
)


@pytest.fixture
def repo_with_hookspath(tmp_path: Path) -> Path:
    main = build_repo(tmp_path.resolve())
    hooks_dir = tmp_path.resolve() / "global-hooks"
    hooks_dir.mkdir()
    for name in ("post-checkout", "pre-commit"):
        (hooks_dir / name).symlink_to(DISPATCH)
    git(main, "config", "core.hooksPath", str(hooks_dir))
    return main


def test_worktree_add_links_shared_dirs_without_any_claude_session(
    repo_with_hookspath: Path,
) -> None:
    main = repo_with_hookspath

    worktree = add_worktree(main)

    for entry in ENTRIES:
        link = worktree / entry
        assert link.is_symlink(), entry
        assert link.resolve() == (main / entry).resolve()
    assert git(worktree, "status", "--porcelain") == ""
    assert not (main / "artifacts").is_symlink()


def test_dispatcher_reruns_the_repo_local_hook_it_hides(
    repo_with_hookspath: Path,
) -> None:
    main = repo_with_hookspath
    marker = main / ".git" / "pre-commit-ran"
    local_hook = main / ".git" / "hooks" / "pre-commit"
    local_hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
    local_hook.chmod(0o755)

    (main / "README.md").write_text("changed\n")
    git(main, "commit", "-aqm", "change")

    assert marker.exists()


def test_dispatcher_propagates_a_failing_repo_local_hook(
    repo_with_hookspath: Path,
) -> None:
    main = repo_with_hookspath
    local_hook = main / ".git" / "hooks" / "pre-commit"
    local_hook.write_text("#!/bin/sh\nexit 1\n")
    local_hook.chmod(0o755)

    (main / "README.md").write_text("changed\n")
    result = subprocess.run(
        ["git", "commit", "-aqm", "change"], cwd=main, capture_output=True, text=True
    )

    assert result.returncode != 0
    assert git(main, "status", "--porcelain") != ""


def test_repo_local_post_checkout_runs_before_linking(
    repo_with_hookspath: Path,
) -> None:
    """git-lfs installs post-checkout in .git/hooks; both it and the linker
    must run on `git worktree add`."""
    main = repo_with_hookspath
    marker = main / ".git" / "post-checkout-ran"
    local_hook = main / ".git" / "hooks" / "post-checkout"
    local_hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
    local_hook.chmod(0o755)

    worktree = add_worktree(main)

    assert marker.exists()
    assert (worktree / "artifacts").is_symlink()


def test_branch_checkout_in_the_main_worktree_links_nothing(
    repo_with_hookspath: Path,
) -> None:
    main = repo_with_hookspath

    git(main, "checkout", "-qb", "feature")

    # main's own entries stay as build_repo made them: real dirs, plus the
    # docs/agents vault link — nothing rewritten to point at itself
    for entry in ("artifacts", "data", "runs"):
        assert (main / entry).is_dir() and not (main / entry).is_symlink(), entry
    assert (main / "docs" / "agents").resolve().name == "vault"
