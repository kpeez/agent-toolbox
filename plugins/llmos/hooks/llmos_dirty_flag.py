"""Shared dirty-flag contract between the PostToolUse stamp hook
(`llmos_stamp_hook.py`) and the Stop qmd-reindex hook (`llmos_qmd_hook.py`):
a touch-file under a session-scoped scratch dir, keyed by qmd collection
name. Scoping by the hook payload's own `session_id` keeps concurrent
sessions from colliding or leaking a stale flag into each other.
"""

from __future__ import annotations

import tempfile
from pathlib import Path


def flag_path(session_id: str, collection: str) -> Path:
    scratch = Path(tempfile.gettempdir()) / "llmos-hooks" / session_id
    scratch.mkdir(parents=True, exist_ok=True)
    return scratch / f"{collection}.dirty"
