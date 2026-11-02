#!/usr/bin/env python3
"""Run a small swarm of Antigravity CLI (``agy``) workers in headless mode.

``models`` prints one JSON line per model slug that ``agy models`` lists:
``model``, ``name``, ``base`` (the slug without its effort suffix), and
``effort``.

``run`` reads a task file (see ``workers.py``) and runs one
``agy --print --output-format json`` per task, at most ``--parallel`` at a
time. A task without ``model`` takes the next model from ``--models`` in turn,
or agy's own default model when ``--models`` is not set. A failed task runs
once more on the next model in ``--models``.

A task's ``effort`` (or ``--effort``) picks the model slug with the nearest
effort suffix, such as ``gemini-3.8-flash-high``. With no model, it becomes
``--effort``.

agy reports a denied tool, a print timeout, and an empty answer with exit 0
and status ``SUCCESS``. The result line reads them from the envelope:
``timeout`` for ``finished_reason: print_timeout``, ``error`` for an empty
answer, and the ``denied_actions`` in ``error``.

Workers are read-only by default. Headless agy auto-denies every tool that
needs approval, and ``--settings`` adds deny rules for writes, commands, web,
and MCP for the run only. ``--edit`` runs in ``accept-edits`` mode with writes
allowed, and then every task needs its own ``dir``. Commands, web, and MCP
stay denied in both modes. This is agy's permission engine, not an OS
sandbox.

``--out DIR`` keeps each attempt's envelope as ``DIR/<id>.<attempt>.json``.

Usage: python3 agy_run.py {models,run} --help
"""

import argparse
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from workers import EFFORTS, load_tasks, nearest, run_all, spawn

LEVELS = ("low", "medium", "high", "xhigh", "max")
DENY = ["command(*)", "read_url(*)", "execute_url(*)", "mcp(*)"]
READ_ONLY_NOTE = ("You are a read-only worker. Use only file read, list, and "
                  "search tools. Do not run shell commands, write files, or "
                  "browse the web. End with your answer as plain text.")


def list_models(agy: str) -> list[dict]:
    out = subprocess.run([agy, "models"], capture_output=True, text=True,
                         check=True, stdin=subprocess.DEVNULL).stdout
    models = []
    for line in out.splitlines():
        slug, _, name = line.partition("\t")
        if not slug.strip():
            continue
        base, _, level = slug.strip().rpartition("-")
        if level not in LEVELS:
            base, level = slug.strip(), None
        models.append({"model": slug.strip(), "name": name.strip(),
                       "base": base, "effort": level})
    return models


def resolve(model: str | None, effort: str | None,
            catalog: list[dict]) -> tuple[str | None, str | None]:
    """Return the model slug and the --effort value for one attempt."""
    if not effort:
        return model, None
    if not model:
        return None, nearest(effort, list(LEVELS))
    entry = next((m for m in catalog if m["model"] == model), None)
    base = entry["base"] if entry else model
    levels = {m["effort"]: m["model"] for m in catalog
              if m["base"] == base and m["effort"]}
    level = nearest(effort, list(levels))
    return (levels[level] if level else model), None


def run_settings(edit: bool, task_dir: str) -> str:
    deny = DENY if edit else DENY + ["write_file(*)"]
    settings = {"toolPermission": "request-review",
                "permissions": {"deny": deny}}
    if edit:
        settings["permissions"]["allow"] = [f"write_file({task_dir})"]
    return json.dumps(settings)


