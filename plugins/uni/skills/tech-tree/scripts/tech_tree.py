#!/usr/bin/env python3
"""Validate a course tech tree and gate a learner's progress through it.

The graph lives in ``tech-tree.json``; the learner's state lives in
``progress.json`` beside it. GRAPH-FORMAT.md defines both. Standard library
only.

Commands:

    validate          check the graph; exit 1 on errors, print warnings
    mermaid           print the tree as a Mermaid flowchart with status marks
    frontier          list topics whose prerequisites are all met
    next              name the next task: a frontier lesson or a due review
    record ID RESULT  record a lesson or review result (pass or fail)
    place ID RESULT   record a placement (diagnostic) result
    status            print every topic with its state

A lesson passes only without help. ``record ID pass --helped`` logs the
attempt but leaves the topic unmastered. ``record`` refuses a topic whose
prerequisites are not met: the gate is hard. Placement is the only way past
it.
"""

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
WEIGHTS = (0.5, 1.0)
INTERVALS = (1, 3, 7, 14, 30, 60)  # days after the 1st, 2nd, ... repetition
LESSON_EVERY = 3  # at most this many reviews between two lessons
MET = ("mastered", "conditional")


class Graph:
    def __init__(self, data):
        self.course = data.get("course", "")
        self.topics = data.get("topics", [])
        self.by_id = {t.get("id"): t for t in self.topics}

    def requires(self, tid):
        return list(self.by_id[tid].get("requires", {}))

    def children(self, tid):
        return [t["id"] for t in self.topics if tid in t.get("requires", {})]

    def ancestors(self, tid):
        seen, stack = set(), self.requires(tid)
        while stack:
            p = stack.pop()
            if p in self.by_id and p not in seen:
                seen.add(p)
                stack.extend(self.requires(p))
        return seen

    def descendants(self, tid):
        seen, stack = set(), self.children(tid)
        while stack:
            c = stack.pop()
            if c not in seen:
                seen.add(c)
                stack.extend(self.children(c))
        return seen

    def key_prerequisites(self, tid):
        keys = [k for kp in self.by_id[tid].get("kps", []) for k in kp.get("key", [])]
        return list(dict.fromkeys(keys + self.requires(tid)))

    def order(self, partial=False):
        """Topological order, or None when the requires graph has a cycle."""
        indeg = {t["id"]: len(t.get("requires", {})) for t in self.topics}
        queue = [tid for tid, d in indeg.items() if d == 0]
        out = []
        while queue:
            tid = queue.pop(0)
            out.append(tid)
            for c in self.children(tid):
                indeg[c] -= 1
                if indeg[c] == 0:
                    queue.append(c)
        return out if partial or len(out) == len(self.topics) else None


def validate(g):
    errors, warnings = [], []
    ids = [t.get("id") for t in g.topics]
    for tid in ids:
        if not isinstance(tid, str) or not ID_RE.match(tid):
            errors.append(f"id {tid!r} is not kebab-case")
        elif ids.count(tid) > 1:
            errors.append(f"id {tid} is duplicated")
    if errors:
        return errors, warnings
    for t in g.topics:
        tid = t["id"]
        for field in ("title", "goal", "check"):
            if not str(t.get(field, "")).strip():
                errors.append(f"{tid}: {field} is empty")
        req = t.get("requires", {})
        if not isinstance(req, dict):
            errors.append(f"{tid}: requires must map each prerequisite id to a reason")
            continue
        for p, why in req.items():
            if p not in g.by_id:
                errors.append(f"{tid}: requires unknown topic {p}")
            elif not str(why).strip():
                errors.append(f"{tid}: requires {p} has no reason")
    if errors:
        return errors, warnings
    if g.order() is None:
        stuck = sorted(set(ids) - set(g.order(partial=True)))
        return [f"requires has a cycle among or above: {', '.join(stuck)}"], warnings
    for t in g.topics:
        tid, anc = t["id"], g.ancestors(t["id"])
        for i, kp in enumerate(t.get("kps", []), 1):
            if not str(kp.get("title", "")).strip():
                errors.append(f"{tid}: knowledge point {i} has no title")
            for k in kp.get("key", []):
                if k not in anc:
                    errors.append(f"{tid}: knowledge point {i} key {k} is not an ancestor")
        for e, w in t.get("encompasses", {}).items():
            if e not in anc:
                errors.append(f"{tid}: encompasses {e}, which is not an ancestor")
            if w not in WEIGHTS:
                errors.append(f"{tid}: encompasses {e} with weight {w}; use 0.5 or 1.0")
        req = list(t.get("requires", {}))
        if len(req) > 4:
            warnings.append(f"{tid}: {len(req)} direct prerequisites; split the topic")
        kps = t.get("kps", [])
        if not kps:
            warnings.append(f"{tid}: no knowledge points")
        elif len(kps) > 4:
            warnings.append(f"{tid}: {len(kps)} knowledge points; split the topic")
        if t.get("minutes", 0) > 30:
            warnings.append(f"{tid}: {t['minutes']} minutes; split the topic")
        if " and " in t["goal"]:
            warnings.append(f"{tid}: goal joins two skills with 'and'")
        for p in req:
            if any(p in g.ancestors(q) for q in req if q != p):
                warnings.append(f"{tid}: requires {p} is redundant (reached through another prerequisite)")
    return errors, warnings


