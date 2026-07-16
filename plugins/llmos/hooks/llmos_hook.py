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
    receipt_script = HOOKS_DIR.parent / "scripts" / "write_daily_receipt.py"
    return (
        f"llmOS root: {root}. Read {root / 'AGENTS.md'} before durable knowledge work.\n"
        f"Today's catch-all branch: {today} (cut off main; per-spec branches live at "
        f"<agent>/{today}/<spec> and merge back into the catch-all, never straight to main).\n"
        "Write a receipt only when a spec is completed: "
        f"python3 {receipt_script} --agent <agent> --receipt-id <spec-slug> "
        "--desc '<what the spec does>' --info '<[[spec]], plans, #issues, PR>' --project <slug>."
    )


def _is_note(path: Path) -> bool:
    return path.suffix == ".md"


def pre_tool_use(data: dict) -> str | None:
    root = _resolved_root()
    if root is None:
        return None
    file_path = (data.get("tool_input") or {}).get("file_path")
    if not file_path:
        return None
    target = Path(file_path).resolve()  # resolve symlinks first (ADR-0002)
    if not _is_under(target, root):
        return None
    if not _is_note(target):
        return None
    schema = root / "agents" / "references" / "schema.md"
    if not schema.is_file():
        return None
    return schema.read_text(encoding="utf-8")


EVENTS = {"session-start": session_start, "pre-tool-use": pre_tool_use}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in EVENTS:
        return  # unrecognized invocation: stay silent, never block
    handler = EVENTS[sys.argv[1]]
    try:
        output = handler(_read_payload())
    except Exception:
        return  # hook failure must never block the tool call
    if output:
        print(output)


if __name__ == "__main__":
    main()
