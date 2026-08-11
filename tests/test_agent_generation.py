"""The committed provider adapters must stay derived from roles.json."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "plugins" / "swe" / "scripts" / "generate_agents.py"


def test_committed_adapters_match_regeneration() -> None:
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_check_rejects_a_hand_edited_adapter() -> None:
    adapter = ROOT / "plugins" / "swe" / "agents" / "explorer.md"
    original = adapter.read_text()
    adapter.write_text(original + "\nhand edit\n")
    try:
        result = subprocess.run(
            [sys.executable, str(GENERATOR), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
    finally:
        adapter.write_text(original)

    assert result.returncode != 0
