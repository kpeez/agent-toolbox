#!/usr/bin/env python3
"""Append-only ledger for autoresearch runs.

Two verbs, no update or delete:

  ledger.py append RUN_DIR --commit SHA --status keep|discard|crash \
      --description TEXT [--metric KEY=VALUE ...]
  ledger.py render RUN_DIR

`append` assigns the next experiment id, appends one JSON line to
RUN_DIR/results.jsonl, and regenerates RUN_DIR/summary.md. `render`
regenerates the summary alone. Metric semantics stay in the run's program;
this script treats metrics as opaque key-value pairs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

STATUSES = ("keep", "discard", "crash")


def read_ledger(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "results.jsonl"
    if not path.exists():
        return []
    records = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise SystemExit(f"corrupt ledger line {number}: {error}")
    return records


def parse_metric(pair: str) -> tuple[str, Any]:
    key, separator, raw = pair.partition("=")
    if not key or not separator:
        raise SystemExit(f"metric must be KEY=VALUE, got {pair!r}")
    if raw == "null":
        return key, None
    for cast in (int, float):
        try:
            return key, cast(raw)
        except ValueError:
            continue
    return key, raw


def cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def render(run_dir: Path) -> None:
    records = read_ledger(run_dir)
    metric_keys: list[str] = []
    for record in records:
        for key in record.get("metrics") or {}:
            if key not in metric_keys:
                metric_keys.append(key)
    best_id = None
    for record in records:
        if record.get("status") == "keep":
            best_id = record.get("id")
    header = ["id", "commit", "status", *metric_keys, "description"]
    lines = [
        "# Autoresearch results",
        "",
        "Generated from `results.jsonl`; the ledger is the source of truth.",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
    ]
    for record in records:
        metrics = record.get("metrics") or {}
        marker = " ← best" if record.get("id") == best_id else ""
        row = [
            f"{record.get('id')}{marker}",
            cell(record.get("commit")),
            cell(record.get("status")),
            *[cell(metrics.get(key)) for key in metric_keys],
            cell(record.get("description")),
        ]
        lines.append("| " + " | ".join(row) + " |")
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n")


def append(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        raise SystemExit(f"run directory not found: {run_dir}")
    if args.status not in STATUSES:
        raise SystemExit(f"status must be one of {', '.join(STATUSES)}")
    records = read_ledger(run_dir)
    next_id = records[-1]["id"] + 1 if records else 0
    record = {
        "id": next_id,
        "commit": args.commit,
        "status": args.status,
        "description": args.description,
        "metrics": dict(parse_metric(pair) for pair in args.metric),
    }
    with (run_dir / "results.jsonl").open("a") as ledger:
        ledger.write(json.dumps(record) + "\n")
    render(run_dir)
    print(json.dumps(record))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    verbs = parser.add_subparsers(dest="verb", required=True)
    appender = verbs.add_parser("append")
    appender.add_argument("run_dir")
    appender.add_argument("--commit", required=True)
    appender.add_argument("--status", required=True)
    appender.add_argument("--description", required=True)
    appender.add_argument("--metric", action="append", default=[])
    renderer = verbs.add_parser("render")
    renderer.add_argument("run_dir")
    args = parser.parse_args()
    if args.verb == "append":
        append(args)
    else:
        render(Path(args.run_dir))


if __name__ == "__main__":
    main()
