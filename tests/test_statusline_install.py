"""Prove install.sh actually wires the statusline up, not just copies the file.

For a long time install.sh copied cc_statusline.py into ~/.claude/ and stopped
there. Nothing wrote settings.json, and settings.json is the only thing that
decides which command Claude Code runs -- so on a real machine the installed
script sat unread while the statusline ran a hand-copied file at a different
path that no install ever refreshed. Every repo-side edit silently failed to
reach the bar it was editing.

Copying a file and activating it are two different steps, and only the second
one is observable to the user. These tests drive the real install.sh against a
throwaway HOME rather than testing the settings-writing logic in isolation,
because the bug was never in that logic -- it was in nobody calling it.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"
COMMAND = "python3 ~/.claude/cc_statusline.py"


def _run_install(home: Path) -> str:
    result = subprocess.run(
        ["bash", str(INSTALL_SH)],
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(f"install.sh failed:\n{result.stderr}")
    return result.stdout


def _settings(home: Path) -> dict:
    return json.loads((home / ".claude" / "settings.json").read_text())


def _write_settings(home: Path, payload: dict) -> None:
    claude = home / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "settings.json").write_text(json.dumps(payload, indent=2))


class StatuslineInstallTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_installs_script_and_points_settings_at_it(self) -> None:
        _run_install(self.home)

        installed = self.home / ".claude" / "cc_statusline.py"
        self.assertTrue(installed.is_file(), "statusline script was not installed")
        self.assertEqual(
            installed.read_text(),
            (REPO_ROOT / "scripts" / "cc_statusline.py").read_text(),
            "installed statusline drifted from the repo source",
        )
        self.assertEqual(_settings(self.home)["statusLine"]["command"], COMMAND)

    def test_preserves_unrelated_settings_keys(self) -> None:
        _write_settings(self.home, {"model": "opus", "enabledPlugins": {"knack": True}})

        _run_install(self.home)

        settings = _settings(self.home)
        self.assertEqual(settings["model"], "opus")
        self.assertEqual(settings["enabledPlugins"], {"knack": True})
        self.assertEqual(settings["statusLine"]["command"], COMMAND)

    def test_migrates_a_statusline_pinned_to_an_older_shipped_path(self) -> None:
        """The exact broken state this fixes: settings naming a path we no longer update."""
        _write_settings(
            self.home,
            {
                "statusLine": {
                    "type": "command",
                    "command": "python3 ~/.claude/statusline.py",
                }
            },
        )

        _run_install(self.home)

        self.assertEqual(_settings(self.home)["statusLine"]["command"], COMMAND)

    def test_leaves_a_statusline_the_user_chose_alone(self) -> None:
        mine = {"type": "command", "command": "~/bin/my-own-bar.sh"}
        _write_settings(self.home, {"statusLine": mine})

        out = _run_install(self.home)

        self.assertEqual(_settings(self.home)["statusLine"], mine)
        self.assertIn("kept your statusLine", out)

    def test_rewrites_only_the_statusline_key(self) -> None:
        """A settings.json already in our output shape must come back byte-identical."""
        original = json.dumps(
            {
                "model": "opus",
                "statusLine": {"type": "command", "command": COMMAND},
                "env": {"FOO": "bar"},
            },
            indent=2,
        )
        settings_path = self.home / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(original + "\n")

        _run_install(self.home)

        self.assertEqual(settings_path.read_text(), original + "\n")

    def test_leaves_malformed_settings_untouched_without_failing_the_install(
        self,
    ) -> None:
        """A broken settings.json must not be clobbered, nor abort the rest of the install."""
        settings_path = self.home / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text('{"model": "opus", oops not json')

        out = _run_install(self.home)

        self.assertEqual(settings_path.read_text(), '{"model": "opus", oops not json')
        self.assertIn("not valid JSON", out)
        self.assertTrue(
            (self.home / ".codex" / "agents").is_dir(),
            "install aborted early instead of continuing past the bad settings file",
        )

    def test_follows_a_symlinked_settings_file(self) -> None:
        """Dotfiles setups symlink settings.json; the link must survive the write."""
        real = self.home / "dotfiles" / "settings.json"
        real.parent.mkdir(parents=True, exist_ok=True)
        real.write_text(json.dumps({"model": "opus"}, indent=2))
        link = self.home / ".claude" / "settings.json"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(real)

        _run_install(self.home)

        self.assertTrue(link.is_symlink(), "symlink was replaced by a regular file")
        self.assertEqual(json.loads(real.read_text())["statusLine"]["command"], COMMAND)
        self.assertEqual(json.loads(real.read_text())["model"], "opus")


if __name__ == "__main__":
    unittest.main()
