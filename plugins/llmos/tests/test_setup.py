"""Prove no rule file or user-level rules directory is ever created in
agent-toolbox (rules live in the vault only -- ADR-0002).

Tests redirect HOME into tmp_path and run the real script; they never touch
the operator's actual ~/.claude, ~/.codex, or ~/.config/llmos.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install.sh"


def run_install(fake_home: Path) -> subprocess.CompletedProcess[str]:
    """Run the real install.sh with HOME redirected into a temp dir.

    The script is non-interactive, so it never blocks on stdin or touches
    anything outside `fake_home`.
    """
    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    result = subprocess.run(
        ["bash", str(INSTALL_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def test_no_rule_files_live_in_agent_toolbox():
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    rule_paths = [f for f in tracked if "rules" in Path(f).parts]

    assert rule_paths == [], (
        f"rule files live in the vault only (ADR-0002), never agent-toolbox: {rule_paths}"
    )


def test_setup_creates_no_user_level_rules_dir(tmp_path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    run_install(fake_home)

    assert not (fake_home / ".claude" / "rules").exists()
