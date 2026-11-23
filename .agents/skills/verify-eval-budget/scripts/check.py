#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Model-check the eval-batch budget in evals/skills/run_eval.py with TLC.

1. TLC checks EvalBudget.tla on EvalBudget.cfg (the current code): every rule holds.
2. Each past-bug variant breaks the rule it targets, so each rule can fail.
3. Replay.cfg is checked again with its state graph saved. In every state, each
   Reserve, Prepare, Release, and Resume step runs on the real run_eval code in a
   temporary --out folder, and the real successors must equal the model's.

Exit 0 only when all three match. TLC and Java come from TLA2TOOLS and JAVA, or
from .github/scripts/statechart_tlc.py (the statechart skill's pins).
"""

import argparse
import functools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
REPO = SKILL.parent.parent.parent
sys.path.insert(0, str(REPO / "evals" / "skills"))
import run_eval

SPEC = SKILL / "EvalBudget.tla"
# name: (InFlight, MoveAside, the rule that must break, the commit that fixed it)
VARIANTS = {
    "in-flight-counter": ("counter", "prepare", "NoFalseStop", "3df0eca"),
    "move-aside-in-prepare": ("active", "prepare", "CapSafe", "9fb690e"),
}
REAL_ACTIONS = ("Reserve", "Prepare", "Release", "Resume")
STOP_USD, COST_USD = 2.0, 1.0  # Stop and Cost in EvalBudget.cfg, read as dollars


@functools.cache
def tools():
    if os.environ.get("TLA2TOOLS") and os.environ.get("JAVA"):
        return os.environ["JAVA"], os.environ["TLA2TOOLS"]
    lines = subprocess.run(
        ["uv", "run", ".github/scripts/statechart_tlc.py"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    found = dict(line.split("=", 1) for line in lines)
    return found["JAVA"], found["TLA2TOOLS"]


def tlc(work, cfg_text, *extra):
    """Run TLC on a copy of the spec in `work`, so no trace file lands in the skill folder."""
    shutil.copy(SPEC, work / SPEC.name)
    (work / "run.cfg").write_text(cfg_text)
    java, jar = tools()
    proc = subprocess.run(
        [
            java,
            "-XX:+UseParallelGC",
            "-cp",
            jar,
            "tlc2.TLC",
            "-workers",
            "auto",
            "-metadir",
            str(work / "meta"),
            "-config",
            "run.cfg",
            *extra,
            SPEC.name,
        ],
        check=False,
        cwd=work,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    if "Invariant" not in out and "No error has been found" not in out:
        sys.exit(f"TLC did not finish:\n{out[-3000:]}")
    broken = re.search(r"Invariant (\w+) is violated", out)
    states = re.findall(r"([\d,]+) distinct states found", out)
    path = re.findall(r"^State \d+: <(\w+)", out, re.MULTILINE)
    return (broken[1] if broken else None), (states[-1] if states else "?"), path


def variant_cfg(in_flight, move_aside, rule):
    cfg = (SKILL / "EvalBudget.cfg").read_text()
    cfg = cfg.replace('InFlight = "active"', f'InFlight = "{in_flight}"')
    cfg = cfg.replace('MoveAside = "reserve"', f'MoveAside = "{move_aside}"')
    return re.sub(r"INVARIANTS .*", f"INVARIANTS {rule}", cfg)


# --- TLC values in the state graph ------------------------------------------

TOKEN = re.compile(r'\s*(:>|@@|[(){},]|"[^"]*"|-?\d+|\w+)')


def parse_value(text):
    tokens = TOKEN.findall(text)
    pos = 0

    def value():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        if tok == "(":
            fn = {}
            while True:
                key = value()
                assert tokens[pos] == ":>"
                pos += 1
                fn[key] = value()
                pos += 1
                if tokens[pos - 1] == ")":
                    return fn
        if tok == "{":
            items = set()
            while tokens[pos] != "}":
                items.add(value())
                if tokens[pos] == ",":
                    pos += 1
            pos += 1
            return frozenset(items)
        if tok.startswith('"'):
            return tok[1:-1]
        if tok in ("TRUE", "FALSE"):
            return tok == "TRUE"
        return int(tok) if re.fullmatch(r"-?\d+", tok) else tok

    return value()


def parse_state(label):
    text = label.replace('\\"', '"').replace("\\\\", "\\")
    state = {}
    for line in text.split("\\n"):
        name, _, rest = line.removeprefix("/\\ ").partition(" = ")
        state[name] = parse_value(rest)
    return state


def state_graph(dot):
    nodes, edges = {}, defaultdict(set)
    for line in dot.read_text().splitlines():
        if m := re.match(r'(-?\d+) \[label="(.*)"(,style = filled)?\];?$', line):
            nodes[m[1]] = parse_state(m[2])
        elif m := re.match(r'(-?\d+) -> (-?\d+) \[label="(\w+)"', line):
            edges[m[1], m[3]].add(m[2])
    return nodes, edges


def key(state, ignore=("falseStop",)):
    def freeze(v):
        return tuple(sorted(v.items())) if isinstance(v, dict) else v

    return tuple(sorted((k, freeze(v)) for k, v in state.items() if k not in ignore))


# --- the real code ----------------------------------------------------------

RECORDS = {
    "started": {"started_at": "t", "cost_usd": None, "error": None},
    "known": {"started_at": "t", "cost_usd": COST_USD, "error": None, "ended_at": "t"},
    "unknown": {
        "started_at": "t",
        "cost_usd": None,
        "error": "no plugin-eval result",
        "ended_at": "t",
    },
    "apiError": {
        "started_at": "t",
        "cost_usd": COST_USD,
        "error": None,
        "ended_at": "t",
        "api_error": "overloaded",
    },
}
REASONS = {
    "budget": "budget: test",
    "cost": "r: cost None is unknown or over $2",
    "errors": "3 runs in a row ended with an error",
}


def item(r):
    return {"case": r, "arm": "hook-on", "repeat": 1}


def build(out, s):
    """Write the folders, stop.json, and Batch memory that model state `s` stands for."""
    for r, status in s["record"].items():
        if status != "none":
            run = run_eval.run_dir(out, item(r))
            run.mkdir(parents=True)
            run_eval.save_json(run / "run.json", {"run": str(run), **RECORDS[status]})
    aside = [COST_USD] * (s["asideKnown"] // int(COST_USD)) + [None] * s["asideUnknown"]
    for n, cost in enumerate(aside):
        (out / "interrupted" / f"old-{n}").mkdir(parents=True)
        run_eval.save_json(
            out / "interrupted" / f"old-{n}" / "run.json", {"cost_usd": cost}
        )
    if s["stop"] != "none":
        run_eval.save_json(out / "stop.json", {"at": "t", "reason": REASONS[s["stop"]]})
    batch = run_eval.Batch(out, {"per_run_stop_usd": STOP_USD}, float(s["cap"]))
    batch.active = {run_eval.run_dir(out, item(r)) for r in s["active"]}
    batch.failures = s["failures"]
    return batch


def observe(out, batch, s):
    """The model state that the folders and Batch memory now stand for."""
    record = {}
    for r in s["record"]:
        path = run_eval.run_dir(out, item(r)) / "run.json"
        rec = json.loads(path.read_text()) if path.is_file() else None
        record[r] = (
            "none"
            if rec is None
            else "started"
            if not rec.get("ended_at")
            else "apiError"
            if rec.get("api_error")
            else "known"
            if rec.get("cost_usd") is not None
            else "unknown"
        )
    known, unknown = 0, 0
    for path in out.glob("interrupted/*/run.json"):
        cost = json.loads(path.read_text()).get("cost_usd")
        known, unknown = (
            (known + int(cost), unknown) if cost is not None else (known, unknown + 1)
        )
    reason = (batch.stop or {}).get("reason", "")
    stop = (
        "none"
        if not batch.stop
        else "budget"
        if reason.startswith("budget")
        else "errors"
        if "in a row" in reason
        else "cost"
    )
    runs = {run_eval.run_dir(out, item(r)): r for r in s["record"]}
    return {
        **s,
        "record": record,
        "asideKnown": known,
        "asideUnknown": unknown,
        "stop": stop,
        "active": frozenset(runs[run] for run in batch.active),
        "failures": batch.failures,
    }


def materialize(args):
    Path(args.output).mkdir(exist_ok=False)


def real_steps(s, action, max_restarts):
    """Each successor of `action` from `s`, run on the real code."""
    run_eval.se.materialize = materialize
    idle = [w for w, pc in s["pc"].items() if pc == "idle"]
    if action == "Reserve":
        params = [(w, r) for w in idle for r in s["todo"]]
    elif action == "Resume":
        params = [()] if s["restarts"] < max_restarts else []
    else:
        want = {"Prepare": "reserved", "Release": "ended"}[action]
        params = [(w,) for w, pc in s["pc"].items() if pc == want]
    for p in params:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            batch = build(out, s)
            pc, job, todo = dict(s["pc"]), dict(s["job"]), s["todo"]
            if action == "Reserve":
                w, r = p
                run = run_eval.run_dir(out, item(r))
                todo = todo - {r}
                if not (run_eval.finished(run) or not batch.reserve(run)):
                    pc[w], job[w] = "reserved", r
            elif action == "Prepare":
                run_eval.prepare(out, item(job[p[0]]), argparse.Namespace(corpus=None, runtime=None))
                pc[p[0]] = "prepared"
            elif action == "Release":
                w = p[0]
                run = run_eval.run_dir(out, item(job[w]))
                rec = json.loads((run / "run.json").read_text())
                if not rec.get(
                    "ended_at"
                ):  # launch raised: execute.one releases a stand-in record
                    rec = {"run": str(run), "cost_usd": None, "error": "runner failed"}
                batch.release(run, rec)
                pc[w], job[w] = "idle", "none"
            else:
                batch = run_eval.Batch(
                    out, {"per_run_stop_usd": STOP_USD}, float(s["cap"])
                )
                pc, job, todo = (
                    {w: "idle" for w in pc},
                    {w: "none" for w in job},
                    frozenset(s["record"]),
                )
            after = observe(out, batch, {**s, "pc": pc, "job": job, "todo": todo})
            if action == "Resume":
                after["restarts"] = s["restarts"] + 1
            yield after


def show(state, base=None):
    """`state` as name=value, only the values that differ from `base` when given."""

    def text(v):
        if isinstance(v, (dict, tuple)):
            return "(" + " ".join(f"{a}:{b}" for a, b in (v.items() if isinstance(v, dict) else v)) + ")"
        return "{" + " ".join(sorted(v)) + "}" if isinstance(v, frozenset) else str(v)

    base = dict(base or {})
    return ", ".join(
        f"{k}={text(v)}" for k, v in sorted(dict(state).items())
        if k != "falseStop" and (k not in base or key({k: base[k]}) != key({k: v}))
    )


def replay(work):
    cfg = (SKILL / "Replay.cfg").read_text()
    max_restarts = int(re.search(r"MaxRestarts = (\d+)", cfg)[1])
    broken, states, _ = tlc(work, cfg, "-dump", "dot,actionlabels", "graph")
    if broken:
        return [f"Replay.cfg breaks {broken}"], states, 0
    nodes, edges = state_graph(work / "graph.dot")
    if len(nodes) != int(states.replace(",", "")):
        return [f"read {len(nodes)} states from graph.dot, TLC found {states}"], states, 0
    problems, steps = [], 0
    for src, s in nodes.items():
        for action in REAL_ACTIONS:
            model = {key(nodes[dst]) for dst in edges.get((src, action), ())}
            real = set()
            try:
                for after in real_steps(s, action, max_restarts):
                    real.add(key(after))
                    steps += 1
            except Exception as error:  # a step the model allows crashed the real code, or its interface changed
                problems.append(f"{action} from [{show(s)}]: the real code raised {error!r}")
                continue
            if real != model:
                lines = [f"{action} from [{show(s)}]"]
                lines += [f"  only the real code reaches [{show(k, s)}]" for k in real - model]
                lines += [f"  only the model reaches [{show(k, s)}]" for k in model - real]
                problems.append("\n".join(lines))
    return problems, len(nodes), steps


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--no-variants", action="store_true", help="skip the past-bug variants"
    )
    parser.add_argument(
        "--no-replay", action="store_true", help="skip the replay on the real code"
    )
    args = parser.parse_args()
    ok = True
    with tempfile.TemporaryDirectory(prefix="verify-eval-budget-") as tmp:
        work = Path(tmp)
        (work / "now").mkdir()
        broken, states, path = tlc(work / "now", (SKILL / "EvalBudget.cfg").read_text())
        if broken:
            ok = False
            print(
                f"FAIL now: {broken} breaks ({states} states). Shortest path: {' -> '.join(path)}"
            )
        else:
            print(f"PASS now: CapSafe and NoFalseStop hold ({states} states)")
        for name, (in_flight, move_aside, rule, fix) in (
            {} if args.no_variants else VARIANTS
        ).items():
            (work / name).mkdir()
            broken, states, path = tlc(
                work / name, variant_cfg(in_flight, move_aside, rule)
            )
            if broken == rule:
                print(
                    f"PASS {name}: {rule} breaks, as before {fix}: {' -> '.join(path[1:])}"
                )
            else:
                ok = False
                print(
                    f"FAIL {name}: {rule} should break, as before {fix}, but it holds ({states} states)"
                )
        if not args.no_replay:
            (work / "replay").mkdir()
            problems, states, steps = replay(work / "replay")
            for problem in problems[:3]:
                print(f"FAIL real code: {problem}")
            if problems:
                ok = False
                print(f"FAIL real code: {len(problems)} steps differ from the model")
            else:
                print(
                    f"PASS real code: {steps} real steps from {states} model states match the model"
                )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
