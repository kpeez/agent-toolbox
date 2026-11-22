#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Score the delegation arm from kept `run_eval.py` runs. See delegation-arm.md for the metric definitions.

    uv run evals/skills/delegation_metrics.py base=OUT_BASE head=OUT_HEAD [--json FILE]

Each LABEL=OUT folder is one SHA. A run counts when run.json has ended_at, no api_error, no error, and no
session violation. Every other run is listed under `excluded`.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import skill_eval as se
from run_eval import wilson

# Cases whose request forbids a source edit. Every other case asks for one.
NO_EDIT_CASES = ("IM-07", "IM-08", "IM-09")
EDIT_TOOLS = ("Edit", "Write", "NotebookEdit")


def jsonl(path):
    return [
        json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()
    ]


def root_edits(transcript):
    return sum(
        1
        for row in transcript
        if row.get("type") == "assistant" and not row.get("isSidechain")
        for block in row["message"]["content"]
        if block.get("type") == "tool_use" and block["name"] in EDIT_TOOLS
    )


def agent_spawns(transcript):
    return sum(
        1
        for row in transcript
        if row.get("type") == "assistant" and not row.get("isSidechain")
        for block in row["message"]["content"]
        if block.get("type") == "tool_use"
        and block["name"] in ("Agent", "Task")
    )


def total_tokens(stream):
    result = [e for e in stream if e.get("type") == "result"][-1]
    return sum(
        usage[key]
        for usage in result["modelUsage"].values()
        for key in (
            "inputTokens",
            "outputTokens",
            "cacheReadInputTokens",
            "cacheCreationInputTokens",
        )
    )


def is_source(name):
    path = Path(name)
    return not (
        path.name.startswith("test_")
        or path.name == "README.md"
        or "__pycache__" in path.parts
        or ".git" in path.parts
    )


def source_changed(run, case, corpus_path):
    """True when a non-test, non-README file differs from the fixture, or is new, in the final working folder."""
    root = se.fixtures_root(corpus_path) / case["fixture"]
    fixture = {
        str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }
    workspace = run / "workspace"
    final = {
        str(p.relative_to(workspace)): p.read_bytes()
        for p in workspace.rglob("*")
        if p.is_file()
    }
    return any(
        is_source(name) and fixture.get(name) != data for name, data in final.items()
    )


def score_run(run, case_id, case, corpus_path):
    record = json.loads((run / "run.json").read_text())
    stream = jsonl(run / "kept" / "stream.jsonl")
    result = [e for e in stream if e.get("type") == "result"][-1]
    transcript = jsonl(run / "kept" / "transcript.jsonl")
    ok = result.get("subtype") == "success" and not result.get("is_error")
    changed = source_changed(run, case, corpus_path)
    wants_edit = case_id not in NO_EDIT_CASES
    return {
        "case": case_id,
        "repeat": run.name,
        "wants_edit": wants_edit,
        "root_edits": root_edits(transcript),
        "agent_spawns": agent_spawns(transcript),
        "task_done": ok and changed == wants_edit,
        "total_tokens": total_tokens(stream),
        "cost_usd": record.get("cost") or result.get("total_cost_usd"),
    }


def collect(out, corpus, corpus_path):
    scored, excluded = [], []
    for run in sorted((out / "runs").glob("*/*/r*")):
        case_id = run.parent.parent.name
        record = (
            json.loads((run / "run.json").read_text())
            if (run / "run.json").is_file()
            else {}
        )
        if (
            not record.get("ended_at")
            or record.get("api_error")
            or record.get("error")
            or record.get("violations")
        ):
            excluded.append(f"{case_id}/{run.name}")
            continue
        scored.append(score_run(run, case_id, corpus[case_id], corpus_path))
    return scored, excluded


def share(rows, key):
    k = sum(1 for r in rows if r[key])
    n = len(rows)
    ci = wilson(k, n)
    return {"k": k, "n": n, "share": k / n if n else None, "wilson95": ci and [ci["low"], ci["high"]]}


def summarize(rows):
    tokens = [r["total_tokens"] for r in rows]
    costs = [r["cost_usd"] or 0 for r in rows]
    return {
        "runs": len(rows),
        "root_thread_edit_calls_per_run": statistics.mean(r["root_edits"] for r in rows)
        if rows
        else None,
        "runs_with_a_root_thread_edit": share(
            [{**r, "x": r["root_edits"] > 0} for r in rows], "x"
        ),
        "runs_with_an_agent_spawn": share(
            [{**r, "x": r["agent_spawns"] > 0} for r in rows], "x"
        ),
        "task_done": share(rows, "task_done"),
        "total_tokens_mean": statistics.mean(tokens) if rows else None,
        "total_tokens_median": statistics.median(tokens) if rows else None,
        "total_tokens_sd": statistics.stdev(tokens) if len(rows) > 1 else None,
        "cost_usd_total": sum(costs),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outs", nargs="+", metavar="LABEL=OUT")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--corpus", type=Path, default=se.DATASET)
    args = parser.parse_args()
    corpus = {c["id"]: c for c in se.corpus(args.corpus)}
    report = {}
    for item in args.outs:
        label, out = item.split("=", 1)
        rows, excluded = collect(Path(out), corpus, args.corpus)
        report[label] = {
            "excluded": excluded,
            "all_cases": summarize(rows),
            "edit_cases": summarize([r for r in rows if r["wants_edit"]]),
            "no_edit_cases": summarize([r for r in rows if not r["wants_edit"]]),
            "runs": rows,
        }
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.json:
        args.json.write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
