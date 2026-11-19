#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Fail when a plugin hook runs a runtime its event class does not allow.

A hook that fires on every tool call pays its startup cost each time, so it
runs TypeScript through scripts/run-ts (bun, else node 22.18+) or cats a text
file. A hook on any other event may also run a uv Python script. A bare `bun`
command is not allowed because it has no node fallback.

Per-call events (PreToolUse, PostToolUse, PostToolUseFailure,
PermissionRequest) allow:

- `sh $ROOT/scripts/run-ts $ROOT/<path>.ts [args]`
- `cat $ROOT/<path>.md`

Every other event allows the same, plus
`uv run --script $ROOT/<path>.py [args]`.

$ROOT is the double-quoted token "$CLAUDE_PLUGIN_ROOT" followed by `/`. The
quotes stop word splitting on a root path with spaces. The braced form
${CLAUDE_PLUGIN_ROOT} is not allowed because fish, which Codex may run through
`$SHELL -lc`, rejects it. A path with a `..` segment is not allowed because it
leaves the plugin folder.

A plugin whose hooks use run-ts must ship scripts/run-ts, and every copy must
be byte-identical.
"""

import json
import re
import shlex
import sys
from pathlib import Path


PLAIN = re.compile(r'[A-Za-z0-9_./" -]*')


PER_CALL_EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionRequest"}
QUOTED_ROOT = '"$CLAUDE_PLUGIN_ROOT"'
ROOT = re.compile(r"\$CLAUDE_PLUGIN_ROOT/")
RUN_TS = "scripts/run-ts"


def _under_root(token: str, suffix: str) -> bool:
    """True for a path under the plugin root that ends in suffix and has no `..` segment."""
    match = ROOT.match(token)
    return (
        match is not None
        and token.endswith(suffix)
        and len(token) > match.end() + len(suffix)
        and ".." not in token.split("/")
    )


def _runs_run_ts(command: str) -> bool:
    """True when the command runs the plugin's scripts/run-ts launcher."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    match = ROOT.match(tokens[1]) if len(tokens) > 1 else None
    return tokens[:1] == ["sh"] and match is not None and tokens[1][match.end():] == RUN_TS


def check_command(command: str, event: str) -> str | None:
    """Return None when the command is allowed for the event, else a reason it fails."""
    # One plain command only. Any other character (an operator, a newline,
    # `$(`, a backtick, `#`) would let a second command ride behind an
    # allowed first word, so allow plain words and the quoted plugin root
    # alone. This raw-text check also rejects the braced and unquoted root,
    # because shlex.split drops the quotes and hides them from the tokens.
    bare = command.replace(QUOTED_ROOT, "")
    if not PLAIN.fullmatch(bare):
        return 'must be one plain command: letters, digits, _ . / - " and the double-quoted "$CLAUDE_PLUGIN_ROOT" only'
    try:
        tokens = shlex.split(command)
    except ValueError as error:
        return f"cannot parse: {error}"
    if not tokens:
        return "empty command"
    head, *args = tokens
    if head == "cat" and len(args) == 1 and _under_root(args[0], ".md"):
        return None
    if (
        head == "sh"
        and len(args) >= 2
        and _runs_run_ts(command)
        and _under_root(args[1], ".ts")
        and not _has_flag(args)
    ):
        return None
    if (
        event not in PER_CALL_EVENTS
        and head == "uv"
        and args[:2] == ["run", "--script"]
        and len(args) >= 3
        and _under_root(args[2], ".py")
        and not _has_flag(args[3:])
    ):
        return None
    if event in PER_CALL_EVENTS:
        return f'{event} fires on every tool call: run `sh "$CLAUDE_PLUGIN_ROOT"/scripts/run-ts "$CLAUDE_PLUGIN_ROOT"/<path>.ts` or cat `"$CLAUDE_PLUGIN_ROOT"/<path>.md`, with no `..` segment'
    return 'must run `sh "$CLAUDE_PLUGIN_ROOT"/scripts/run-ts "$CLAUDE_PLUGIN_ROOT"/<path>.ts`, `uv run --script "$CLAUDE_PLUGIN_ROOT"/<path>.py`, or cat `"$CLAUDE_PLUGIN_ROOT"/<path>.md`, with no `..` segment'


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
    launchers: dict[Path, bytes] = {}
    files = sorted((root / "plugins").glob("*/hooks/hooks.json"))
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        launcher = path.parents[1] / RUN_TS
        for event, groups in data.get("hooks", {}).items():
            for group in groups:
                for hook in group.get("hooks", []):
                    command = hook.get("command", "")
                    commands += 1
                    reason = check_command(command, event)
                    if reason is None and _runs_run_ts(command):
                        if not launcher.is_file():
                            reason = f"needs {launcher.relative_to(root)}, which is missing"
                        else:
                            launchers[launcher] = launcher.read_bytes()
                    if reason is not None:
                        print(
                            f"{path.relative_to(root)} {event}: `{command}` {reason}"
                        )
                        failures += 1
    if len(set(launchers.values())) > 1:
        names = ", ".join(str(p.relative_to(root)) for p in sorted(launchers))
        print(f"the run-ts copies differ and must be byte-identical: {names}")
        failures += 1
    if failures:
        print(
            f"{failures} hook problem(s) found. See AGENTS.md."
        )
        return 1
    print(
        f"ok: {commands} hook commands in {len(files)} plugins run run-ts TS, uv Python off the per-call path, or cat text"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
