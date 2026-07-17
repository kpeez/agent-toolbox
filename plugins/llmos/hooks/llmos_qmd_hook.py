#!/usr/bin/env python3
"""Stop hook: reindex the qmd `llmos` collection iff this turn dirtied it.

Runs `qmd update -c llmos` only when the PostToolUse stamp hook
(`llmos_stamp_hook.py`) left a dirty flag for this session, then clears the
flag either way -- a vault-untouched turn spawns no qmd process at all.
Failures (qmd missing, non-zero exit) never block the turn (same fail-silent
contract as `llmos_hook.py`).
"""

from __future__ import annotations

import subprocess

from llmos_dirty_flag import flag_path
from llmos_hook import _read_payload

COLLECTION = "llmos"


def stop(data: dict) -> None:
    session_id = data.get("session_id") or "default"
    flag = flag_path(session_id, COLLECTION)
    if not flag.exists():
        return
    try:
        subprocess.run(["qmd", "update", "-c", COLLECTION], check=False)
    finally:
        flag.unlink(missing_ok=True)


def main() -> None:
    try:
        stop(_read_payload())
    except Exception:
        return  # hook failure must never block the turn


if __name__ == "__main__":
    main()