def load(args):
    gpath = Path(args.graph)
    g = Graph(json.loads(gpath.read_text()))
    errors, _ = validate(g)
    if errors:
        sys.exit("graph has errors; run validate:\n  " + "\n  ".join(errors))
    ppath = Path(args.progress) if args.progress else gpath.with_name("progress.json")
    progress = json.loads(ppath.read_text()) if ppath.exists() else {}
    progress.setdefault("topics", {})
    progress.setdefault("log", [])
    progress.setdefault("reviews_since_lesson", 0)
    for tid in g.by_id:
        progress["topics"].setdefault(tid, {"status": "unseen", "fails": 0, "reps": 0, "due": None})
    for tid in progress["topics"]:
        if tid not in g.by_id:
            print(f"warning: progress has unknown topic {tid}; migrate or remove it", file=sys.stderr)
    return g, progress, ppath


def save(progress, ppath):
    ppath.write_text(json.dumps(progress, indent=2) + "\n")


def met(state, tid):
    return state[tid]["status"] in MET


def frontier(g, state):
    return [
        tid for tid in g.order()
        if not met(state, tid) and all(met(state, p) for p in g.requires(tid))
    ]


def due_reviews(g, state, today):
    due = [tid for tid in g.order() if met(state, tid) and state[tid]["due"] and state[tid]["due"] <= today]
    return sorted(due, key=lambda tid: state[tid]["due"])


def interval(reps):
    return INTERVALS[min(max(int(reps), 1), len(INTERVALS)) - 1]


def add_days(day, n):
    return (dt.date.fromisoformat(day) + dt.timedelta(days=n)).isoformat()


def credit(g, state, tid, today, weight=1.0):
    """Pass credit down encompassing edges; it only pushes due dates later."""
    for e, w in g.by_id[tid].get("encompasses", {}).items():
        share = weight * w
        s = state[e]
        if share < 0.5 or s["status"] != "mastered" or not s["due"]:
            continue
        # Credit that arrives long before the review is due counts for nothing.
        days_left = (dt.date.fromisoformat(s["due"]) - dt.date.fromisoformat(today)).days
        if days_left <= interval(s["reps"]) / 2:
            s["reps"] += share
            s["due"] = max(s["due"], add_days(today, interval(s["reps"])))
        credit(g, state, e, today, share)


def cmd_next(g, progress, today):
    state = progress["topics"]
    due = due_reviews(g, state, today)
    front = frontier(g, state)
    failed_today = {e["id"] for e in progress["log"] if e["date"] == today and e["result"] == "fail"}

    def score(tid):
        covers = sum(w for e, w in g.by_id[tid].get("encompasses", {}).items() if e in due)
        return (tid not in failed_today, covers, len(g.descendants(tid)) - state[tid]["fails"])

    lesson = max(front, key=score) if front else None
    covering = lesson and any(
        g.by_id[lesson].get("encompasses", {}).get(e) == 1.0 for e in due
    )
    if due and not covering and (progress["reviews_since_lesson"] < LESSON_EVERY or not lesson):
        return f"review {due[0]}  (due {state[due[0]]['due']}; {len(due)} due)"
    if lesson:
        kind = "retry" if state[lesson]["fails"] else "lesson"
        return f"{kind} {lesson}  ({g.by_id[lesson]['title']})"
    upcoming = sorted(state[t]["due"] for t in state if met(state, t) and state[t]["due"])
    if len(front) == 0 and all(met(state, t) for t in g.by_id):
        return "course complete" + (f"; next review {upcoming[0]}" if upcoming else "")
    return f"nothing due; next review {upcoming[0]}" if upcoming else "nothing to do"


