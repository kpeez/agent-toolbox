"""Behavioral checks for the autoresearch run cleanup helper."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "cleanup.py"
SPEC = importlib.util.spec_from_file_location("autoresearch_cleanup", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
cleanup = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cleanup
SPEC.loader.exec_module(cleanup)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "2026-08-22"
        self.run.mkdir()
        (self.run / "program.md").write_text("# original program\n", encoding="utf-8")
        (self.run / "EXPERIMENT_SUMMARY.md").write_text("# verified summary\n", encoding="utf-8")
        (self.run / "autoresearch-run.png").write_bytes(b"PNG fixture bytes\n")
        (self.run / "results.jsonl").write_text('{"id": 0}\n', encoding="utf-8")
        (self.run / "logs").mkdir()
        (self.run / "logs" / "exp000.log").write_text("baseline\n", encoding="utf-8")
        self.trash = self.root / "Trash"
        self.trash.mkdir()
        self.trash_command = self.root / "fake-trash.py"
        self.trash_command.write_text(
            "#!/usr/bin/env python3\n"
            "import os, shutil, sys\n"
            "from pathlib import Path\n"
            "destination = Path(os.environ['FAKE_TRASH'])\n"
            "destination.mkdir(parents=True, exist_ok=True)\n"
            "for raw in sys.argv[1:]:\n"
            "    source = Path(raw)\n"
            "    target = destination / source.name\n"
            "    suffix = 1\n"
            "    while target.exists() or target.is_symlink():\n"
            "        target = destination / f'{source.name}-{suffix}'\n"
            "        suffix += 1\n"
            "    shutil.move(str(source), str(target))\n",
            encoding="utf-8",
        )
        self.trash_command.chmod(0o755)
        self.failed_trash_command = self.root / "failed-trash.py"
        self.failed_trash_command.write_text(
            "#!/usr/bin/env python3\n"
            "raise SystemExit('simulated trash interruption')\n",
            encoding="utf-8",
        )
        self.failed_trash_command.chmod(0o755)
        self.old_env = os.environ.copy()
        os.environ["FAKE_TRASH"] = str(self.trash)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        os.environ.clear()
        os.environ.update(self.old_env)

    def apply(self):
        return cleanup.cleanup_run(
            self.run,
            apply=True,
            acknowledged=True,
            markers=set(),
        )

    def with_fake_trash(self):
        return mock.patch.object(cleanup, "find_trash", return_value=str(self.trash_command))

    def archive_path(self) -> Path:
        return self.run / f"{self.run.name}_archive.tar.zst"

    def test_success_retains_only_archive_summary_plot_and_archives_original_program(self):
        summary = (self.run / "EXPERIMENT_SUMMARY.md").read_bytes()
        plot = (self.run / "autoresearch-run.png").read_bytes()
        with self.with_fake_trash():
            result = self.apply()

        self.assertEqual(result["status"], "archived")
        self.assertEqual(
            {entry.name for entry in self.run.iterdir()},
            {self.archive_path().name, "EXPERIMENT_SUMMARY.md", "autoresearch-run.png"},
        )
        self.assertEqual((self.run / "EXPERIMENT_SUMMARY.md").read_bytes(), summary)
        self.assertEqual((self.run / "autoresearch-run.png").read_bytes(), plot)
        members = cleanup._archive_members(self.archive_path())
        program_member = members[f"{self.run.name}/program.md"]
        self.assertEqual(program_member[0], "file")
        expected_digest = hashlib.sha256(b"# original program\n").hexdigest()
        self.assertEqual(program_member[3], expected_digest)
        self.assertIn(f"{self.run.name}/logs/exp000.log", members)
        trashed_programs = list(self.trash.rglob("program.md"))
        self.assertEqual(len(trashed_programs), 1)
        self.assertEqual(trashed_programs[0].read_text(encoding="utf-8"), "# original program\n")

    def test_repeat_invocation_is_a_noop_for_dry_run_and_apply(self):
        with self.with_fake_trash():
            self.apply()
        before = {
            path.name: path.read_bytes()
            for path in self.run.iterdir()
            if path.is_file()
        }
        dry = cleanup.cleanup_run(self.run, apply=False, acknowledged=False, markers=set())
        applied = cleanup.cleanup_run(self.run, apply=True, acknowledged=True, markers=set())
        self.assertEqual(dry["status"], "already-clean")
        self.assertEqual(applied["status"], "already-clean")
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.run.iterdir() if path.is_file()})

    def test_corrupt_archive_is_rejected_without_mutating_lightweight_run(self):
        with self.with_fake_trash():
            self.apply()
        archive = self.archive_path()
        archive.write_bytes(b"corrupted")
        with self.assertRaises(cleanup.CleanupError):
            cleanup.cleanup_run(self.run, apply=False, acknowledged=False, markers=set())
        self.assertTrue((self.run / "EXPERIMENT_SUMMARY.md").is_file())
        self.assertTrue((self.run / "autoresearch-run.png").is_file())

    def test_active_marker_blocks_cleanup_and_preserves_sources(self):
        marker = self.run / ".autoresearch-active"
        marker.write_text("pid=123\n", encoding="utf-8")
        with self.assertRaises(cleanup.CleanupError):
            cleanup.cleanup_run(self.run, apply=False, acknowledged=False, markers={".autoresearch-active"})
        self.assertTrue((self.run / "program.md").is_file())
        self.assertTrue(marker.is_file())

    def test_changing_snapshot_blocks_cleanup(self):
        original = cleanup.snapshot(self.run, excluded_root_names=(f"{self.run.name}_archive.tar.zst",))
        changed_entries = dict(original.entries)
        changed_entries["late.log"] = cleanup.Entry("late.log", "file", 4, 0o644, 0, digest="deadbeef")
        changed = cleanup.Snapshot(changed_entries)
        calls = 0

        def changing_snapshot(*args, **kwargs):
            nonlocal calls
            calls += 1
            return original if calls == 1 else changed

        with mock.patch.object(cleanup, "snapshot", side_effect=changing_snapshot):
            with self.assertRaises(cleanup.CleanupError):
                cleanup.cleanup_run(self.run, apply=False, acknowledged=False, markers=set())
        self.assertTrue((self.run / "program.md").is_file())

    def test_symlink_is_archived_as_a_link_without_following_target(self):
        outside = self.root / "outside.txt"
        outside.write_text("outside\n", encoding="utf-8")
        link = self.run / "external-link"
        link.symlink_to(outside)
        with self.with_fake_trash():
            self.apply()
        members = cleanup._archive_members(self.archive_path())
        link_member = members[f"{self.run.name}/external-link"]
        self.assertEqual(link_member[0], "symlink")
        self.assertEqual(link_member[1], str(outside))
        self.assertNotIn(f"{self.run.name}/external-link/outside.txt", members)
        trashed_link = next(self.trash.rglob("external-link"))
        self.assertTrue(trashed_link.is_symlink())

    def test_missing_required_file_is_rejected(self):
        (self.run / "program.md").unlink()
        with self.assertRaises(cleanup.CleanupError):
            cleanup.cleanup_run(self.run, apply=False, acknowledged=False, markers=set())

    def test_missing_zstd_is_rejected_before_mutation(self):
        real_which = cleanup.shutil.which

        def no_zstd(command):
            return None if command == "zstd" else real_which(command)

        with mock.patch.object(cleanup.shutil, "which", side_effect=no_zstd):
            with self.assertRaises(cleanup.CleanupError):
                cleanup.cleanup_run(self.run, apply=False, acknowledged=False, markers=set())
        self.assertTrue((self.run / "program.md").is_file())

    def test_missing_trash_is_rejected_before_staging(self):
        with mock.patch.object(cleanup, "find_trash", side_effect=cleanup.CleanupError("no trash")):
            with self.assertRaises(cleanup.CleanupError):
                self.apply()
        self.assertTrue((self.run / "program.md").is_file())
        self.assertFalse(self.archive_path().exists())

    def test_insufficient_space_is_rejected_before_staging(self):
        usage = type("Usage", (), {"free": 0})()
        with self.with_fake_trash(), mock.patch.object(cleanup.shutil, "disk_usage", return_value=usage):
            with self.assertRaises(cleanup.CleanupError):
                self.apply()
        self.assertTrue((self.run / "program.md").is_file())
        self.assertFalse(self.archive_path().exists())

    def test_existing_archive_with_full_sources_is_refused_without_overwrite(self):
        archive = self.archive_path()
        archive.write_bytes(b"existing")
        with self.assertRaises(cleanup.CleanupError):
            cleanup.cleanup_run(self.run, apply=False, acknowledged=False, markers=set())
        self.assertEqual(archive.read_bytes(), b"existing")
        self.assertTrue((self.run / "program.md").is_file())

    def test_stage_failure_leaves_originals(self):
        with mock.patch.object(cleanup, "stage_lightweight", side_effect=cleanup.CleanupError("stage failed")):
            with self.with_fake_trash(), self.assertRaises(cleanup.CleanupError):
                self.apply()
        self.assertTrue((self.run / "program.md").is_file())

    def test_corrupt_staged_tar_fails_integrity_before_retirement(self):
        real_verify = cleanup.verify_archive
        calls = 0

        def corrupt_first_archive(archive, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                Path(archive).write_bytes(b"corrupt staged tar")
            return real_verify(archive, *args, **kwargs)

        with self.with_fake_trash(), mock.patch.object(cleanup, "verify_archive", side_effect=corrupt_first_archive):
            with self.assertRaises(cleanup.CleanupError):
                self.apply()
        self.assertTrue((self.run / "program.md").is_file())
        self.assertTrue((self.root / f".{self.run.name}.cleanup-staging").exists())

    def test_valid_tar_with_changed_content_fails_source_hash_verification(self):
        real_verify = cleanup.verify_archive
        calls = 0

        def replace_with_different_valid_archive(archive, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                alternate_root = self.root / "alternate"
                alternate_run = alternate_root / self.run.name
                shutil.copytree(self.run, alternate_run, symlinks=True)
                (alternate_run / "program.md").write_text("different program\n", encoding="utf-8")
                alternate_archive = self.root / "alternate.tar.zst"
                process = subprocess.Popen(
                    [shutil.which("zstd") or "zstd", "-q", "-T0", "-f", "-o", str(alternate_archive), "-"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                assert process.stdin is not None
                with tarfile.open(fileobj=process.stdin, mode="w|") as stream:
                    stream.add(alternate_run, arcname=self.run.name)
                process.stdin.close()
                self.assertEqual(process.wait(), 0)
                if process.stderr is not None:
                    process.stderr.close()
                Path(archive).write_bytes(alternate_archive.read_bytes())
            return real_verify(archive, *args, **kwargs)

        with self.with_fake_trash(), mock.patch.object(cleanup, "verify_archive", side_effect=replace_with_different_valid_archive):
            with self.assertRaises(cleanup.CleanupError):
                self.apply()
        self.assertTrue((self.run / "program.md").is_file())
        self.assertTrue((self.root / f".{self.run.name}.cleanup-staging").exists())

    def test_executable_mode_is_preserved_in_archive(self):
        (self.run / "program.md").chmod(0o755)
        with self.with_fake_trash():
            self.apply()
        members = cleanup._archive_members(self.archive_path())
        self.assertEqual(
            members[f"{self.run.name}/program.md"][4],
            stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH,
        )

    def test_publish_interruption_leaves_originals_and_staging(self):
        with mock.patch.object(cleanup, "publish_lightweight", side_effect=cleanup.CleanupError("interrupted")):
            with self.with_fake_trash(), self.assertRaises(cleanup.CleanupError):
                self.apply()
        self.assertTrue((self.run / "program.md").is_file())
        self.assertTrue(any(path.name.startswith(f".{self.run.name}.cleanup-") for path in self.root.iterdir()))

    def test_install_rename_failure_keeps_recovery_original_and_staging(self):
        real_rename = cleanup.os.rename
        calls = 0

        def fail_install(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated replacement interruption")
            return real_rename(source, destination)

        with self.with_fake_trash(), mock.patch.object(cleanup.os, "rename", side_effect=fail_install):
            with self.assertRaises(OSError):
                self.apply()
        recovery = self.root / f".{self.run.name}.cleanup-original"
        staging = self.root / f".{self.run.name}.cleanup-staging"
        self.assertTrue((recovery / "program.md").is_file())
        self.assertTrue((staging / f"{self.run.name}_archive.tar.zst").is_file())
        self.assertFalse(self.run.exists())

    def test_keyboard_interrupt_after_recovery_rename_keeps_original(self):
        real_rename = cleanup.os.rename
        calls = 0

        def interrupt_install(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise KeyboardInterrupt()
            return real_rename(source, destination)

        with self.with_fake_trash(), mock.patch.object(cleanup.os, "rename", side_effect=interrupt_install):
            with self.assertRaises(KeyboardInterrupt):
                self.apply()
        recovery = self.root / f".{self.run.name}.cleanup-original"
        self.assertTrue((recovery / "program.md").is_file())

    def test_post_replacement_verification_failure_keeps_both_recovery_and_run(self):
        real_verify = cleanup.verify_archive
        calls = 0

        def fail_after_install(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise cleanup.CleanupError("simulated post-install verification failure")
            return real_verify(*args, **kwargs)

        with self.with_fake_trash(), mock.patch.object(cleanup, "verify_archive", side_effect=fail_after_install):
            with self.assertRaises(cleanup.CleanupError):
                self.apply()
        recovery = self.root / f".{self.run.name}.cleanup-original"
        self.assertTrue((recovery / "program.md").is_file())
        self.assertTrue((self.run / self.archive_path().name).is_file())
        self.assertTrue((self.run / "EXPERIMENT_SUMMARY.md").is_file())

    def test_trash_failure_keeps_recovery_original_after_lightweight_install(self):
        with mock.patch.object(cleanup, "find_trash", return_value=str(self.failed_trash_command)):
            with self.assertRaises(cleanup.CleanupError):
                self.apply()
        recovery = self.root / f".{self.run.name}.cleanup-original"
        self.assertTrue((recovery / "program.md").is_file())
        self.assertTrue((self.run / self.archive_path().name).is_file())
        self.assertTrue((self.run / "autoresearch-run.png").is_file())

    def test_change_after_staging_is_detected_before_recovery_rename(self):
        real_stage = cleanup.stage_lightweight

        def stage_then_change(*args, **kwargs):
            staging = real_stage(*args, **kwargs)
            (self.run / "results.jsonl").write_text('{"id": 1}\n', encoding="utf-8")
            return staging

        with self.with_fake_trash(), mock.patch.object(cleanup, "stage_lightweight", side_effect=stage_then_change):
            with self.assertRaises(cleanup.CleanupError):
                self.apply()
        self.assertTrue((self.run / "program.md").is_file())
        self.assertFalse((self.root / f".{self.run.name}.cleanup-original").exists())
        self.assertTrue((self.root / f".{self.run.name}.cleanup-staging").exists())

    def test_apply_requires_stopped_run_acknowledgment(self):
        with self.assertRaises(cleanup.CleanupError):
            cleanup.cleanup_run(self.run, apply=True, acknowledged=False, markers=set())
        self.assertTrue((self.run / "program.md").is_file())


if __name__ == "__main__":
    unittest.main()
