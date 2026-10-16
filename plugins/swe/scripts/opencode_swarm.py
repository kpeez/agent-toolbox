#!/usr/bin/env python3
"""Run a small swarm of OpenCode workers on free OpenCode Zen models.

``models`` prints the free Zen models that can call tools: the ``opencode/``
models whose input and output cost is 0 in ``opencode models opencode
--verbose``. The list changes often, so read it live before each swarm.

``run`` reads a JSON list of tasks and runs one ``opencode run --format json``
per task, at most ``--parallel`` at a time. Each task is an object:

    {"id": "auth-review", "prompt": "...", "model": "opencode/...",
     "dir": "/abs/worktree", "files": ["/abs/file"]}

Only ``id`` and ``prompt`` are required. A task without ``model`` takes the
next model from ``--models`` (or the live free list) in turn. A task without
``dir`` runs in ``--dir``. A failed task runs once more on the next model in
the pool, because free models often hit rate limits.

Workers are read-only by default: the build agent may read, grep, glob, and
list, and every other tool is denied. ``--edit`` also allows file edits, and
then every task needs its own ``dir``, such as a git worktree. Shell, web,
and nested subagents stay denied in both modes. This is OpenCode's own
permission config, not an OS sandbox.

``run`` prints one JSON line per task: ``id``, ``model``, ``status`` (``ok``,
``error``, or ``timeout``), ``exit``, ``seconds``, ``attempts``, ``text`` (the
worker's final answer), ``error``, and ``session``. ``--out DIR`` also keeps
each attempt's raw event stream as ``DIR/<id>.<attempt>.jsonl``.

Usage: python3 opencode_swarm.py {models,run} --help
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

READ_TOOLS = ("read", "grep", "glob", "list")


def policy(edit: bool) -> dict:
    rules = {"*": "deny", **{tool: "allow" for tool in READ_TOOLS}}
    if edit:
        rules["edit"] = "allow"
    return rules


def child_env(edit: bool) -> dict:
    """Layer the swarm policy over any inherited OPENCODE_CONFIG_CONTENT."""
    env = dict(os.environ)
    config = json.loads(env.get("OPENCODE_CONFIG_CONTENT") or "{}")
    rules = policy(edit)
    config["permission"] = rules
    config["share"] = "disabled"
    agents = config.setdefault("agent", {})
    for name in set(agents) | {"build"}:
        agents.setdefault(name, {})["permission"] = rules
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config)
    return env


def free_models(opencode: str) -> list[str]:
    out = subprocess.run(
        [opencode, "models", "opencode", "--verbose"],
        capture_output=True, text=True, check=True,
    ).stdout
    models = []
    for name, body in re.findall(r"^(opencode/\S+)\n(\{.*?^\})", out, re.M | re.S):
        info = json.loads(body)
        cost = info.get("cost", {})
        if (
            info.get("status", "active") == "active"
            and cost.get("input") == 0
            and cost.get("output") == 0
            and info.get("capabilities", {}).get("toolcall")
        ):
            models.append(name)
    return models


def parse_events(stream: str) -> tuple[str, str, str]:
    """Return the final answer, the first error, and the session id."""
    texts, error, session = [], "", ""
    for line in stream.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        session = session or event.get("sessionID", "")
        if event.get("type") == "text":
            texts.append(event.get("part", {}).get("text", ""))
        elif event.get("type") == "error" and not error:
            err = event.get("error", {})
            error = err.get("data", {}).get("message") or err.get("name") or line
    return (texts[-1] if texts else ""), error, session


def attempt(args, task: dict, model: str, n: int) -> dict:
    cmd = [args.opencode, "run", "--pure", "--format", "json", "--agent", "build",
           "-m", model, "--dir", task.get("dir", args.dir)]
    for f in task.get("files", []):
        cmd += ["-f", f]
    cmd += ["--", task["prompt"]]
    start = time.monotonic()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=child_env(args.edit),
                            start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=args.timeout)
        status = None
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, 9)
        stdout, stderr = proc.communicate()
        status = "timeout"
    if args.out:
        (args.out / f"{task['id']}.{n}.jsonl").write_text(stdout)
    text, error, session = parse_events(stdout)
    if status is None:
        status = "ok" if proc.returncode == 0 and not error and text else "error"
    if status == "error" and not error:
        error = stderr.strip()[-2000:] or "no answer"
    return {"id": task["id"], "model": model, "status": status,
            "exit": proc.returncode, "seconds": round(time.monotonic() - start, 1),
            "text": text, "error": error, "session": session}


def run_task(args, task: dict, model: str, fallback: str) -> dict:
    result = attempt(args, task, model, 1)
    tried = [result["model"]]
    if result["status"] != "ok" and fallback != model:
        result = attempt(args, task, fallback, 2)
        tried.append(fallback)
    result["attempts"] = tried
    return result


def load_tasks(path: str, edit: bool) -> list[dict]:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text()
    tasks = json.loads(raw)
    if not isinstance(tasks, list) or not tasks:
        sys.exit("tasks: expected a non-empty JSON list")
    ids, dirs = set(), set()
    for task in tasks:
        if not isinstance(task, dict) or not task.get("id") or not task.get("prompt"):
            sys.exit(f"tasks: every task needs id and prompt: {task!r}")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", task["id"]) or task["id"] in ids:
            sys.exit(f"tasks: id must be a unique slug: {task['id']!r}")
        ids.add(task["id"])
        if edit:
            if not task.get("dir"):
                sys.exit(f"tasks: --edit needs a dir per task: {task['id']}")
            if task["dir"] in dirs:
                sys.exit(f"tasks: --edit needs a distinct dir per task: {task['dir']}")
            dirs.add(task["dir"])
    return tasks


def cmd_models(args) -> None:
    print("\n".join(free_models(args.opencode)))


def cmd_run(args) -> None:
    tasks = load_tasks(args.tasks, args.edit)
    pool = args.models.split(",") if args.models else free_models(args.opencode)
    if not pool:
        sys.exit("no free OpenCode Zen model found; pass --models")
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
    turn = itertools.cycle(range(len(pool)))
    plans = []
    for task in tasks:
        i = next(turn)
        model = task.get("model") or pool[i]
        plans.append((task, model, pool[(i + 1) % len(pool)]))
    lock = threading.Lock()
    failed = 0

    def work(plan):
        nonlocal failed
        result = run_task(args, *plan)
        with lock:
            failed += result["status"] != "ok"
            print(json.dumps(result), flush=True)

    with ThreadPoolExecutor(args.parallel) as executor:
        list(executor.map(work, plans))
    sys.exit(1 if failed else 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--opencode", default="opencode",
                        help="OpenCode executable (default: opencode)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("models", help="list free Zen models that can call tools")
    run = sub.add_parser("run", help="run a JSON list of tasks in parallel")
    run.add_argument("tasks", help="path to the JSON task list, or - for stdin")
    run.add_argument("--dir", default=os.getcwd(),
                     help="directory for tasks without their own dir")
    run.add_argument("--models", help="comma-separated model pool")
    run.add_argument("--parallel", type=int, default=4)
    run.add_argument("--timeout", type=int, default=600,
                     help="seconds per attempt (default: 600)")
    run.add_argument("--edit", action="store_true",
                     help="allow file edits; every task needs its own dir")
    run.add_argument("--out", type=Path, help="keep raw event streams here")
    args = parser.parse_args()
    if not shutil.which(args.opencode):
        sys.exit(f"{args.opencode} not found; install opencode-ai 1.x")
    if args.command == "models":
        cmd_models(args)
    else:
        args.dir = os.path.abspath(args.dir)
        cmd_run(args)


if __name__ == "__main__":
    main()
