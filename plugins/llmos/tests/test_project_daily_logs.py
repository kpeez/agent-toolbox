from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
WRITER = PLUGIN_ROOT / "scripts/write_daily_receipt.py"
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


class ReceiptWriterTests(unittest.TestCase):
    def _vault(self, base: Path, slug: str = "alpha", title: str = "Alpha") -> Path:
        landing = base / "projects" / slug / f"{slug}.md"
        landing.parent.mkdir(parents=True)
        landing.write_text(f"---\nstatus: active\n---\n\n# {title}\n", encoding="utf-8")
        return base

    def test_receipt_has_desc_and_info_and_names_agent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._vault(Path(directory))
            result = subprocess.run(
                [
                    sys.executable,
                    str(WRITER),
                    "--agent",
                    "claude",
                    "--receipt-id",
                    "alpha-spec",
                    "--desc",
                    "does the thing",
                    "--info",
                    "[[SPEC-alpha]]",
                    "--info",
                    "PR #7",
                    "--project",
                    "alpha",
                    "--date",
                    "2099-01-02",
                    "--root",
                    str(root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            log = (root / "projects/alpha/logs/2099-01-02-alpha.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("### ", log)
            self.assertIn("| claude", log)
            self.assertIn("<!-- llmos-receipt:claude:alpha-spec:alpha -->", log)
            self.assertIn("- desc: does the thing", log)
            self.assertIn("- info: [[SPEC-alpha]], PR #7", log)
            self.assertIn('categories:\n  - "[[Project Logs]]"', log)
            self.assertIn('project:\n  - "[[projects/alpha/alpha|Alpha]]"', log)

    def test_rerun_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._vault(Path(directory))
            command = [
                sys.executable,
                str(WRITER),
                "--agent",
                "codex",
                "--receipt-id",
                "dup",
                "--desc",
                "x",
                "--project",
                "alpha",
                "--date",
                "2099-01-02",
                "--root",
                str(root),
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
            subprocess.run(command, check=True, capture_output=True, text=True)
            log = (root / "projects/alpha/logs/2099-01-02-alpha.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(log.count("<!-- llmos-receipt:codex:dup:alpha -->"), 1)

    def test_project_inferred_from_working_repo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = self._vault(base / "vault")
            repo = base / "alpha"
            make_repo(repo)
            result = subprocess.run(
                [
                    sys.executable,
                    str(WRITER),
                    "--agent",
                    "gemini",
                    "--receipt-id",
                    "inferred",
                    "--desc",
                    "auto",
                    "--date",
                    "2099-01-02",
                    "--root",
                    str(root),
                ],
                cwd=repo,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / "projects/alpha/logs/2099-01-02-alpha.md").exists())

    def test_fails_when_project_cannot_be_inferred(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "vault"
            root.mkdir()
            not_repo = base / "nope"
            not_repo.mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    str(WRITER),
                    "--agent",
                    "codex",
                    "--receipt-id",
                    "x",
                    "--desc",
                    "x",
                    "--date",
                    "2099-01-02",
                    "--root",
                    str(root),
                ],
                cwd=not_repo,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Failed to infer project", result.stderr)


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
