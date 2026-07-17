"""Prove the Stop hook (spec 0014 behavior 4): runs `qmd update -c llmos`
exactly once when the PostToolUse stamp hook left the session dirty, not at
all when it did not, and clears the flag either way. `qmd` is stubbed on
PATH -- these tests never invoke the real binary.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "hooks" / "llmos_qmd_hook.py"


def make_qmd_stub(bin_dir: Path, call_log: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "qmd"
    stub.write_text(f'#!/bin/sh\necho "$@" >> "{call_log}"\n')
    stub.chmod(0o755)


def flag_path(tmp_path: Path, session_id: str) -> Path:
    return tmp_path / "scratch" / "llmos-hooks" / session_id / "llmos.dirty"


def run_hook(payload: dict, tmp_path: Path, path_env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        env={"PATH": path_env, "TMPDIR": str(tmp_path / "scratch")},
        text=True,
        capture_output=True,
        timeout=10,
    )


def test_runs_qmd_update_when_dirty(tmp_path):
    call_log = tmp_path / "calls.log"
    bin_dir = tmp_path / "bin"
    make_qmd_stub(bin_dir, call_log)
    flag = flag_path(tmp_path, "sess-1")
    flag.parent.mkdir(parents=True)
    flag.touch()

    result = run_hook({"session_id": "sess-1"}, tmp_path, f"{bin_dir}:/usr/bin:/bin")

    assert result.returncode == 0
    assert call_log.read_text().strip() == "update -c llmos"


def test_clears_flag_after_running(tmp_path):
    call_log = tmp_path / "calls.log"
    bin_dir = tmp_path / "bin"
    make_qmd_stub(bin_dir, call_log)
    flag = flag_path(tmp_path, "sess-1")
    flag.parent.mkdir(parents=True)
    flag.touch()

    run_hook({"session_id": "sess-1"}, tmp_path, f"{bin_dir}:/usr/bin:/bin")

    assert not flag.exists()


def test_no_qmd_process_when_flag_absent(tmp_path):
    call_log = tmp_path / "calls.log"
    bin_dir = tmp_path / "bin"
    make_qmd_stub(bin_dir, call_log)

    result = run_hook({"session_id": "sess-1"}, tmp_path, f"{bin_dir}:/usr/bin:/bin")

    assert result.returncode == 0
    assert not call_log.exists()


def test_non_blocking_and_flag_cleared_when_qmd_missing(tmp_path):
    flag = flag_path(tmp_path, "sess-1")
    flag.parent.mkdir(parents=True)
    flag.touch()

    result = run_hook({"session_id": "sess-1"}, tmp_path, "/usr/bin:/bin")

    assert result.returncode == 0
    assert not flag.exists()
