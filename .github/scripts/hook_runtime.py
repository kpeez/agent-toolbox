#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Fail when a plugin hook runs a runtime other than bun TS or cat text.

Hooks run on every tool call, so the agent stack keeps them on fast bun
TypeScript. A short allow-list holds the Python hooks that later steps
port; each entry still has to run as `uv run --script`.
"""

import json
import shlex
import sys
from pathlib import Path

# (plugin, script-path substring) for Python hooks that stay until a later
# step ports them. The allow-list excuses the runtime, not the command:
# an allow-listed hook must still run as `uv run --script <file>.py`.
ALLOW_LIST = [
    # Removed by step 2-port-rex-agents.
    ("rex-agents", "hooks/session_start.py"),
    ("rex-agents", "hooks/mirror_hook.py"),
    ("rex-agents", "hooks/subagent_start.py"),
    ("rex-agents", "hooks/session_end.py"),

    # Removed by step 3-retire-handoff-script.
    ("swe", "scripts/handoff.py"),
    # Removed by step 4-port-swe-scripts.
    ("swe", "skills/ship-pr/scripts/pr_body.py"),
]


def check_command(plugin: str, command: str) -> str | None:
    """Return None when the command is allowed, else a reason it fails."""
    tokens = shlex.split(command)
    if not tokens:
        return "empty command"
    head = tokens[0]
    args = tokens[1:]
    if head == "bun" and any(a.endswith(".ts") for a in args):
        return None
    if head == "cat" and any(a.endswith(".md") for a in args):
        return None
    # Match the allow-list on the script path token, not the raw command, so a
    # quoting change to $CLAUDE_PLUGIN_ROOT cannot shift what is matched.
    script_paths = [a for a in args if a.endswith(".py")]
    for entry_plugin, substring in ALLOW_LIST:
        if entry_plugin == plugin and any(substring in p for p in script_paths):
            if head == "uv" and args[:2] == ["run", "--script"]:
                return None
            return "allow-listed script must run as `uv run --script <file>.py`"
    return "must run a .ts file with bun or cat a .md file"


def main() -> int:
    root = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).resolve().parents[2]
    )
    failures = 0
    commands = 0
    files = sorted((root / "plugins").glob("*/hooks/hooks.json"))
    for path in files:
        plugin = path.parent.parent.name
        data = json.loads(path.read_text(encoding="utf-8"))
        for event, groups in data.get("hooks", {}).items():
            for group in groups:
                for hook in group.get("hooks", []):
                    command = hook.get("command", "")
                    commands += 1
                    reason = check_command(plugin, command)
                    if reason is not None:
                        print(
                            f"{path.relative_to(root)} {event}: `{command}` {reason}"
                        )
                        failures += 1
    if failures:
        print(
            f"{failures} hook command(s) use a forbidden runtime. See AGENTS.md."
        )
        return 1
    print(
        f"ok: {commands} hook commands in {len(files)} plugins run bun TS, cat text, or allow-listed uv Python"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
