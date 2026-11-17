"""Tests for pr_body.py hook command matching, gh-stack enforcement, and attribution checks."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "pr_body.py"
SPEC = importlib.util.spec_from_file_location("swe_ship_pr_body", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
pr_body = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pr_body
SPEC.loader.exec_module(pr_body)


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(root: Path, *, origin_head: str | None = "main", gh_stack: bool = False) -> Path:
    repo = root / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    if origin_head is not None:
        head_sha = _git(repo, "rev-parse", "HEAD")
        _git(repo, "update-ref", f"refs/remotes/origin/{origin_head}", head_sha)
        _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", f"refs/remotes/origin/{origin_head}")
    if gh_stack:
        (repo / ".git" / "gh-stack").write_text("", encoding="utf-8")
    return repo


def _render_valid_body(folder: Path) -> Path:
    slots = folder / "slots"
    slots.mkdir(exist_ok=True)
    (slots / "summary.md").write_text("Each save rewrites the whole cache.\n", encoding="utf-8")
    (slots / "evidence.md").write_text("Before: 4 s. After: 0.2 s.\n", encoding="utf-8")
    (slots / "reversible.md").write_text("yes\n", encoding="utf-8")
    (slots / "blast_radius.md").write_text("local\n", encoding="utf-8")
    body, errors = pr_body.render(str(slots), None)
    assert body is not None and not errors, errors
    body_path = folder / "body.md"
    body_path.write_text(body, encoding="utf-8")
    return body_path


def _run_hook(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    event = {"tool_input": {"command": command}, "cwd": str(cwd)}
    return subprocess.run(
        [sys.executable, str(SCRIPT), "hook"],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )


class CommandMatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.body = _render_valid_body(self.root)

    def test_ignores_mentions_in_arguments_and_other_commands(self):
        for cmd in [
            'rg -l -i "gh pr create" docs',
            'echo "gh pr create --body inline"',
            'git commit -m "gh pr create --base feature"',
            'gh pr edit 12 --title "New title"',
            f"gh pr edit 12 --body-file {self.body.name}",
            "gh stack link feat-a feat-b",
            "gh stack submit --auto",
        ]:
            with self.subTest(cmd=cmd):
                res = _run_hook(cmd, self.root)
                self.assertEqual(res.returncode, 0, res.stderr)

    def test_matches_real_invocations_across_shell_separators(self):
        for cmd in [
            'gh pr create --body "inline"',
            'cd . && gh pr create --body "inline"',
            'true || gh pr create --body "inline"',
            'echo ok; gh pr create --body "inline"',
            'echo ok\ngh pr create --body "inline"',
            'gh pr create --body "inline" | cat',
            'FOO=1 gh pr create --body "inline"',
            'gh pr edit 12 --body "inline"',
            'url=$(gh pr create --body "inline")',
            'url=`gh pr create --body "inline"`',
            'time gh pr create --body "inline"',
            '(cd . && gh pr create --body "inline")',
            'env gh pr create --body "inline"',
            '{ gh pr create --body "inline"; }',
            '/usr/local/bin/gh pr create --body "inline"',
            'gh pr create --body "inline" &',
            'gh pr create -b"inline"',
        ]:
            with self.subTest(cmd=cmd):
                res = _run_hook(cmd, self.root)
                self.assertEqual(res.returncode, 2, f"expected block for {cmd!r}, got {res.returncode}")

    def test_newline_inside_quotes_does_not_split_segment(self):
        res = _run_hook('echo "line1\ngh pr create --body inline"', self.root)
        self.assertEqual(res.returncode, 0, res.stderr)


class StackBaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_allows_non_trunk_base_without_gh_stack_file(self):
        repo = _init_repo(self.root, origin_head="main", gh_stack=False)
        body = _render_valid_body(repo)
        res = _run_hook(f"gh pr create --draft --base feature-a --body-file {body.name}", repo)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_blocks_non_trunk_base_with_gh_stack_file(self):
        repo = _init_repo(self.root, origin_head="main", gh_stack=True)
        body = _render_valid_body(repo)
        for flag in [
            "--base feature-a",
            "--base=feature-a",
            "-B feature-a",
            "-B=feature-a",
            "-Bfeature-a",
        ]:
            with self.subTest(flag=flag):
                res = _run_hook(f"gh pr create --draft {flag} --body-file {body.name}", repo)
                self.assertEqual(res.returncode, 2)
                self.assertIn("gh stack link", res.stderr)
                self.assertIn("gh stack submit", res.stderr)

    def test_allows_trunk_and_omitted_base_with_gh_stack_file(self):
        repo = _init_repo(self.root, origin_head="main", gh_stack=True)
        body = _render_valid_body(repo)
        for args in [
            f"--draft --base main --body-file {body.name}",
            f"--draft -B main --body-file {body.name}",
            f"--draft --body-file {body.name}",
            f"--draft -F{body.name}",
            "gh stack link feat-a feat-b",
            "gh stack submit --auto",
        ]:
            cmd = args if args.startswith("gh ") else f"gh pr create {args}"
            with self.subTest(cmd=cmd):
                start = time.monotonic()
                res = _run_hook(cmd, repo)
                elapsed = time.monotonic() - start
                self.assertEqual(res.returncode, 0, res.stderr)
                self.assertLess(elapsed, 1.0)

    def test_blocks_edit_retarget_to_non_trunk_with_gh_stack_file(self):
        repo = _init_repo(self.root, origin_head="main", gh_stack=True)
        blocked = _run_hook("gh pr edit 12 --base feature-a", repo)
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("gh stack link", blocked.stderr)
        ok = _run_hook("gh pr edit 12 --base main", repo)
        self.assertEqual(ok.returncode, 0, ok.stderr)

    def test_line_continuations_are_checked_as_one_command(self):
        repo = _init_repo(self.root, origin_head="main", gh_stack=True)
        body = _render_valid_body(repo)
        retarget = _run_hook("gh pr edit 12 \\\n  --base feature-a", repo)
        self.assertEqual(retarget.returncode, 2, retarget.stderr)
        inline = _run_hook("gh pr edit 12 \\\n  --body 'x'", repo)
        self.assertEqual(inline.returncode, 2, inline.stderr)
        valid = _run_hook(f"gh pr create \\\n  --base main \\\n  --body-file {body.name}", repo)
        self.assertEqual(valid.returncode, 0, valid.stderr)

    def test_falls_back_to_main_and_master_without_origin_head(self):
        repo = _init_repo(self.root, origin_head=None, gh_stack=True)
        body = _render_valid_body(repo)
        for trunk in ("main", "master"):
            res = _run_hook(f"gh pr create --draft --base {trunk} --body-file {body.name}", repo)
            self.assertEqual(res.returncode, 0, res.stderr)
        blocked = _run_hook(f"gh pr create --draft --base develop --body-file {body.name}", repo)
        self.assertEqual(blocked.returncode, 2)

    def test_respects_custom_origin_head_trunk(self):
        repo = _init_repo(self.root, origin_head="trunk", gh_stack=True)
        body = _render_valid_body(repo)
        ok = _run_hook(f"gh pr create --draft --base trunk --body-file {body.name}", repo)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        blocked = _run_hook(f"gh pr create --draft --base main --body-file {body.name}", repo)
        self.assertEqual(blocked.returncode, 2)

    def test_linked_worktree_reads_common_dir_gh_stack(self):
        repo = _init_repo(self.root, origin_head="main", gh_stack=True)
        worktree = self.root / "wt"
        _git(repo, "worktree", "add", "-b", "feat-a", str(worktree))
        body = _render_valid_body(worktree)
        blocked = _run_hook(f"gh pr create --draft --base feat-base --body-file {body.name}", worktree)
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("gh stack link", blocked.stderr)
        ok = _run_hook(f"gh pr create --draft --base main --body-file {body.name}", worktree)
        self.assertEqual(ok.returncode, 0, ok.stderr)


class AttributionTests(unittest.TestCase):
    def test_allows_non_requester_capitalized_verbs(self):
        for text in [
            "Pyright says the return type is wrong.",
            "Ruff prefers the shorter form.",
            "Upstream decided to drop Python 3.12.",
            "Each save rewrites the whole cache.",
        ]:
            with self.subTest(text=text):
                self.assertEqual(pr_body.slot_errors("summary", text), [])

    def test_flags_requester_attribution(self):
        for text in [
            "the user asked for this",
            "Dana asked for this.",
            "As requested, the flag is gone.",
            "you decided to drop it",
        ]:
            with self.subTest(text=text):
                errors = pr_body.slot_errors("summary", text)
                self.assertTrue(errors, f"expected attribution error for {text!r}")


if __name__ == "__main__":
    unittest.main()
