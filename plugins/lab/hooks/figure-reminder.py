"""Remind the agent once per session to load making-plots when it touches figure work."""

import json
import re
import sys
import tempfile
from pathlib import Path

FIGURE_WORDS = re.compile(
    r"\b(matplotlib|seaborn|plotnine|plots?|plotting|figures?|visuali[sz]ations?|savefig)\b",
    re.IGNORECASE,
)
REMINDER = (
    "This step touches a result figure, a results table, or plotting code. "
    "Load the lab:making-plots skill now, before you change or accept this output. "
    "A brief that hands figure work to a subagent names that skill and tells the worker to load it first."
)


def figure_work(event):
    tool = event.get("tool_name")
    data = event.get("tool_input") or {}
    if tool == "Bash":
        return bool(FIGURE_WORDS.search(data.get("command", "")))
    if tool in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
        path = data.get("file_path") or data.get("notebook_path") or ""
        return path.endswith(".png") or bool(
            FIGURE_WORDS.search(Path(path).as_posix().replace("_", " "))
        )
    return False


def already_loaded(event):
    transcript = event.get("transcript_path")
    try:
        return "skills/making-plots" in Path(transcript).read_text(
            encoding="utf-8", errors="ignore"
        )
    except (OSError, TypeError):
        return False


def main():
    event = json.load(sys.stdin)
    if not figure_work(event):
        return
    marker = (
        Path(tempfile.gettempdir())
        / f"lab-figure-reminder-{event.get('session_id', 'unknown')}"
    )
    if marker.exists() or already_loaded(event):
        return
    marker.touch()
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event.get("hook_event_name", "PostToolUse"),
                    "additionalContext": REMINDER,
                }
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, TypeError, AttributeError, OSError):
        sys.exit(0)
