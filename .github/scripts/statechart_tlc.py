#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Install the statechart skill's pinned TLC and Java with mise, and print
TLA2TOOLS=<jar> and JAVA=<java> lines for $GITHUB_ENV.

The pins are read from run.ts, so CI tests the same tla2tools (checked by
sha256) and Java that the skill installs on first use.
"""

import re
import subprocess
import sys
from pathlib import Path

RUN_TS = Path("plugins/swe/skills/statechart/scripts/run.ts")


def pin(name: str, source: str) -> str:
    found = re.search(rf'^const {name} =\s*"([^"]+)";', source, re.MULTILINE)
    if not found:
        sys.exit(
            f'{RUN_TS}: no `const {name} = "...";` line. Update {__file__} to match.'
        )
    return found[1]


def mise(*args: str) -> str:
    return subprocess.run(
        ["mise", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


source = RUN_TS.read_text()
tlc, java = pin("TLC_TOOL", source), pin("JAVA_TOOL", source)
subprocess.run(["mise", "install", java, tlc], check=True, stdout=sys.stderr)
jar = Path(mise("where", tlc)) / "tla2tools.jar"
java_bin = Path(mise("which", "java", "--tool", java))
for path in (jar, java_bin):
    if not path.is_file():
        sys.exit(f"mise reported {path}, but it is not a file.")
print(f"TLA2TOOLS={jar}")
print(f"JAVA={java_bin}")
