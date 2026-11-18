#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""PreToolUse hook: mirror each background Bash command into its own Rex block.

Rewrites a Bash call only when all of these hold: `run_in_background` is true,
the permission mode is `auto` or `bypassPermissions`, REX_SESSION is set, `rex`
and `uv` are on PATH, REX_AGENTS_MIRROR is not `0`, and the command is not
already mirrored. The hook returns `updatedInput` and no permission decision.
Claude Code checks permission rules against each subcommand of the returned
command, so a deny rule for the original command still blocks the wrapped
form (tested with `Bash(touch:*)` and `Bash(git clean:*)`).

In a mode that prompts, the wrapped command does not match the user's allow
rules and trips Claude Code's brace-and-quote check, so an allowed command
would prompt. Those modes keep the command unchanged.
"""

import json
import os
import shlex
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path

MIRROR = Path(__file__).resolve().parent.parent / "scripts" / "rex_mirror.py"
TRAP = 'trap \'printf "\\n__rex_rc=%d\\n" "$?"\' EXIT'
LABEL_MAX = 60
MIRROR_MODES = {"auto", "bypassPermissions"}


def label_for(tool_input: dict, agent_id: str | None) -> str:
    text = tool_input.get("description") or tool_input.get("command", "")
    text = " ".join(str(text).split())[:LABEL_MAX]
    return f"[claude:sub] {text}" if agent_id else f"[claude] {text}"


def mirrored(command: str, label: str, session_id: str, uv: str) -> str:
    return (
        f"{{ {TRAP}; {command}\nexit $?; }} 2>&1 | "
        f"{shlex.quote(uv)} run --script {shlex.quote(str(MIRROR))} "
        f"{shlex.quote(label)} {shlex.quote(session_id)}"
    )


def decide(data: dict, env: Mapping[str, str], which=shutil.which) -> dict | None:
    """Return the hook output for one PreToolUse event, or None to leave the call alone."""
    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command")
    if data.get("tool_name") != "Bash" or not isinstance(command, str):
        return None
    if tool_input.get("run_in_background") is not True:
        return None
    if data.get("permission_mode") not in MIRROR_MODES:
        return None
    if not env.get("REX_SESSION") or env.get("REX_AGENTS_MIRROR") == "0":
        return None
    uv = which("uv")
    if not uv or not which("rex"):
        return None
    if MIRROR.name in command:
        return None
    label = label_for(tool_input, data.get("agent_id"))
    updated = dict(tool_input)
    updated["command"] = mirrored(command, label, data.get("session_id", ""), uv)
    return {
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": updated}
    }


def main() -> int:
    out = decide(json.load(sys.stdin), os.environ)
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
