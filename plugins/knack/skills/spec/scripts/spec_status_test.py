#!/usr/bin/env python3
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("spec_status.py")
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

    def test_renders_active_and_archived_sections(self):
        self.write_status("active-spec", "---\ndescription: An active feature.\n---\n")
        self.write_status("_archive/old-spec", "---\ndescription: An archived spec.\n---\n")

        overview = self.module.generate_overview(self.specs)

        self.assertIn("## Active", overview)
        self.assertIn("## Archived", overview)
        self.assertIn("- [active-spec](active-spec/STATUS.md) — An active feature.", overview)
        self.assertIn("- [old-spec](_archive/old-spec/STATUS.md) — An archived spec.", overview)
        self.assertLess(overview.index("## Active"), overview.index("## Archived"))

    def test_spec_without_description_renders_link_only(self):
        self.write_status("no-desc", "# No frontmatter\n")

        overview = self.module.generate_overview(self.specs)

        self.assertIn("- [no-desc](no-desc/STATUS.md)\n", overview)

    def test_archive_dir_excluded_from_active(self):
        self.write_status("_archive/archived", "---\ndescription: Archived.\n---\n")

        overview = self.module.generate_overview(self.specs)

        active_section = overview.split("## Active", 1)[1].split("## Archived", 1)[0]
        self.assertNotIn("archived", active_section)

    def test_empty_specs_dir_renders_none_placeholders(self):
        self.specs.mkdir()

        overview = self.module.generate_overview(self.specs)

        self.assertIn("_None._", overview)

    def test_missing_specs_dir_noops_without_writing(self):
        missing = self.root / "missing-specs"

        overview = self.module.generate_overview(missing)
        result = self.module.write_overview(missing)

        self.assertEqual("", overview)
        self.assertFalse(result)
        self.assertFalse(missing.exists())

    def test_spec_without_status_md_is_skipped(self):
        (self.specs / "no-status").mkdir(parents=True)
        self.write_status("valid", "---\ndescription: Valid spec.\n---\n")

        overview = self.module.generate_overview(self.specs)

        self.assertIn("valid", overview)
        self.assertNotIn("no-status", overview)

    def test_symlinked_specs_directory_is_supported(self):
        real_specs = self.root / "real-specs"
        self.write_status("linked", "---\ndescription: Symlinked specs work.\n---\n")
        self.specs.rename(real_specs)
        self.specs.symlink_to(real_specs, target_is_directory=True)

        overview = self.module.generate_overview(self.specs)

        self.assertIn("- [linked](linked/STATUS.md) — Symlinked specs work.", overview)

    def test_cli_writes_overview(self):
        self.write_status("cli-spec", "---\ndescription: CLI write test.\n---\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--specs-dir", str(self.specs), "--write", "--quiet"],
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode)
        self.assertIn("CLI write test.", (self.specs / "STATUS.md").read_text(encoding="utf-8"))

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
