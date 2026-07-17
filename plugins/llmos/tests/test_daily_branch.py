"""Prove daily_branch.py cascades branches the way the vault expects.

The catch-all is cut off main as a bare date; per-spec branches fork off the
catch-all as <agent>/<date>/<spec> and merge back into it, never straight to
main. The SessionStart hook tells every vault session this convention, so it
has to hold.

These tests were carved out of test_project_daily_logs.py, which housed both
the receipt writer's tests and these. ADR-0007 retired the receipt channel and
that file went with it -- but daily_branch.py stayed, so its tests live here
now, under a name that says what they cover.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BRANCH = PLUGIN_ROOT / "scripts/daily_branch.py"


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    )


def make_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    (root / "seed").write_text("seed\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "seed")


def run_branch(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BRANCH), *args, "--root", str(root)],
        capture_output=True,
        text=True,
    )


def current_branch(root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "branch", "--show-current"],
        capture_output=True,
        text=True,
    ).stdout.strip()


class CascadingBranchTests(unittest.TestCase):
    def test_start_from_main_creates_bare_date_catch_all(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_repo(root)
            result = run_branch(root, "start")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(current_branch(root), date.today().isoformat())

    def test_spec_forks_per_spec_branch_off_catch_all(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_repo(root)
            run_branch(root, "start")
            result = run_branch(
                root, "spec", "--agent", "claude", "--name", "Setup LLMOS"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            today = date.today().isoformat()
            self.assertEqual(current_branch(root), f"claude/{today}/setup-llmos")

    def test_start_leaves_todays_per_spec_branch_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_repo(root)
            run_branch(root, "start")
            run_branch(root, "spec", "--agent", "codex", "--name", "thing")
            today = date.today().isoformat()
            self.assertEqual(run_branch(root, "start").returncode, 0)
            self.assertEqual(current_branch(root), f"codex/{today}/thing")

    def test_spec_requires_catch_all_first(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_repo(root)
            result = run_branch(root, "spec", "--agent", "codex", "--name", "thing")
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
