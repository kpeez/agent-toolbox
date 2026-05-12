#!/usr/bin/env python3
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("spec-status.py")
HOOK_INSTALLER_PATH = Path(__file__).with_name("install-status-hooks.sh")


def load_module():
    spec = importlib.util.spec_from_file_location("spec_status", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SpecStatusTest(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.specs = self.root / "specs"

    def tearDown(self):
        self.tmp.cleanup()

    def write_status(self, slug, text):
        status_path = self.specs / slug / "STATUS.md"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(text, encoding="utf-8")
        return status_path

    def test_parses_frontmatter_and_renders_deterministic_overview(self):
        self.write_status(
            "done-spec",
            """---
slug: done-spec
title: Done Spec
phase: done
blocked: false
updated: 2026-05-08
summary: Finished workflow cleanup.
prs: ["#11 `02e8b75`"]
---

# Done Spec - Status
""",
        )
        self.write_status(
            "active-spec",
            """---
slug: active-spec
title: Active Spec
phase: implementing
blocked: true
updated: 2026-05-09
summary: Build deterministic status overview.
issues: []
prs: []
---

# Active Spec - Status
""",
        )

        overview = self.module.generate_overview(self.specs)

        self.assertIn("# Specs Status", overview)
        self.assertIn("| active-spec | implementing | yes | 2026-05-09 | Build deterministic status overview. |", overview)
        self.assertIn("| done-spec | 2026-05-08 | Finished workflow cleanup. | #11 `02e8b75` |", overview)
        self.assertLess(overview.index("## Active"), overview.index("## Completed"))

    def test_missing_specs_noops_without_writing(self):
        missing = self.root / "missing-specs"

        overview = self.module.generate_overview(missing)
        result = self.module.write_overview(missing)

        self.assertEqual("", overview)
        self.assertFalse(result)
        self.assertFalse(missing.exists())

    def test_reports_missing_and_malformed_status_files(self):
        (self.specs / "missing-status").mkdir(parents=True)
        self.write_status("bad-status", "# Bad Status\n\nNo frontmatter here.\n")

        overview = self.module.generate_overview(self.specs)

        self.assertIn("## Needs Attention", overview)
        self.assertIn("| bad-status | malformed STATUS.md frontmatter:", overview)
        self.assertIn("| missing-status | missing STATUS.md |", overview)

    def test_sorts_active_before_completed_by_phase_blocked_updated_and_slug(self):
        for slug, phase, blocked, updated in [
            ("beta", "implementing", "false", "2026-05-09"),
            ("alpha", "implementing", "false", "2026-05-09"),
            ("blocked", "implementing", "true", "2026-05-10"),
            ("planning", "plan", "false", "2026-05-11"),
            ("done", "done", "false", "2026-05-12"),
        ]:
            self.write_status(
                slug,
                f"""---
slug: {slug}
title: {slug}
phase: {phase}
blocked: {blocked}
updated: {updated}
summary: {slug} summary.
prs: []
---
""",
            )

        overview = self.module.generate_overview(self.specs)

        active = overview.split("## Active", 1)[1].split("## Completed", 1)[0]
        self.assertLess(active.index("| planning |"), active.index("| alpha |"))
        self.assertLess(active.index("| alpha |"), active.index("| beta |"))
        self.assertLess(active.index("| beta |"), active.index("| blocked |"))

    def test_symlinked_specs_directory_is_supported(self):
        real_specs = self.root / "real-specs"
        self.write_status(
            "linked",
            """---
slug: linked
title: Linked
phase: verifying
blocked: false
updated: 2026-05-09
summary: Symlinked specs work.
prs: []
---
""",
        )
        self.specs.rename(real_specs)
        self.specs.symlink_to(real_specs, target_is_directory=True)

        overview = self.module.generate_overview(self.specs)

        self.assertIn("| linked | verifying | no | 2026-05-09 | Symlinked specs work. |", overview)

    def test_cli_writes_overview(self):
        self.write_status(
            "cli-spec",
            """---
slug: cli-spec
title: CLI Spec
phase: done
blocked: false
updated: 2026-05-09
summary: CLI writes overview.
prs: ["#12 `abc123`"]
---
""",
        )

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--specs-dir", str(self.specs), "--write", "--quiet"],
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode)
        self.assertIn("CLI writes overview.", (self.specs / "STATUS.md").read_text(encoding="utf-8"))

    def test_hook_installer_writes_git_hooks_that_work_without_specs(self):
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)

        result = subprocess.run(
            ["bash", str(HOOK_INSTALLER_PATH)],
            cwd=repo,
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode)
        hooks_dir = repo / ".git" / "hooks"
        for hook_name in ["post-commit", "post-merge", "post-checkout"]:
            hook_path = hooks_dir / hook_name
            self.assertTrue(hook_path.exists(), hook_name)
            self.assertEqual(0, subprocess.run([str(hook_path)], cwd=repo, check=False).returncode)
        self.assertFalse((hooks_dir / "pre-push").exists())

        pre_push_result = subprocess.run(
            ["bash", str(HOOK_INSTALLER_PATH), "--include-pre-push", "--force"],
            cwd=repo,
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual("", pre_push_result.stderr)
        self.assertEqual(0, pre_push_result.returncode)
        self.assertTrue((hooks_dir / "pre-push").exists())


if __name__ == "__main__":
    unittest.main()
