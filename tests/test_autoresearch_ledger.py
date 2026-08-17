"""The autoresearch ledger must append immutably and render faithfully."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "plugins/lab/skills/autoresearch/scripts/ledger.py"


def run_ledger(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LEDGER), *args],
        capture_output=True,
        text=True,
    )


def append(run_dir: Path, **overrides: str) -> subprocess.CompletedProcess[str]:
    options = {
        "commit": "a1b2c3d",
        "status": "keep",
        "description": "baseline",
    } | overrides
    args = ["append", str(run_dir)]
    for key, value in options.items():
        if key == "metric":
            args.extend(f"--metric={pair}" for pair in value.split())
        else:
            args.append(f"--{key}={value}")
    return run_ledger(*args)


def test_appends_are_immutable_and_ids_monotonic(tmp_path: Path) -> None:
    assert append(tmp_path, metric="val_bpb=0.9979").returncode == 0
    first = (tmp_path / "results.jsonl").read_bytes()

    assert append(tmp_path, status="discard", metric="val_bpb=1.01").returncode == 0
    ledger = (tmp_path / "results.jsonl").read_bytes()

    assert ledger.startswith(first)
    ids = [json.loads(line)["id"] for line in ledger.decode().splitlines()]
    assert ids == [0, 1]


def test_descriptions_and_metric_values_round_trip(tmp_path: Path) -> None:
    description = 'quotes " and | pipes\tand tabs'
    append(tmp_path, description=description, metric="lr=0.04 note=warmup vram=null")

    record = json.loads((tmp_path / "results.jsonl").read_text())

    assert record["description"] == description
    assert record["metrics"] == {"lr": 0.04, "note": "warmup", "vram": None}


def test_invalid_status_is_rejected_without_writing(tmp_path: Path) -> None:
    result = append(tmp_path, status="inconclusive")

    assert result.returncode != 0
    assert not (tmp_path / "results.jsonl").exists()


def test_render_marks_the_last_keep_as_best(tmp_path: Path) -> None:
    append(tmp_path, metric="val_bpb=0.9979")
    append(tmp_path, status="discard", description="worse", metric="val_bpb=1.01")
    append(tmp_path, status="keep", description="better", metric="val_bpb=0.98")
    append(tmp_path, status="crash", description="oom", metric="val_bpb=null")

    summary = (tmp_path / "summary.md").read_text()

    assert "| 2 ← best |" in summary
    assert summary.count("← best") == 1
    assert "val_bpb" in summary and "oom" in summary


def test_corrupt_ledger_stops_instead_of_guessing(tmp_path: Path) -> None:
    (tmp_path / "results.jsonl").write_text("not json\n")

    result = append(tmp_path)

    assert result.returncode != 0
    assert "corrupt ledger line 1" in result.stderr