def attempt(args, task: dict, model: str | None, n: int) -> dict:
    slug, effort = resolve(model, task.get("effort") or args.effort, args.catalog)
    task_dir = task.get("dir", args.dir)
    prompt = task["prompt"] if args.edit else f"{READ_ONLY_NOTE}\n\n{task['prompt']}"
    if task.get("files"):
        prompt += "\n\nRead these files first:\n" + "\n".join(task["files"])
    cmd = [args.agy, f"--print={prompt}", "--output-format", "json",
           "--print-timeout", f"{args.timeout}s", "--disable-slash-commands",
           "--settings", run_settings(args.edit, task_dir)]
    if args.edit:
        cmd += ["--mode", "accept-edits"]
    if slug:
        cmd += ["--model", slug]
    if effort:
        cmd += ["--effort", effort]
    for parent in sorted({str(Path(f).parent) for f in task.get("files", [])}):
        cmd += ["--add-dir", parent]
    proc = spawn(cmd, task_dir, dict(os.environ), args.timeout + 60)
    if args.out:
        (args.out / f"{task['id']}.{n}.json").write_text(proc["stdout"])
    try:
        envelope = json.loads(proc["stdout"].strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        envelope = {}
    text = envelope.get("response", "").strip()
    denied = [d.get("action") for d in envelope.get("denied_actions") or []]
    error = envelope.get("error", "")
    if denied:
        error = (error + "; " if error else "") + "denied: " + ", ".join(denied)
    if proc["timed_out"] or envelope.get("finished_reason") == "print_timeout":
        status = "timeout"
        error = error or f"no answer after {args.timeout}s"
    elif proc["exit"] == 0 and envelope.get("status") == "SUCCESS" and text:
        status = "ok"
    else:
        status = "error"
        error = error or proc["stderr"].strip()[-2000:] or "no answer"
    suffix = (slug or "").rpartition("-")[2]
    return {"id": task["id"], "model": slug or "default",
            "effort": effort or (suffix if suffix in LEVELS else None),
            "status": status, "exit": proc["exit"], "seconds": proc["seconds"],
            "text": text, "error": error,
            "session": envelope.get("conversation_id", "")}


def run_task(args, task: dict, model: str | None, fallback: str | None) -> dict:
    result = attempt(args, task, model, 1)
    tried = [result["model"]]
    if result["status"] != "ok" and fallback and fallback != model:
        result = attempt(args, task, fallback, 2)
        tried.append(result["model"])
    result["attempts"] = tried
    return result


def cmd_models(args) -> None:
    for model in list_models(args.agy):
        print(json.dumps(model))


def cmd_run(args) -> None:
    tasks = load_tasks(args.tasks, args.edit)
    pool = args.models.split(",") if args.models else [None]
    needs_catalog = args.effort or any(t.get("effort") for t in tasks)
    args.catalog = list_models(args.agy) if needs_catalog else []
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
    turn = itertools.cycle(range(len(pool)))
    plans = []
    for task in tasks:
        i = next(turn)
        model = task.get("model") or pool[i]
        plans.append((task, model, pool[(i + 1) % len(pool)]))
    run_all(plans, lambda plan: run_task(args, *plan), args.parallel)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--agy", default="agy",
                        help="Antigravity CLI executable (default: agy)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("models", help="list the model slugs agy can use")
    run = sub.add_parser("run", help="run a JSON list of tasks in parallel")
    run.add_argument("tasks", help="path to the JSON task list, or - for stdin")
    run.add_argument("--dir", default=os.getcwd(),
                     help="directory for tasks without their own dir")
    run.add_argument("--models", help="comma-separated model slugs to rotate")
    run.add_argument("--effort", choices=EFFORTS,
                     help="reasoning effort for tasks without their own")
    run.add_argument("--parallel", type=int, default=4)
    run.add_argument("--timeout", type=int, default=600,
                     help="seconds per attempt (default: 600)")
    run.add_argument("--edit", action="store_true",
                     help="allow file edits; every task needs its own dir")
    run.add_argument("--out", type=Path, help="keep raw envelopes here")
    args = parser.parse_args()
    if not shutil.which(args.agy):
        sys.exit(f"{args.agy} not found; install the Antigravity CLI")
    if args.command == "models":
        cmd_models(args)
    else:
        args.dir = os.path.abspath(args.dir)
        cmd_run(args)


if __name__ == "__main__":
    main()
