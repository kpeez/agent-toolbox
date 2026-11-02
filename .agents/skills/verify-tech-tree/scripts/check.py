#!/usr/bin/env python3
"""Explore every order of learner events on the real tech-tree code.

Breadth-first search over the states that ``tech_tree.py`` reaches on the
course in ``course.json``. Each event calls the real ``cmd_record``,
``cmd_place`` or ``cmd_next``. Each property is checked in every state, and
each violation gets its shortest event path.

Exit 0 when the result for each property matches ``EXPECTED`` and each mutant
breaks the property it targets; 1 otherwise. ``--no-mutants`` skips the mutants.
"""

import argparse
import copy
import datetime as dt
import importlib.util
import json
import sys
from collections import deque
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
REPO = SKILL.parent.parent.parent
SCRIPT = REPO / "plugins" / "uni" / "skills" / "tech-tree" / "scripts" / "tech_tree.py"
TODAY = "2026-01-01"
MAX_FAILS, MAX_REPS, MAX_OVERDUE, MAX_DEPTH = 2, 3, 2, 7

EXPECTED = {
    "LessonGate": True,
    "NextIsLegal": True,
    "MetHasDue": True,
    "UnmetHasNoDue": True,
    "ConditionalNeedsMetAncestors": False,
}


def load(name="tech_tree"):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def shift(day, n):
    return (dt.date.fromisoformat(day) + dt.timedelta(days=n)).isoformat()


def events(g):
    for tid in g.order():
        yield ("record", tid, "pass", False)
        yield ("record", tid, "pass", True)
        yield ("record", tid, "fail", False)
        yield ("place", tid, "pass", False)
        yield ("place", tid, "fail", False)
    yield ("day",)


def key(progress):
    topics = tuple(sorted((t, s["status"], s["fails"], s["reps"], s["due"]) for t, s in progress["topics"].items()))
    failed = frozenset(e["id"] for e in progress["log"] if e["date"] == TODAY and e["result"] == "fail")
    return topics, min(progress["reviews_since_lesson"], 4), failed


def in_bounds(progress):
    floor = shift(TODAY, -MAX_OVERDUE)
    return all(
        s["fails"] <= MAX_FAILS and s["reps"] <= MAX_REPS and (s["due"] is None or s["due"] >= floor)
        for s in progress["topics"].values()
    )


def met(state, tid):
    return state[tid]["status"] in ("mastered", "conditional")


def unmet(g, state, tid):
    """Written here, not taken from tech_tree.py, so a mutant cannot change it."""
    return [a for a in g.ancestors(tid) if not met(state, a)]


def step(tt, g, progress, event):
    """Apply one event to a copy of ``progress``; None when the code refuses it."""
    p = copy.deepcopy(progress)
    note = {}
    if event[0] == "day":
        for s in p["topics"].values():
            if s["due"]:
                s["due"] = shift(s["due"], -1)
        p["log"] = []
        return p, note
    kind, tid, result, helped = event
    passed = result == "pass"
    if kind == "record":
        state = p["topics"]
        note["lesson"] = not met(state, tid)
        note["unmet_before"] = unmet(g, state, tid)
        try:
            tt.cmd_record(g, p, tid, passed, helped, TODAY)
        except SystemExit:
            return None, note
    else:
        tt.cmd_place(g, p, tid, passed, TODAY)
    return p, note


def properties(tt, g, progress, note):
    state = progress["topics"]
    out = {}
    out["LessonGate"] = not (note.get("lesson") and note.get("unmet_before"))
    words = tt.cmd_next(g, progress, TODAY).split()
    if words[0] in ("lesson", "retry"):
        tid = words[1]
        out["NextIsLegal"] = not met(state, tid) and not unmet(g, state, tid)
    elif words[0] == "review":
        out["NextIsLegal"] = met(state, words[1])
    else:
        out["NextIsLegal"] = True
    out["MetHasDue"] = all(s["due"] for t, s in state.items() if met(state, t))
    out["UnmetHasNoDue"] = all(s["due"] is None for t, s in state.items() if not met(state, t))
    out["ConditionalNeedsMetAncestors"] = all(
        met(state, a) for t, s in state.items() if s["status"] == "conditional" for a in g.ancestors(t)
    )
    return out


def explore(tt, stop_on=None):
    g = tt.Graph(json.loads((SKILL / "course.json").read_text()))
    start = {"topics": {t: {"status": "unseen", "fails": 0, "reps": 0, "due": None} for t in g.by_id},
             "log": [], "reviews_since_lesson": 0}
    seen = {key(start): None}
    queue = deque([(start, [], 0)])
    broken = {}
    while queue:
        progress, path, depth = queue.popleft()
        if depth == MAX_DEPTH:
            continue
        for event in events(g):
            nxt, note = step(tt, g, progress, event)
            if nxt is None or not in_bounds(nxt):
                continue
            new_path = path + [event]
            for name, ok in properties(tt, g, nxt, note).items():
                if not ok and name not in broken:
                    broken[name] = new_path
                    if name == stop_on:
                        return broken, len(seen)
            k = key(nxt)
            if k not in seen:
                seen[k] = True
                queue.append((nxt, new_path, depth + 1))
    return broken, len(seen)


def words(event):
    if event[0] == "day":
        return "a day passes"
    kind, tid, result, helped = event
    return f"{kind} {tid} {result}" + (" --helped" if helped else "")


def mutant_gate(tt):
    tt.unmet_ancestors = lambda g, state, tid: []


def mutant_frontier(tt):
    original = tt.frontier
    tt.frontier = lambda g, state: [t for t in g.order() if not tt.met(state, t)] or original(g, state)


def mutant_place_due(tt):
    original = tt.cmd_place

    def place(g, progress, tid, passed, today):
        out = original(g, progress, tid, passed, today)
        for s in progress["topics"].values():
            if s["status"] == "conditional":
                s["due"] = None
        return out

    tt.cmd_place = place


def mutant_fail_keeps_due(tt):
    original = tt.cmd_record

    def record(g, progress, tid, passed, helped, today):
        before = progress["topics"][tid]["due"]
        out = original(g, progress, tid, passed, helped, today)
        if not passed and progress["topics"][tid]["status"] == "learning":
            progress["topics"][tid]["due"] = before or today
        return out

    tt.cmd_record = record


MUTANTS = {
    "LessonGate": mutant_gate,
    "NextIsLegal": mutant_frontier,
    "MetHasDue": mutant_place_due,
    "UnmetHasNoDue": mutant_fail_keeps_due,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-mutants", action="store_true")
    args = ap.parse_args()

    broken, states = explore(load())
    print(f"{states} distinct states, depth {MAX_DEPTH}, bounds: fails <= {MAX_FAILS}, "
          f"reps <= {MAX_REPS}, overdue <= {MAX_OVERDUE} days")
    ok = True
    for name, holds_expected in EXPECTED.items():
        holds = name not in broken
        status = "holds" if holds else "breaks"
        match = holds == holds_expected
        ok &= match
        print(f"{name}: {status}" + ("" if match else f"  (expected {'holds' if holds_expected else 'breaks'})"))
        if not holds:
            for i, event in enumerate(broken[name], 1):
                print(f"  {i}. {words(event)}")
    if not args.no_mutants:
        for name, mutate in MUTANTS.items():
            tt = load(f"tech_tree_{name}")
            mutate(tt)
            caught = name in explore(tt, stop_on=name)[0]
            ok &= caught
            print(f"mutant for {name}: {'caught' if caught else 'NOT CAUGHT (the check cannot fail)'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
