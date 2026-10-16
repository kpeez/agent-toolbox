#!/usr/bin/env python3
"""Run a small swarm of OpenCode workers on any model OpenCode can reach.

OpenCode reaches models through its providers: OpenCode Zen (free and paid),
OpenCode Go, GitHub Copilot, OpenAI, local Ollama, and others the user
connected. This script treats them all the same way. It supports OpenCode 2.x
(npm ``@opencode/cli``) and 1.x (npm ``opencode-ai``). Each run starts its own
server (``--standalone`` on 2.x, ``--pure`` on 1.x), so the worker policy
below reaches it and parallel runs share no server.

``models`` prints one JSON line per active model that can call tools:
``model``, ``provider``, and ``free`` (input and output cost 0). ``--free``
keeps only the free ones.

``prefs`` shows or sets the user's model pool, kept per user in
``$XDG_CONFIG_HOME/swe/opencode.json`` (default ``~/.config``). It never
writes OpenCode's own config.

``run`` reads a JSON list of tasks and runs one ``opencode run --format json``
per task, at most ``--parallel`` at a time. Each task is an object:

    {"id": "auth-review", "prompt": "...", "model": "provider/model",
     "dir": "/abs/worktree", "files": ["/abs/file"]}

Only ``id`` and ``prompt`` are required. A task without ``model`` takes the
next model from the pool in turn, and a failed task runs once more on the next
model in the pool, because free models often hit rate limits. The pool is
``--models``, else the user's ``prefs``. With neither, every task runs on the
OpenCode Zen stealth model and falls back to DeepSeek V4.1 Flash, both free. A
paid model runs only when the user names it. A task without ``dir`` runs in
``--dir``.

Workers are read-only by default: they may read, grep, glob, and list, and
every other tool is denied, the 2.x code-mode ``execute`` tool included.
``--edit`` also allows file edits and writes, and then every task needs its own
``dir``, such as a git worktree. Shell, web, and nested subagents stay denied
in both modes. This is OpenCode's own permission config, not an OS sandbox.

``run`` prints one JSON line per task: ``id``, ``model``, ``status`` (``ok``,
``error``, or ``timeout``), ``exit``, ``seconds``, ``attempts``, ``text`` (the
worker's final answer), ``error``, and ``session``. ``--out DIR`` also keeps
each attempt's raw event stream as ``DIR/<id>.<attempt>.jsonl``.

Usage: python3 opencode_run.py {models,prefs,run} --help
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
DEFAULT_MODEL = "opencode/big-pickle"  # the OpenCode Zen stealth model
FALLBACK_MODEL = "opencode/deepseek-v4.1-flash-free"


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


def major_version(opencode: str) -> int:
    out = subprocess.run([opencode, "--version"], capture_output=True,
                         text=True, check=True).stdout
    return int(re.search(r"(\d+)\.\d+", out).group(1))


def output(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=True,
                          stdin=subprocess.DEVNULL).stdout


def entry(provider: str, model_id: str, costs: list) -> dict:
    free = bool(costs) and all(
        c.get("input") == 0 and c.get("output") == 0 for c in costs)
    return {"model": f"{provider}/{model_id}", "provider": provider, "free": free}


def list_models(opencode: str, major: int) -> list[dict]:
    """Every active model that can call tools, over all connected providers."""
    if major >= 2:
        data = json.loads(output([opencode, "api", "--standalone", "model.list"]))
        return [entry(m["providerID"], m["id"], m.get("cost") or [])
                for m in data["data"]
                if m.get("enabled", True) and m.get("status", "active") == "active"
                and m.get("capabilities", {}).get("tools")]
    out = output([opencode, "models", "--verbose"])
    models = []
    for name, body in re.findall(r"^(\S+/\S+)\n(\{.*?^\})", out, re.M | re.S):
        info = json.loads(body)
        if (info.get("status", "active") == "active"
                and info.get("capabilities", {}).get("toolcall")):
            provider, model_id = name.split("/", 1)
            models.append(entry(provider, model_id, [info.get("cost", {})]))
    return models


def prefs_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "swe" / "opencode.json"


def read_prefs() -> dict:
    path = prefs_path()
    return json.loads(path.read_text()) if path.exists() else {}


def model_pool(args) -> tuple[list[str], bool]:
    """Return the pool, and whether tasks take its models in turn."""
    if args.models:
        return args.models.split(","), True
    saved = read_prefs().get("models")
    if saved:
        return saved, True
    return [DEFAULT_MODEL, FALLBACK_MODEL], False


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
            error = (err.get("data", {}).get("message") or err.get("message")
                     or err.get("name") or line)
    return (texts[-1] if texts else ""), error, session


def attempt(args, task: dict, model: str, n: int) -> dict:
    server = "--standalone" if args.major >= 2 else "--pure"
    cmd = [args.opencode, "run", server, "--format", "json", "-m", model]
    for f in task.get("files", []):
        cmd += ["-f", f]
    cmd += ["--", task["prompt"]]
    start = time.monotonic()
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True, env=child_env(args.edit),
                            cwd=task.get("dir", args.dir), start_new_session=True)
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
    if status == "timeout" and not error:
        error = f"no answer after {args.timeout}s" + ("" if stdout else ", no events")
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
    for model in list_models(args.opencode, args.major):
        if model["free"] or not args.free:
            print(json.dumps(model))


def cmd_prefs(args) -> None:
    prefs = read_prefs()
    if args.models is not None:
        wanted = [m for m in args.models.split(",") if m]
        known = {m["model"] for m in list_models(args.opencode, args.major)}
        unknown = [m for m in wanted if m not in known]
        if unknown:
            sys.exit(f"not a tool-capable model OpenCode can reach: {', '.join(unknown)}")
        prefs["models"] = wanted
        prefs_path().parent.mkdir(parents=True, exist_ok=True)
        prefs_path().write_text(json.dumps(prefs, indent=2) + "\n")
    print(json.dumps({"path": str(prefs_path()), **prefs}))


def cmd_run(args) -> None:
    tasks = load_tasks(args.tasks, args.edit)
    pool, rotate = model_pool(args)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
    turn = itertools.cycle(range(len(pool)) if rotate else [0])
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
    models = sub.add_parser("models", help="list the models that can call tools")
    models.add_argument("--free", action="store_true", help="only free models")
    prefs = sub.add_parser("prefs", help="show or set this user's model pool")
    prefs.add_argument("--models",
                       help="comma-separated pool to save; empty clears it")
    run = sub.add_parser("run", help="run a JSON list of tasks in parallel")
    run.add_argument("tasks", help="path to the JSON task list, or - for stdin")
    run.add_argument("--dir", default=os.getcwd(),
                     help="directory for tasks without their own dir")
    run.add_argument("--models", help="comma-separated pool; overrides prefs")
    run.add_argument("--parallel", type=int, default=4)
    run.add_argument("--timeout", type=int, default=600,
                     help="seconds per attempt (default: 600)")
    run.add_argument("--edit", action="store_true",
                     help="allow file edits; every task needs its own dir")
    run.add_argument("--out", type=Path, help="keep raw event streams here")
    args = parser.parse_args()
    if not shutil.which(args.opencode):
        sys.exit(f"{args.opencode} not found; install @opencode/cli or opencode-ai")
    args.major = major_version(args.opencode)
    if args.command == "models":
        cmd_models(args)
    elif args.command == "prefs":
        cmd_prefs(args)
    else:
        args.dir = os.path.abspath(args.dir)
        cmd_run(args)


if __name__ == "__main__":
    main()
