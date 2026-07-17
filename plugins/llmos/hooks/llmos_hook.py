#!/usr/bin/env python3
"""Gated SessionStart + PreToolUse hook for the llmOS plugin.

One script, no `--provider` flag, serves both Claude and Codex (ADR-0003):
each `hooks.json` entry names its own event on the command line, and the
JSON payload arrives on stdin the same way on both harnesses.

SessionStart gates on the session cwd; PreToolUse gates on the *resolved*
target path, symlinks followed first -- that is what makes an edit to
`docs/agents/specs/*.md` from another repo, which is a symlink into the
vault, still fire (ADR-0002). Outside its gate each event is silent.

This hook runs on every Write/Edit in every repo, so failure must never
block the tool call: an unconfigured vault root makes `vault_root()` raise
`SystemExit` (by design, so a bare CLI invocation fails loudly), and that
raise is caught here and treated as "not in a vault" rather than propagated.
No `MEMORY.md` is read (ADR-0003).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOKS_DIR.parent / "scripts"))


def _read_payload() -> dict:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _is_under(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _resolved_root() -> Path | None:
    """Vault root, or None -- never raises.

    `vault_root()` intentionally `sys.exit`s with a repair message when the
    vault is unconfigured (a good CLI UX for `/setup-llmos`). A hook that ran
    on every Write/Edit everywhere cannot let that propagate: an unconfigured
    vault must read as "this session has nothing to do with the vault," not
    as a blocked tool call.
    """
    try:
        from vault_root import vault_root
    except ImportError:
        return None
    try:
        return vault_root()
    except SystemExit:
        return None


def session_start(data: dict) -> str | None:
    root = _resolved_root()
    if root is None:
        return None
    cwd = Path(data.get("cwd") or ".").resolve()
    if not _is_under(cwd, root):
        return None
    today = date.today().isoformat()
    return (
        f"llmOS root: {root}. Read {root / 'AGENTS.md'} before durable knowledge work.\n"
        f"Insight worth keeping goes under ## Thoughts in "
        f"{root / 'reviews' / 'daily' / f'{today}.md'} -- prose only, and never a "
        "restatement of commits, issues, or PRs, which GitHub already records."
    )


def _is_note(path: Path) -> bool:
    return path.suffix == ".md"


PATCH_VERBS = ("*** Update File:", "*** Add File:", "*** Delete File:")


def _target_paths(tool_input: dict) -> list[str]:
    """Every file the tool call names, in either harness's shape.

    Claude's Write/Edit names exactly one `file_path`. Codex's native
    `apply_patch` names none: its targets live inside the patch envelope on
    `command`, and one patch may touch several files.
    """
    file_path = tool_input.get("file_path")
    if file_path:
        return [file_path]
    command = tool_input.get("command")
    if not command:
        return []
    return [
        line.split(":", 1)[1].strip()
        for line in command.splitlines()
        if line.startswith(PATCH_VERBS)
    ]


def pre_tool_use(data: dict) -> str | None:
    root = _resolved_root()
    if root is None:
        return None
    # resolve symlinks first (ADR-0002); this also anchors Codex's
    # working-directory-relative patch paths against cwd
    targets = [Path(p).resolve() for p in _target_paths(data.get("tool_input") or {})]
    if not any(_is_under(t, root) and _is_note(t) for t in targets):
        return None
    schema = root / "agents" / "references" / "schema.md"
    if not schema.is_file():
        return None
    return schema.read_text(encoding="utf-8")


EVENTS = {"session-start": session_start, "pre-tool-use": pre_tool_use}


def _emit(event: str, output: str) -> str:
    """Render `output` on the one channel that reaches the model for `event`.

    Both harnesses add SessionStart stdout to the model's context, so that
    event prints as-is. PreToolUse does not: plain stdout there is written to
    the transcript only, and the model never sees a byte of it. The sole
    supported injection point is `hookSpecificOutput.additionalContext`, which
    Claude and Codex parse identically (ADR-0003).
    """
    if event == "session-start":
        return output
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": output,
            }
        }
    )


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in EVENTS:
        return  # unrecognized invocation: stay silent, never block
    handler = EVENTS[sys.argv[1]]
    try:
        output = handler(_read_payload())
    except Exception:
        return  # hook failure must never block the tool call
    if output:
        print(_emit(sys.argv[1], output))


if __name__ == "__main__":
    main()
