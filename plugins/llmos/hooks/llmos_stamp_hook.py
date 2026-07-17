#!/usr/bin/env python3
"""PostToolUse hook (Write|Edit): normalize + stamp vault markdown notes.

One process: normalizes frontmatter, stamps `updated` with today's date,
appends the invoking provider to `authors` if detectable and absent, and
flags the qmd collection dirty for the Stop hook (`llmos_qmd_hook.py`) to
consume. Non-vault writes and notes without a frontmatter block are left
untouched. File resolution (vault root, symlinks, Codex's `apply_patch`
envelope) is imported from `llmos_hook.py`, not reimplemented. Failures never
block the tool call (same fail-silent contract as `llmos_hook.py`).
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOKS_DIR.parent))  # llmos_vault package

from llmos_dirty_flag import flag_path  # noqa: E402
from llmos_hook import (  # noqa: E402
    _is_note,
    _is_under,
    _read_payload,
    _resolved_root,
    _target_paths,
)

from llmos_vault import frontmatter  # noqa: E402

COLLECTION = "llmos"

PROVIDER_ENV_MARKERS = (
    ("claude", "CLAUDECODE"),
    ("codex", "CODEX_SANDBOX_NETWORK_DISABLED"),
    ("gemini", "GEMINI_CLI"),
)


def _provider() -> str | None:
    """Best-effort invoking-provider name from harness-set env vars.

    ADR-0003 found Claude and Codex indistinguishable via `CLAUDE_PLUGIN_ROOT`
    (both set it); these markers are harness-specific instead. Returns None
    rather than guess when nothing matches, so `authors` is left alone.
    """
    for name, marker in PROVIDER_ENV_MARKERS:
        if os.environ.get(marker):
            return name
    return None


def stamp_vault_note(path: Path, provider: str | None) -> None:
    text = path.read_text(encoding="utf-8")
    properties, body = frontmatter.parse(text)
    frontmatter.set_scalar(properties, "updated", date.today().isoformat())
    if provider:
        frontmatter.append_unique(properties, "authors", provider)
    path.write_text(frontmatter.serialize(properties, body), encoding="utf-8")


def post_tool_use(data: dict) -> None:
    root = _resolved_root()
    if root is None:
        return
    targets = [Path(p).resolve() for p in _target_paths(data.get("tool_input") or {})]
    vault_targets = [t for t in targets if _is_under(t, root) and _is_note(t) and t.is_file()]
    if not vault_targets:
        return
    provider = _provider()
    stamped = False
    for target in vault_targets:
        try:
            stamp_vault_note(target, provider)
            stamped = True
        except ValueError:
            continue  # no frontmatter block: nothing to normalize or stamp
    if stamped:
        session_id = data.get("session_id") or "default"
        flag_path(session_id, COLLECTION).touch()


def main() -> None:
    try:
        post_tool_use(_read_payload())
    except Exception:
        return  # hook failure must never block the tool call


if __name__ == "__main__":
    main()
