#!/usr/bin/env python3
"""Run a small swarm of OpenCode workers on any model OpenCode can reach.

OpenCode reaches models through its providers: OpenCode Zen (free and paid),
OpenCode Go, GitHub Copilot, OpenAI, local Ollama, and others the user
connected. This script treats them all the same way. It supports OpenCode 2.x
(npm ``@opencode/cli``) and 1.x (npm ``opencode-ai``). Each run starts its own
server (``--standalone`` on 2.x, ``--pure`` on 1.x), so the worker policy
below reaches it and parallel runs share no server.

``models`` prints one JSON line per active model that can call tools:
``model``, ``provider``, ``free`` (input and output cost 0), ``stealth``, and
``variants`` (its effort levels). ``--free`` keeps only the free ones. A
stealth model is a free OpenCode Zen model under a code name: it has no model
family and no version number in its ID, such as ``cat-jam-free``.

``prefs`` shows or sets the user's model pool, kept per user in
``$XDG_CONFIG_HOME/swe/opencode.json`` (default ``~/.config``). It never
writes OpenCode's own config.

``run`` reads a task file (see ``workers.py``) and runs one
``opencode run --format json`` per task, at most ``--parallel`` at a time.
A model is ``provider/model``. A task without ``model`` takes the
next model from the pool in turn, and a failed task runs once more on the next
model in the pool, because free models often hit rate limits. The pool is
``--models``, else the user's ``prefs``. With neither, the pool is every live
stealth model, and a failed task falls back to DeepSeek V4.1 Flash, all free.
A paid model runs only when the user names it. A task without ``dir`` runs in
``--dir``.

A task's ``effort`` (or ``--effort``) sets the model's reasoning effort, one
of ``none minimal low medium high xhigh max``. It maps to the model's nearest
variant (``#variant`` on 2.x, ``--variant`` on 1.x). A model with no variants
runs at its default effort.

Workers are read-only by default: they may read, grep, glob, and list, and
every other tool is denied, the 2.x code-mode ``execute`` tool included.
``--edit`` also allows file edits and writes, and then every task needs its own
``dir``, such as a git worktree. Shell, web, and nested subagents stay denied
in both modes. This is OpenCode's own permission config, not an OS sandbox.

``run`` prints the result line from ``workers.py`` per task; ``effort`` is the
variant used, or null. ``--out DIR`` also keeps each attempt's raw event
stream as ``DIR/<id>.<attempt>.jsonl``.

Usage: python3 opencode_run.py {models,prefs,run} --help
"""

import argparse
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from workers import EFFORTS, load_tasks, nearest, run_all, spawn

READ_TOOLS = ("read", "grep", "glob", "list")
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


def entry(provider: str, model_id: str, costs: list, family: str,
          variants: list) -> dict:
    free = bool(costs) and all(
        c.get("input") == 0 and c.get("output") == 0 for c in costs)
    stealth = (provider == "opencode" and free and not family
               and not re.search(r"\d", model_id))
    return {"model": f"{provider}/{model_id}", "provider": provider, "free": free,
            "stealth": stealth, "variants": variants}


def list_models(opencode: str, major: int) -> list[dict]:
    """Every active model that can call tools, over all connected providers."""
    if major >= 2:
        data = json.loads(output([opencode, "api", "--standalone", "model.list"]))
        return [entry(m["providerID"], m["id"], m.get("cost") or [],
                      m.get("family"), [v["id"] for v in m.get("variants") or []])
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
            models.append(entry(provider, model_id, [info.get("cost", {})],
                                info.get("family"), list(info.get("variants") or {})))
    return models


def prefs_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "swe" / "opencode.json"


def read_prefs() -> dict:
    path = prefs_path()
    return json.loads(path.read_text()) if path.exists() else {}


def model_pool(args, catalog: list[dict]) -> tuple[list[str], str | None]:
    """Return the pool, and the fallback model (None: the next in the pool)."""
    if args.models:
        return args.models.split(","), None
    saved = read_prefs().get("models")
    if saved:
        return saved, None
    stealth = [m["model"] for m in catalog if m["stealth"]]
    return stealth or [FALLBACK_MODEL], FALLBACK_MODEL


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
    level = nearest(task.get("effort") or args.effort,
                    args.variants.get(model, []))
    if args.major >= 2:
        cmd = [args.opencode, "run", "--standalone", "--format", "json",
               "-m", f"{model}#{level}" if level else model]
    else:
        cmd = [args.opencode, "run", "--pure", "--format", "json", "-m", model]
        if level:
            cmd += ["--variant", level]
    for f in task.get("files", []):
        cmd += ["-f", f]
    cmd += ["--", task["prompt"]]
    proc = spawn(cmd, task.get("dir", args.dir), child_env(args.edit), args.timeout)
    stdout, stderr = proc["stdout"], proc["stderr"]
    status = "timeout" if proc["timed_out"] else None
    if args.out:
        (args.out / f"{task['id']}.{n}.jsonl").write_text(stdout)
    text, error, session = parse_events(stdout)
    if status is None:
        status = "ok" if proc["exit"] == 0 and not error and text else "error"
    if status == "timeout" and not error:
        error = f"no answer after {args.timeout}s" + ("" if stdout else ", no events")
    if status == "error" and not error:
        error = stderr.strip()[-2000:] or "no answer"
    return {"id": task["id"], "model": model, "effort": level, "status": status,
            "exit": proc["exit"], "seconds": proc["seconds"],
            "text": text, "error": error, "session": session}


def run_task(args, task: dict, model: str, fallback: str) -> dict:
    result = attempt(args, task, model, 1)
    tried = [result["model"]]
    if result["status"] != "ok" and fallback != model:
        result = attempt(args, task, fallback, 2)
        tried.append(fallback)
    result["attempts"] = tried
    return result


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
    catalog = list_models(args.opencode, args.major)
    args.variants = {m["model"]: m["variants"] for m in catalog}
    pool, fallback = model_pool(args, catalog)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
    turn = itertools.cycle(range(len(pool)))
    plans = []
    for task in tasks:
        i = next(turn)
        model = task.get("model") or pool[i]
        plans.append((task, model, fallback or pool[(i + 1) % len(pool)]))
    run_all(plans, lambda plan: run_task(args, *plan), args.parallel)


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
    run.add_argument("--effort", choices=EFFORTS,
                     help="reasoning effort for tasks without their own")
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
