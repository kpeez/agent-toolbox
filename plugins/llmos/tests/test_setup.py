"""Prove setup-agent.sh retires the stale llmOS symlinks the plugin replaces,
and that no rule file or user-level rules directory is ever created in
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
SETUP_SCRIPT = REPO_ROOT / "scripts" / "setup-agent.sh"


def run_setup_agent(fake_home: Path) -> subprocess.CompletedProcess[str]:
    """Run the real setup-agent.sh with HOME redirected into a temp dir.

    Feeds "n" to the ollama-Modelfiles prompt so the script never blocks on
    stdin or touches anything outside `fake_home`.
    """
    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    result = subprocess.run(
        ["bash", str(SETUP_SCRIPT)],
        cwd=REPO_ROOT,
        input="n\n",
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def test_setup_removes_stale_vault_symlinks(tmp_path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    # A fake symlink target stands in for the vault -- never touch a real one.
    fake_vault_skill = tmp_path / "fake-vault-skill"
    fake_vault_skill.mkdir()

    stale_paths = [
        fake_home / ".claude" / "skills" / "maintain-llmos",
        fake_home / ".claude" / "skills" / "setup-llmos",
        fake_home / ".codex" / "skills" / "setup-llmos",
    ]
    for path in stale_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(fake_vault_skill)

    run_setup_agent(fake_home)

    for path in stale_paths:
        assert not path.is_symlink(), f"{path} should have been removed"


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

    run_setup_agent(fake_home)

    assert not (fake_home / ".claude" / "rules").exists()
