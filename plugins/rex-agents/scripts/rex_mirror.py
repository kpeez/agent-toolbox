#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Pass a command's output through unchanged, mirror it into a Rex block, and exit with its status.

The mirror hook pipes a background command into this script in this form:

    { trap 'printf "\\n__rex_rc=%d\\n" "$?"' EXIT; CMD
    exit $?; } 2>&1 | rex_mirror.py LABEL [SESSION_ID]

The EXIT trap appends a status marker. This script holds back the last bytes
of the stream so the marker never reaches stdout, then exits with the status
it names. A stream without the marker exits 125.
"""

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MARKER = re.compile(rb"\n__rex_rc=(\d+)\n$")
HOLD = 32  # longer than any marker, so a marker split across reads is still held back
NO_MARKER = 125
CACHE = Path.home() / ".cache" / "rex-agents"


def start_viewer(label: str, log: str, nonce: str) -> str | None:
    """Open a Rex block that shows the log. Return its block ID, or None."""
    rex, uv = shutil.which("rex"), shutil.which("uv")
    session = os.environ.get("REX_SESSION")
    if not (rex and uv and session):
        return None
    viewer = str(Path(__file__).resolve().with_name("rex_mirror_view.py"))
    try:
        r = subprocess.run(
            [
                rex,
                "run",
                "-s",
                session,
                "--focus=false",
                "--keep-open",
                "--shell=none",
                "--label",
                label,
                "--json",
                "--",
                uv,
                "run",
                "--script",
                viewer,
                log,
                label,
                nonce,
            ],
            capture_output=True,
            check=False,
            timeout=15,
        )
        return json.loads(r.stdout)["block_ids"][0] if r.returncode == 0 else None
    except (subprocess.TimeoutExpired, ValueError, KeyError, IndexError):
        return None


def remember(session_id: str, block: str, label: str) -> None:
    """Record the block so the session-end hook can close it."""
    CACHE.mkdir(parents=True, exist_ok=True)
    with open(CACHE / f"{session_id}.jsonl", "a") as f:
        f.write(
            json.dumps(
                {
                    "block": block,
                    "rex_session": os.environ["REX_SESSION"],
                    "label": label,
                }
            )
            + "\n"
        )


def main() -> int:
    label = sys.argv[1] if len(sys.argv) > 1 else "[claude] job"
    session_id = sys.argv[2] if len(sys.argv) > 2 else ""
    fd, log = tempfile.mkstemp(prefix="rex-mirror-", suffix=".log")
    os.close(fd)
    nonce = secrets.token_hex(
        8
    )  # the exit line names it, so command output cannot fake one
    block = start_viewer(label, log, nonce)
    if block and session_id:
        remember(session_id, block, label)
    out = sys.stdout.buffer
    tail = b""
    with open(log, "ab", buffering=0) as logf:
        while chunk := sys.stdin.buffer.read1(65536):
            tail += chunk
            if len(tail) > HOLD:
                out.write(tail[:-HOLD])
                out.flush()
                logf.write(tail[:-HOLD])
                tail = tail[-HOLD:]
        m = MARKER.search(tail)
        rc = int(m.group(1)) if m else NO_MARKER
        body = tail[: m.start()] if m else tail
        out.write(body)
        out.flush()
        logf.write(body)
        logf.write(f"\n__rex_mirror_exit_{nonce}={rc}\n".encode())
    if not block:
        os.unlink(log)
    if not m:
        print(
            "rex_mirror: the command's exit status marker is missing", file=sys.stderr
        )
    return rc


if __name__ == "__main__":
    sys.exit(main())