def cmd_record(g, progress, tid, passed, helped, today):
    state = progress["topics"]
    s = state[tid]
    is_review = met(state, tid)
    if not is_review and not all(met(state, p) for p in g.requires(tid)):
        missing = [p for p in g.requires(tid) if not met(state, p)]
        sys.exit(f"{tid} is locked; first master: {', '.join(missing)}")
    progress["log"].append({
        "date": today, "id": tid, "kind": "review" if is_review else "lesson",
        "result": "pass" if passed else "fail", "helped": helped,
    })
    progress["reviews_since_lesson"] = progress["reviews_since_lesson"] + 1 if is_review else 0
    if passed and helped:
        if not is_review:
            s["status"] = "learning"
        return f"{tid}: helped pass logged; not mastered. Give a fresh unhelped item."
    if passed:
        s["status"], s["fails"] = "mastered", 0
        s["reps"] = s["reps"] + 1 if is_review else 1
        s["due"] = add_days(today, interval(s["reps"]))
        if not is_review:  # a retaught prerequisite restarts its dependents' ladder
            for c in g.children(tid):
                state[c]["fails"] = 0
        credit(g, state, tid, today)
        return f"{tid}: mastered; next review {s['due']}"
    s["fails"] += 1
    notes = []
    if is_review:
        if s["status"] == "conditional":
            s.update(status="unseen", reps=0, due=None, fails=0)
            for d in g.descendants(tid):
                if state[d]["status"] == "conditional":
                    state[d].update(status="unseen", reps=0, due=None)
            notes.append(f"{tid}: placement credit removed; teach it as a lesson")
        else:
            s["reps"], s["due"] = max(0, s["reps"] - 1), add_days(today, 1)
            for t in g.topics:
                if tid in t.get("encompasses", {}) and met(state, t["id"]) and state[t["id"]]["due"]:
                    state[t["id"]]["due"] = min(state[t["id"]]["due"], add_days(today, 1))
            stuck = [t for t in g.by_id if not met(state, t) and state[t]["fails"] >= 2
                     and tid in g.key_prerequisites(t)]
            if stuck or s["fails"] >= 2:
                s["status"], s["due"] = "learning", None
                notes.append(f"{tid}: reteach the lesson; locked until then: {', '.join(stuck) or 'its dependents'}")
            else:
                notes.append(f"{tid}: review again tomorrow")
        return "\n".join(notes)
    s["status"] = "learning"
    if s["fails"] == 1:
        return f"{tid}: lesson failed; teach another frontier topic, then retry with new questions"
    if s["fails"] == 2:
        keys = ", ".join(g.key_prerequisites(tid)) or "none"
        return f"{tid}: failed twice; review its key prerequisites: {keys}"
    return f"{tid}: failed {s['fails']} times with prerequisites passing; split the topic or add a missing edge"


def cmd_place(g, progress, tid, passed, today):
    state = progress["topics"]
    progress["log"].append({"date": today, "id": tid, "kind": "place", "result": "pass" if passed else "fail", "helped": False})
    if passed:
        changed = [t for t in [tid, *g.ancestors(tid)] if state[t]["status"] != "mastered"]
        for t in changed:
            state[t].update(status="conditional", reps=1, due=add_days(today, 3))
        return f"conditional credit: {', '.join(changed) or 'none'}"
    changed = [t for t in [tid, *g.descendants(tid)] if state[t]["status"] == "conditional"]
    for t in changed:
        state[t].update(status="unseen", reps=0, due=None)
    return f"{tid} and its descendants are not placed" + (f"; removed credit: {', '.join(changed)}" if changed else "")


def cmd_mermaid(g, state):
    front = set(frontier(g, state)) if state else set()
    marks = {"mastered": "✓ ", "conditional": "~ "}
    lines = ["flowchart TD"]
    for tid in g.order():
        mark = marks.get(state[tid]["status"], "▶ " if tid in front else "") if state else ""
        title = g.by_id[tid]["title"].replace('"', "'")
        lines.append(f'  {tid}["{mark}{title}"]')
    for tid in g.order():
        for p in g.requires(tid):
            lines.append(f"  {p} --> {tid}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graph", default="tech-tree.json")
    ap.add_argument("--progress", help="default: progress.json beside the graph")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="today, as YYYY-MM-DD")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("validate", "mermaid", "frontier", "next", "status"):
        sub.add_parser(name)
    for name in ("record", "place"):
        p = sub.add_parser(name)
        p.add_argument("id")
        p.add_argument("result", choices=("pass", "fail"))
        if name == "record":
            p.add_argument("--helped", action="store_true", help="the learner had a hint, example, or answer")
    args = ap.parse_args()

    if args.cmd == "validate":
        errors, warnings = validate(Graph(json.loads(Path(args.graph).read_text())))
        for w in warnings:
            print(f"warning: {w}")
        for e in errors:
            print(f"error: {e}")
        print("ok" if not errors else f"{len(errors)} errors")
        sys.exit(1 if errors else 0)

    g, progress, ppath = load(args)
    state = progress["topics"]
    if args.cmd == "mermaid":
        print(cmd_mermaid(g, state))
    elif args.cmd == "frontier":
        print("\n".join(frontier(g, state)) or "(empty)")
    elif args.cmd == "next":
        print(cmd_next(g, progress, args.date))
    elif args.cmd == "status":
        for tid in g.order():
            s = state[tid]
            print(f"{tid:32} {s['status']:12} reps={s['reps']:<4g} fails={s['fails']} due={s['due'] or '-'}")
    elif args.cmd in ("record", "place"):
        if args.id not in g.by_id:
            sys.exit(f"unknown topic {args.id}")
        passed = args.result == "pass"
        if args.cmd == "record":
            print(cmd_record(g, progress, args.id, passed, args.helped, args.date))
        else:
            print(cmd_place(g, progress, args.id, passed, args.date))
        save(progress, ppath)


if __name__ == "__main__":
    main()
