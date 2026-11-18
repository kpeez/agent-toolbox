#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""SubagentStart hook: tell a subagent in a Rex pane to leave panes and sessions alone."""

import json
import os
import sys

RULE = (
    "You are a subagent. Never open, rename, or arrange Rex panes or sessions. "
    "In auto mode, your background commands are mirrored into Rex automatically."
)


def main() -> int:
    if not os.environ.get("REX_SESSION"):
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SubagentStart",
                    "additionalContext": RULE,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
