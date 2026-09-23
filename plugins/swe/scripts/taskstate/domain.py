"""Pure domain rules for taskstate. No I/O, no sqlite."""
from __future__ import annotations

import datetime

TRUNC_CAP = 2000
TRUNC_MARK = "\u2026[truncated %d chars]"

VALID_LIFECYCLES = ("proposed", "open", "active", "verified", "accepted",
                    "cancelled", "superseded")
VALID_KINDS = ("code", "research", "operation")
READY_DEPS = ("verified", "accepted")


def parse_time(value):
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=datetime.timezone.utc)
        return value
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")


def truncate(text, cap=TRUNC_CAP):
    if text is None:
        return None
    s = str(text)
    if len(s) <= cap:
        return s
    return s[:cap] + (TRUNC_MARK % (len(s) - cap))


def is_ready(task, dep_lifecycles):
    """Derived ready: open, no hold, all deps verified/accepted."""
    if task.get("lifecycle") != "open":
        return False
    if task.get("hold"):
        return False
    for lc in dep_lifecycles:
        if lc not in READY_DEPS:
            return False
    return True


def health(task, now=None):
    """running | stalled | idle."""
    if task.get("lifecycle") != "active":
        return "idle"
    now = now or datetime.datetime.now(datetime.timezone.utc)
    lease = parse_time(task.get("lease_expires_at"))
    if lease is not None and lease <= now:
        return "stalled"
    return "running"


def authorization(task, grants):
    """Return {execute, publish, via}. One-off tasks get session-request."""
    out = {"execute": False, "publish": False, "via": []}
    if not task.get("spec_id"):
        out["execute"] = True
        out["via"] = ["session-request"]
        # Publish still needs an explicit publish grant even for one-offs.
        for g in grants or []:
            if g.get("kind") == "publish" and _grant_covers(g, task):
                out["publish"] = True
                out["via"] = out["via"] + [g["grant_id"]]
        return out
    for g in grants or []:
        if _grant_covers(g, task):
            if g.get("kind") == "execute":
                out["execute"] = True
                out["via"].append(g["grant_id"])
            elif g.get("kind") == "publish":
                out["publish"] = True
                out["via"].append(g["grant_id"])
    return out


def _grant_covers(grant, task):
    import json as _json
    try:
        scope = _json.loads(grant.get("scope_json") or "{}")
    except Exception:
        return False
    if scope.get("project") is True:
        return True
    tasks = scope.get("tasks") or []
    return task.get("ref") in tasks


def evidence_freshness(evidence, expected_head, expected_diff):
    """current iff inputs.commit == expected head and diff matches.

    unknown when both commits are None (non-git work).
    """
    import json as _json
    try:
        inputs = _json.loads(evidence.get("inputs_json") or "{}")
    except Exception:
        return "stale"
    if inputs.get("commit") is None and expected_head is None:
        return "unknown"
    if inputs.get("commit") != expected_head:
        return "stale"
    if inputs.get("diff_hash") != expected_diff:
        return "stale"
    return "current"


def verify_gaps(task, criteria, evidences, expected_head, expected_diff):
    """List gaps for READY-TO-VERIFY. Empty list means verifiable.

    evidences: list of evidence rows (dicts). Only non-late rows count.
    Returns list of {ac_id (or None for task-level), gap}.
    gap in missing|failing|stale|unavailable|inconclusive.
    """
    import json as _json
    live = [e for e in evidences if not e.get("late")]
    gaps = []
    if criteria:
        by_ac = {}
        for e in live:
            try:
                acs = _json.loads(e.get("criteria_json") or "[]")
            except Exception:
                acs = []
            for ac in acs:
                prev = by_ac.get(ac)
                if prev is None or str(e.get("recorded_at") or "") >= str(prev.get("recorded_at") or ""):
                    by_ac[ac] = e
        for c in criteria:
            ac = c["ac_id"]
            e = by_ac.get(ac)
            if e is None:
                gaps.append({"ac_id": ac, "gap": "missing"})
                continue
            if e.get("result") in ("unavailable",):
                gaps.append({"ac_id": ac, "gap": "unavailable"})
                continue
            if e.get("result") == "inconclusive":
                gaps.append({"ac_id": ac, "gap": "inconclusive"})
                continue
            if e.get("result") != "pass":
                gaps.append({"ac_id": ac, "gap": "failing"})
                continue
            if evidence_freshness(e, expected_head, expected_diff) not in ("current", "unknown"):
                gaps.append({"ac_id": ac, "gap": "stale"})
                continue
    else:
        passing = [e for e in live if e.get("result") == "pass"
                   and _is_task_level(e)
                   and evidence_freshness(e, expected_head, expected_diff) in ("current", "unknown")]
        if not passing:
            # Classify the best available task-level evidence for detail.
            task_level = [e for e in live if _is_task_level(e)]
            if not task_level:
                gaps.append({"ac_id": None, "gap": "missing"})
            else:
                latest = max(task_level, key=lambda e: str(e.get("recorded_at") or ""))
                if latest.get("result") == "unavailable":
                    gaps.append({"ac_id": None, "gap": "unavailable"})
                elif latest.get("result") == "inconclusive":
                    gaps.append({"ac_id": None, "gap": "inconclusive"})
                elif latest.get("result") != "pass":
                    gaps.append({"ac_id": None, "gap": "failing"})
                else:
                    gaps.append({"ac_id": None, "gap": "stale"})
    return gaps


def _is_task_level(evidence):
    import json as _json
    try:
        acs = _json.loads(evidence.get("criteria_json") or "[]")
    except Exception:
        return False
    return not acs


def latest_progress(entries):
    """Latest progress|handoff entry, labelled agent-reported."""
    best = None
    for e in entries or []:
        if e.get("kind") in ("progress", "handoff"):
            if best is None or str(e.get("recorded_at") or "") >= str(best.get("recorded_at") or ""):
                best = e
    if best is None:
        return None
    return {"entry_id": best.get("entry_id"), "kind": best.get("kind"),
            "body": best.get("body"), "recorded_at": best.get("recorded_at"),
            "label": "agent-reported"}
