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
import re
import shlex
import sys
from pathlib import Path

# (plugin, script path under the plugin root) for Python hooks that stay until a later
# step ports them. The allow-list excuses the runtime, not the command:
# an allow-listed hook must still run as `uv run --script <file>.py`.
ALLOW_LIST = [
    # Removed by step 3-retire-handoff-script.
    ("swe", "scripts/handoff.py"),
    # Removed by step 4-port-swe-scripts.
    ("swe", "skills/ship-pr/scripts/pr_body.py"),
]


PLAIN = re.compile(r'[A-Za-z0-9_./" -]*')


def check_command(plugin: str, command: str) -> str | None:
    """Return None when the command is allowed, else a reason it fails."""
    # One plain command only. Any other character (an operator, a newline,
    # `$(`, a backtick, `#`) would let a second command ride behind an
    # allowed first word, so allow plain words and the plugin root alone.
    bare = command.replace("${CLAUDE_PLUGIN_ROOT}", "").replace("$CLAUDE_PLUGIN_ROOT", "")
    if not PLAIN.fullmatch(bare):
        return "must be one plain command: letters, digits, _ . / - \" and the plugin root only"
    try:
        tokens = shlex.split(command)
    except ValueError as error:
        return f"cannot parse: {error}"
    if not tokens:
        return "empty command"
    head, *args = tokens
    if head == "bun" and args and args[0].endswith(".ts") and not _has_flag(args):
        return None
    if head == "cat" and len(args) == 1 and args[0].endswith(".md"):
        return None
    if head == "uv" and args[:2] == ["run", "--script"] and len(args) > 2:
        script, rest = args[2], args[3:]
        for entry_plugin, path in ALLOW_LIST:
            if entry_plugin == plugin and _below_root(script) == path:
                return "unexpected flag" if _has_flag(rest) else None
    return "must run a .ts file with bun or cat a .md file"


def _has_flag(args: list[str]) -> bool:
    return any(a.startswith("-") for a in args)


def _below_root(script: str) -> str | None:
    for root in ("${CLAUDE_PLUGIN_ROOT}/", "$CLAUDE_PLUGIN_ROOT/"):
        if script.startswith(root):
            return script.removeprefix(root)
    return None


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
