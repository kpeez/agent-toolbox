"""Task file, effort levels, and the parallel loop that every harness runner shares.

A task file is a JSON list of objects:

    {"id": "auth-review", "prompt": "...", "model": "...", "effort": "high",
     "dir": "/abs/worktree", "files": ["/abs/file"]}

Only ``id`` and ``prompt`` are required. A runner prints one JSON line per
task: ``id``, ``model``, ``effort``, ``status`` (``ok``, ``error``, or
``timeout``), ``exit``, ``seconds``, ``attempts``, ``text`` (the worker's final
answer), ``error``, and ``session``.
"""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time

EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


def load_tasks(path: str, edit: bool) -> list[dict]:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text()
    tasks = json.loads(raw)
    if not isinstance(tasks, list) or not tasks:
        sys.exit("tasks: expected a non-empty JSON list")
    ids, dirs = set(), set()
    for task in tasks:
        if not isinstance(task, dict) or not task.get("id") or not task.get("prompt"):
            sys.exit(f"tasks: every task needs id and prompt: {task!r}")
        if task.get("effort") not in (None, *EFFORTS):
            sys.exit(f"tasks: effort must be one of {' '.join(EFFORTS)}: {task['id']}")
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


def nearest(effort: str | None, levels: list[str]) -> str | None:
    """The level nearest to the effort, preferring the higher one."""
    known = [v for v in levels if v in EFFORTS]
    if not effort or not known:
        return None
    want = EFFORTS.index(effort)
    return min(known, key=lambda v: (abs(EFFORTS.index(v) - want),
                                     -EFFORTS.index(v)))


def spawn(cmd: list[str], cwd: str, env: dict, timeout: int) -> dict:
    """Run one worker with no stdin; kill its process group on timeout."""
    start = time.monotonic()
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=env, cwd=cwd,
                            start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, stderr = proc.communicate()
        timed_out = True
    return {"stdout": stdout, "stderr": stderr, "exit": proc.returncode,
            "timed_out": timed_out, "seconds": round(time.monotonic() - start, 1)}


def run_all(plans: list, work, parallel: int) -> None:
    """Run work(plan) for each plan, print each result line, exit 1 on any failure."""
    lock = threading.Lock()
    failed = 0

    def one(plan):
        nonlocal failed
        result = work(plan)
        with lock:
            failed += result["status"] != "ok"
            print(json.dumps(result), flush=True)

    with ThreadPoolExecutor(parallel) as executor:
        list(executor.map(one, plans))
    sys.exit(1 if failed else 0)
