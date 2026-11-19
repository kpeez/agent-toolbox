#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Fail when a plugin hook runs a runtime other than bun TS or cat text.

Hooks run on every tool call, so the agent stack keeps them on fast bun
TypeScript.
"""

import json
import re
import shlex
import sys
from pathlib import Path


PLAIN = re.compile(r'[A-Za-z0-9_./" -]*')


def check_command(command: str) -> str | None:
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
    return "must run a .ts file with bun or cat a .md file"


def _has_flag(args: list[str]) -> bool:
    return any(a.startswith("-") for a in args)


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
        data = json.loads(path.read_text(encoding="utf-8"))
        for event, groups in data.get("hooks", {}).items():
            for group in groups:
                for hook in group.get("hooks", []):
                    command = hook.get("command", "")
                    commands += 1
                    reason = check_command(command)
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
        f"ok: {commands} hook commands in {len(files)} plugins run bun TS or cat text"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
