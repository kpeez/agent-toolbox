"""Prove audit_metadata.py polices what the note contract still says.

ADR-0007 retired the [[Project Logs]] category, so the filename, category and
ownership rules that policed `projects/<slug>/logs/` came out. Nothing else in
the suite touches this script, so the checks that stayed -- the ones that make
a daily review a daily review -- were being asserted by nobody. These pin the
seam: what the ADR removed no longer fires, and what it kept still does.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from llmos_vault.frontmatter import parse as parse_frontmatter

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
AUDIT = PLUGIN_ROOT / "scripts/audit_metadata.py"


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    )


def make_vault(root: Path) -> None:
    """A git repo -- the audit reads untracked files to find new notes."""
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")


def write_note(root: Path, relative: str, frontmatter: str, body: str = "x\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\n{textwrap.dedent(frontmatter).strip()}\n---\n\n{body}", encoding="utf-8"
    )
    return path


def run_audit(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(AUDIT), "--root", str(root)],
        capture_output=True,
        text=True,
    )


class RetiredProjectLogRulesTests(unittest.TestCase):
    def test_project_log_note_is_no_longer_specially_policed(self) -> None:
        """ADR-0007: the category and its filename rule are gone.

        This note would have drawn three errors before -- filename not
        YYYY-MM-DD-<project>.md, missing [[Project Logs]], and a project value
        that must match its directory. It is now just an ordinary note.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_vault(root)
            write_note(
                root,
                "projects/demo/logs/whatever-name.md",
                """
                created: 2026-07-16
                """,
            )
            result = run_audit(root)
            self.assertNotIn("Project Logs", result.stdout + result.stderr)
            self.assertNotIn("project log filename", result.stdout + result.stderr)


class RetainedDailyReviewRulesTests(unittest.TestCase):
    def test_daily_review_must_not_claim_project_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_vault(root)
            write_note(
                root,
                "reviews/daily/2026-07-16.md",
                """
                created: 2026-07-16
                project:
                  - "[[projects/demo/demo|Demo]]"
                """,
            )
            result = run_audit(root)
            self.assertIn("must not claim project ownership", result.stdout)
            self.assertNotEqual(result.returncode, 0)

    def test_daily_review_created_must_be_an_iso_date(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_vault(root)
            write_note(
                root,
                "reviews/daily/2026-07-16.md",
                """
                created: last tuesday
                """,
            )
            result = run_audit(root)
            self.assertIn("created must be an ISO date", result.stdout)
            self.assertNotEqual(result.returncode, 0)

    def test_clean_daily_review_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_vault(root)
            write_note(
                root,
                "reviews/daily/2026-07-16.md",
                """
                created: 2026-07-16
                """,
            )
            result = run_audit(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class RetainedPropertyRulesTests(unittest.TestCase):
    def test_retired_property_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_vault(root)
            write_note(
                root,
                "knowledge/thing.md",
                """
                created: 2026-07-16
                type: note
                """,
            )
            result = run_audit(root)
            self.assertIn("retired property type", result.stdout)
            self.assertNotEqual(result.returncode, 0)

    def test_status_outside_the_set_is_rejected(self) -> None:
        """A status the Base does not filter on renders an empty view, not an
        error -- so it has to fail here or it fails silently in Obsidian."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_vault(root)
            write_note(
                root,
                "knowledge/thing.md",
                """
                created: 2026-07-16
                status: nearly-done
                """,
            )
            result = run_audit(root)
            self.assertIn("invalid status", result.stdout)
            self.assertNotEqual(result.returncode, 0)


class FixStampsThroughCanonicalSerializerTests(unittest.TestCase):
    """`--fix` must route through `llmos_vault.frontmatter` (spec 0014 Risks:
    "make audit_metadata import them in the same slice") rather than
    hand-splicing raw text -- so a stamped note comes out normalized: sorted
    keys, wikilinks quoted, single frontmatter block."""

    def test_fix_stamps_categories_and_project_via_canonical_serializer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_vault(root)
            note = write_note(
                root,
                "projects/demo/specs/0001-demo.md",
                """
                created: 2026-07-16
                """,
            )
            result = subprocess.run(
                [sys.executable, str(AUDIT), "--root", str(root), "--fix"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            text = note.read_text(encoding="utf-8")
            properties, _ = parse_frontmatter(text)
            self.assertEqual(properties["categories"], ["[[Specifications]]"])
            self.assertEqual(
                properties["project"], ["[[projects/demo/demo|demo]]"]
            )
            self.assertEqual(text.count("---\n"), 2)
            self.assertEqual(list(properties.keys()), sorted(properties.keys()))
            self.assertIn('  - "[[Specifications]]"', text)

    def test_fix_is_a_no_op_once_stamped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_vault(root)
            note = write_note(
                root,
                "projects/demo/specs/0001-demo.md",
                """
                created: 2026-07-16
                """,
            )
            fix_args = [sys.executable, str(AUDIT), "--root", str(root), "--fix"]
            subprocess.run(fix_args, capture_output=True, text=True)
            once = note.read_text(encoding="utf-8")
            subprocess.run(fix_args, capture_output=True, text=True)
            twice = note.read_text(encoding="utf-8")

            self.assertEqual(once, twice)


if __name__ == "__main__":
    unittest.main()
