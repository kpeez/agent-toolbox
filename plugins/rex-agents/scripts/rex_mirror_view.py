#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Show a mirror log in a Rex block and report its state with OSC 7501.

Usage: rex_mirror_view.py LOG LABEL NONCE

Reports `working` at start. When rex_mirror.py writes its exit line
`__rex_mirror_exit_<NONCE>=N`, reports `done` for status 0 or `error`
otherwise, with "LABEL: exit N" as the message, then deletes the log and
exits. Run the block with --keep-open so the record stays. OSC 7501 sequences
in the command's output cannot reach the terminal: the viewer keeps SGR
color sequences, tab, newline, and carriage return, and removes every other
C0 or C1 control, so only the viewer sets the block's status.
"""

import base64
import os
import re
import sys
import time

CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
# An SGR color sequence, kept; or any other C0 or C1 control (ESC included), removed.
UNSAFE = re.compile(r"\x1b\[[0-9;:]*m|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def safe(text: str) -> str:
    return UNSAFE.sub(
        lambda m: m.group() if m.group().startswith("\x1b[") else "", text
    )


def status(state: str, msg: str) -> None:
    b64 = base64.b64encode(CONTROL.sub(" ", msg).encode()).decode()
    sys.stdout.write(f"\033]7501;state={state}:app=rex-mirror:msg={b64}\033\\")
    sys.stdout.flush()


def main() -> int:
    log, label, nonce = sys.argv[1], sys.argv[2], sys.argv[3]
    exit_line = re.compile(rf"^__rex_mirror_exit_{re.escape(nonce)}=(\d+)$")
    status("working", label)
    partial = ""
    with open(log, errors="replace", newline="") as f:
        while True:
            chunk = f.readline()
            if not chunk:
                time.sleep(0.2)
                continue
            partial += chunk
            if not partial.endswith("\n"):
                continue
            line, partial = partial, ""
            m = exit_line.match(line.rstrip("\n"))
            if m:
                rc = int(m.group(1))
                status("done" if rc == 0 else "error", f"{label}: exit {rc}")
                os.unlink(log)
                return 0
            sys.stdout.write(safe(line))
            sys.stdout.flush()


if __name__ == "__main__":
    sys.exit(main())
