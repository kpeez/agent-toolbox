"""Public package invariants and clean, cross-cwd project installation."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


PACKAGE = Path(os.environ.get("UNI_PACKAGE_ROOT", Path(__file__).resolve().parents[1]))
REPOSITORY = Path(os.environ.get("UNI_REPOSITORY_ROOT", PACKAGE.parents[1]))


def assert_local_references(test, skills):
    """Resolve shipped Markdown resources as an installed Codex instance would."""
    files = list(skills.rglob("*.md"))
    test.assertTrue(files, "No installed skill instructions")
    for document in files:
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text()):
            link = link.split("#", 1)[0].strip("<>")
            if not link or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", link):
                continue
            target = (document.parent / link).resolve()
            test.assertTrue(target.is_relative_to(skills.resolve()), f"Resource escapes installed sibling bundle: {document}: {link}")
            test.assertTrue(target.exists(), f"Missing installed resource: {document}: {link}")


class PackagingTests(unittest.TestCase):
    def test_provider_versions_and_catalog_sources(self):
        manifests = [json.loads((PACKAGE / provider / "plugin.json").read_text())
                     for provider in (".claude-plugin", ".codex-plugin")]
        self.assertEqual(manifests[0]["version"], manifests[1]["version"])
        self.assertEqual(manifests[0]["name"], "uni")
        self.assertEqual(manifests[1]["name"], "uni")
        for catalog in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
            plugins = json.loads((REPOSITORY / catalog).read_text())["plugins"]
            uni = [plugin for plugin in plugins if plugin["name"] == "uni"]
            self.assertEqual(len(uni), 1, f"Uni must be discoverable exactly once in {catalog}")
            for plugin in plugins:
                declared = plugin["source"]
                if isinstance(declared, dict):
                    self.assertEqual(declared["source"], "local")
                    declared = declared["path"]
                source = (REPOSITORY / declared).resolve()
                self.assertTrue(source.is_relative_to((REPOSITORY / "plugins").resolve()))
                self.assertTrue(source.is_dir(), f"Catalog points at missing plugin: {source}")
                provider_manifests = [json.loads((source / provider / "plugin.json").read_text())
                                      for provider in (".claude-plugin", ".codex-plugin")]
                self.assertEqual(provider_manifests[0]["version"], provider_manifests[1]["version"])
                for hook in (source / "hooks").glob("*.json"):
                    self.assertIsInstance(json.loads(hook.read_text()), dict)

    def test_installed_sibling_resources_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="uni-package-check-") as temporary:
            scratch = Path(temporary)
            copied = scratch / "bundle"
            shutil.copytree(PACKAGE, copied)
            project, foreign_cwd = scratch / "project", scratch / "elsewhere"
            project.mkdir()
            foreign_cwd.mkdir()
            install = copied / "scripts/install.nu"
            result = subprocess.run(["nu", str(install), str(project)], cwd=foreign_cwd,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = project / ".agents/skills"
            source_skills = sorted(path.name for path in (copied / "skills").iterdir() if path.is_dir())
            self.assertEqual(sorted(path.name for path in installed.iterdir()), source_skills)
            self.assertEqual(len(source_skills), 8, "The requested complete suite has eight capabilities")
            for source in (copied / "skills").rglob("*"):
                if source.is_file() and "__pycache__" not in source.parts:
                    self.assertEqual((installed / source.relative_to(copied / "skills")).read_bytes(), source.read_bytes())
            assert_local_references(self, installed)
            marker = installed / "learn" / "learner-owned-note.txt"
            marker.write_text("Preserve learner-owned content")
            before = {path.relative_to(installed): path.read_bytes() for path in installed.rglob("*") if path.is_file()}
            retry = subprocess.run(["nu", str(install), str(project)], cwd=foreign_cwd,
                                   capture_output=True, text=True)
            self.assertNotEqual(retry.returncode, 0, "Repeated installation must reject collisions")
            self.assertIn("Refusing to overwrite", retry.stderr)
            self.assertEqual(before, {path.relative_to(installed): path.read_bytes() for path in installed.rglob("*") if path.is_file()})

    def test_install_collision_is_atomic_and_rejects_symlink(self):
        with tempfile.TemporaryDirectory(prefix="uni-collision-check-") as temporary:
            scratch = Path(temporary)
            project = scratch / "project"
            project.mkdir()
            destination = project / ".agents/skills"
            destination.mkdir(parents=True)
            unrelated = destination / "unrelated"
            unrelated.mkdir()
            (unrelated / "SKILL.md").write_text("User-owned unrelated skill")
            original = scratch / "original"
            original.mkdir()
            (original / "SKILL.md").write_text("User-owned review skill")
            (destination / "learn-review").symlink_to(original, target_is_directory=True)
            result = subprocess.run(["nu", str(PACKAGE / "scripts/install.nu"), str(project)],
                                    cwd=scratch, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Refusing to overwrite", result.stderr)
            self.assertEqual(sorted(path.name for path in destination.iterdir()), ["learn-review", "unrelated"])
            self.assertTrue((destination / "learn-review").is_symlink())
            self.assertEqual((original / "SKILL.md").read_text(), "User-owned review skill")


if __name__ == "__main__":
    unittest.main()
