#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""SessionStart hook: put the using-rex skill in context for an interactive session in a Rex pane."""

import os
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "using-rex"


def body(text: str) -> str:
    """Return the skill text without its YAML frontmatter."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5 :].lstrip("\n")
    return text


def main() -> int:
    if (
        not os.environ.get("REX_SESSION")
        or os.environ.get("CLAUDE_CODE_ENTRYPOINT") == "sdk-cli"
    ):
        return 0
    print(f"Skill folder: {SKILL}\n")
    print(body((SKILL / "SKILL.md").read_text()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
