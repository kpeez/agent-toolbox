#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Fail when a plugin under plugins/ names another plugin's skill or agent.

Each plugin installs alone, so a reference such as `lab:autoresearch` inside
plugins/swe leads a swe-only user to a skill that does not exist.
"""

import re
import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    plugins_dir = root / "plugins"
    plugins = sorted(p.name for p in plugins_dir.iterdir() if p.is_dir())
    failures = 0
    for plugin in plugins:
        others = [p for p in plugins if p != plugin]
        pattern = re.compile(
            rf"(?<![\w-])({'|'.join(map(re.escape, others))}):[a-z][\w-]*"
        )
        for path in sorted((plugins_dir / plugin).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                for match in pattern.finditer(line):
                    print(
                        f"{path.relative_to(root)}:{number}: names `{match.group(0)}` from another plugin"
                    )
                    failures += 1
    if failures:
        print(
            f"{failures} cross-plugin reference(s). Inline the rule or copy the skill; see AGENTS.md."
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
