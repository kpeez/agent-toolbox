"""The plugin's static config must stay shaped the way both harnesses expect.

These replace the vault suite's HookConfigTests, which asserted the same
invariants against the retired agents/claude/settings.template.json and
agents/codex/hooks.json payloads.
"""

from __future__ import annotations

import json
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parents[1]


def _hook_commands() -> list[str]:
    hooks = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text())["hooks"]
    return [
        entry["command"]
        for event in hooks.values()
        for matcher in event
        for entry in matcher["hooks"]
    ]


def test_codex_manifest_omits_hooks_key() -> None:
    # Codex manifest validation rejects a "hooks" key; hooks are auto-discovered.
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text())
    assert "hooks" not in manifest


def test_hooks_declare_session_start_and_pre_tool_use() -> None:
    hooks = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text())["hooks"]
    assert set(hooks) == {"SessionStart", "PreToolUse"}
    assert hooks["PreToolUse"][0]["matcher"] == "Write|Edit"


def test_hook_commands_use_the_plugin_root_variable() -> None:
    # Both harnesses expand ${CLAUDE_PLUGIN_ROOT}; there is no CODEX_PLUGIN_ROOT.
    commands = _hook_commands()
    assert commands
    assert all("${CLAUDE_PLUGIN_ROOT}" in command for command in commands)
    assert not any("CODEX_PLUGIN_ROOT" in command for command in commands)


def test_no_hook_command_passes_provider() -> None:
    assert not any("--provider" in command for command in _hook_commands())


def test_marketplace_registers_the_plugin() -> None:
    marketplace = json.loads(
        (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text()
    )
    entry = next(p for p in marketplace["plugins"] if p["name"] == "llmos")
    assert entry["source"] == "./plugins/llmos"
