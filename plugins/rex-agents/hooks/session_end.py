#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""SessionEnd hook: close this session's mirror blocks that ended `done`.

rex_mirror.py lists each block it opens in ~/.cache/rex-agents/<session_id>.jsonl.
A block whose newest status record is `done` is closed. An `error` block and a
block still `working` stay open for the user, and stay in the list.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

CACHE = Path.home() / ".cache" / "rex-agents"


def newest_state(rex: str, session: str, block: str) -> str | None:
    """Return the state of the block's newest record, "gone" if the block is gone, or None."""
    r = subprocess.run(
        [rex, "block", "call", "-s", session, "-b", block, "program_status"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if r.returncode != 0:
        return "gone" if "not found" in r.stderr else None
    records = json.loads(r.stdout).get("records") or []
    if not records:
        return None
    return max(records, key=lambda rec: rec.get("updated_at", ""))["state"]


def main() -> int:
    session_id = json.load(sys.stdin).get("session_id", "")
    path = CACHE / f"{session_id}.jsonl"
    rex = shutil.which("rex")
    if not session_id or not rex or not path.exists():
        return 0
    keep = []
    for line in path.read_text().splitlines():
        entry = json.loads(line)
        state = newest_state(rex, entry["rex_session"], entry["block"])
        if state == "done":
            subprocess.run(
                [rex, "block", "close", "-s", entry["rex_session"], entry["block"]],
                capture_output=True,
                check=False,
                timeout=10,
            )
        elif state != "gone":
            keep.append(line)
    if keep:
        path.write_text("\n".join(keep) + "\n")
    else:
        path.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
