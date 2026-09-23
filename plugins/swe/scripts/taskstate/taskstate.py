#!/usr/bin/env python3
"""taskstate Phase 1 local core. Stdlib only. See docs/agents/specs/0029-taskstate.md."""
from __future__ import annotations

import argparse
import datetime
import getpass
import hashlib
import json
import os
import socket
import sqlite3
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import domain
import facts
import store as store_mod


class TaskStateError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or []


# --- small helpers ----------------------------------------------------------

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_hex(text):
    if not isinstance(text, (bytes, bytearray)):
        text = text.encode("utf-8")
    return hashlib.sha256(text).hexdigest()


def new_uuid4():
    return str(uuid.uuid4())


def is_uuid_any(value):
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def is_uuid4(value):
    try:
        return uuid.UUID(str(value)).version == 4
    except (ValueError, AttributeError, TypeError):
        return False


def lease_seconds():
    try:
        return int(os.environ.get("TASKSTATE_LEASE_SECONDS", "7200"))
    except ValueError:
        return 7200


def current_actor(cli_actor=None):
    if cli_actor:
        return cli_actor
    env = os.environ.get("TASKSTATE_ACTOR")
    if env:
        return env
    try:
        user = getpass.getuser()
    except Exception:
        user = os.environ.get("USER", "unknown")
    return "cli:%s" % user


def current_host():
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def is_human_allowed(human_override=None):
    """Single human-check so Phase 3 can extend agent detection."""
    if human_override is not None:
        return bool(human_override)
    try:
        tty = sys.stdin.isatty()
    except Exception:
        tty = False
    if not tty:
        return False
    if os.environ.get("CLAUDECODE"):
        return False
    return True


def require_human(human_override):
    if not is_human_allowed(human_override):
        raise TaskStateError("human_only", "This command is human-only (interactive TTY without agent session required)")


def parse_observed(value=None):
    if value is None:
        return now_iso()
    try:
        parsed = domain.parse_time(value)
    except Exception:
        raise TaskStateError("validation_failed", "Invalid --observed-at: %r" % value)
    return parsed.astimezone(datetime.timezone.utc).isoformat(timespec="microseconds")


# --- worktree cache ----------------------------------------------------------

def _cache_path():
    gd = facts.git_dir()
    if not gd:
        return None
    return os.path.join(gd, "taskstate.json")


def read_cache():
    path = _cache_path()
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_cache(project, ref, attempt_id, epoch):
    path = _cache_path()
    if not path:
        return
    payload = {"project": project, "ref": ref, "attempt_id": attempt_id, "epoch": epoch}
    tmp = path + ".tmp-%d" % os.getpid()
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True)
            fh.write("\n")
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def clear_cache(project=None, ref=None, attempt_id=None, epoch=None):
    path = _cache_path()
    if not path or not os.path.isfile(path):
        return
    if any(value is not None for value in (project, ref, attempt_id, epoch)):
        cache = read_cache()
        if project is not None and cache.get("project") != project:
            return
        if ref is not None and cache.get("ref") != ref:
            return
        if attempt_id is not None and cache.get("attempt_id") != attempt_id:
            return
        if epoch is not None:
            try:
                if int(cache.get("epoch")) != int(epoch):
                    return
            except (TypeError, ValueError):
                return
    try:
        os.unlink(path)
    except OSError:
        pass


# --- db helpers ---------------------------------------------------------------

def _row_dict(row):
    return dict(row) if row is not None else None


def fetch_task(conn, ref):
    row = conn.execute("SELECT * FROM task WHERE ref=?", (ref,)).fetchone()
    if row is None:
        raise TaskStateError("task_not_found", "Unknown task: %s" % ref)
    return _row_dict(row)


def fetch_task_by_id(conn, task_id):
    row = conn.execute("SELECT * FROM task WHERE task_id=?", (task_id,)).fetchone()
    return _row_dict(row)


def task_criteria(conn, task_id):
    rows = conn.execute("SELECT ac_id, text FROM criterion WHERE task_id=? ORDER BY ac_id",
                        (task_id,)).fetchall()
    return [{"ac_id": r["ac_id"], "text": r["text"]} for r in rows]


def task_dep_refs(conn, task_id):
    rows = conn.execute(
        "SELECT t.ref AS ref, t.lifecycle AS lifecycle FROM task_dep d "
        "JOIN task t ON t.task_id=d.depends_on WHERE d.task_id=? ORDER BY ref",
        (task_id,)).fetchall()
    return [{"ref": r["ref"], "lifecycle": r["lifecycle"]} for r in rows]


def dep_lifecycles(conn, task_id):
    rows = conn.execute(
        "SELECT t.lifecycle AS lc FROM task_dep d JOIN task t ON t.task_id=d.depends_on "
        "WHERE d.task_id=?", (task_id,)).fetchall()
    return [r["lc"] for r in rows]


def all_grants(conn):
    rows = conn.execute("SELECT * FROM grant_ ORDER BY created_at").fetchall()
    return [_row_dict(r) for r in rows]


def ref_to_id(conn, ref):
    row = conn.execute("SELECT task_id FROM task WHERE ref=?", (ref,)).fetchone()
    if row is None:
        raise TaskStateError("unknown_dependency", "Unknown dependency: %s" % ref)
    return row["task_id"]


def check_cycle(conn, new_task_id, new_dep_ids):
    graph = {}
    for r in conn.execute("SELECT task_id FROM task").fetchall():
        graph[r["task_id"]] = []
    for r in conn.execute("SELECT task_id, depends_on FROM task_dep").fetchall():
        graph.setdefault(r["task_id"], []).append(r["depends_on"])
    graph[new_task_id] = list(new_dep_ids)
    visiting, visited = set(), set()

    def walk(node):
        if node in visited:
            return False
        if node in visiting:
            return True
        visiting.add(node)
        for dep in graph.get(node, []):
            if dep in graph and walk(dep):
                return True
        visiting.discard(node)
        visited.add(node)
        return False

    for node in list(graph):
        if walk(node):
            raise TaskStateError("dependency_cycle", "dependency cycle detected")


def current_attempt_for_task(conn, task):
    if task.get("owner_attempt"):
        row = conn.execute("SELECT * FROM attempt WHERE attempt_id=?",
                           (task["owner_attempt"],)).fetchone()
        if row is not None:
            return _row_dict(row)
    row = conn.execute("SELECT * FROM attempt WHERE task_id=? ORDER BY started_at DESC LIMIT 1",
                       (task["task_id"],)).fetchone()
    return _row_dict(row)


def expected_inputs(conn, task):
    att = current_attempt_for_task(conn, task)
    if att is not None and att.get("last_head") is not None:
        return att["last_head"], att.get("last_diff_hash"), att
    return None, None, att


def expected_inputs_live(conn, task, live):
    """Freshness baseline. Use live git facts only when live worktree and
    the attempt worktree are both non-null and equal; otherwise use stored
    attempt facts. Applies to both owned and ownerless tasks."""
    att = current_attempt_for_task(conn, task)
    if isinstance(live, dict) and live.get("head") is not None and att is not None:
        att_wt = att.get("worktree") if att else None
        live_wt = live.get("worktree")
        if att_wt and live_wt and att_wt == live_wt:
            return live.get("head"), live.get("diff_hash"), att
    return expected_inputs(conn, task)


def update_attempt_facts(conn, attempt_id, fact, observed_at):
    if attempt_id is None:
        return False
    row = conn.execute("SELECT facts_observed_at FROM attempt WHERE attempt_id=?",
                       (attempt_id,)).fetchone()
    if row is None:
        return False
    prev = row["facts_observed_at"]
    try:
        new_dt = domain.parse_time(observed_at)
    except Exception:
        return False
    if prev:
        try:
            prev_dt = domain.parse_time(prev)
        except Exception:
            prev_dt = None
        if prev_dt is not None and new_dt is not None and new_dt <= prev_dt:
            return False
    try:
        norm = new_dt.astimezone(datetime.timezone.utc).isoformat(timespec="microseconds")
    except Exception:
        norm = observed_at
    conn.execute("UPDATE attempt SET last_head=?, last_diff_hash=?, branch=?, worktree=?, "
                 "facts_observed_at=? WHERE attempt_id=?",
                 (fact.get("head"), fact.get("diff_hash"), fact.get("branch"),
                  fact.get("worktree"), norm, attempt_id))
    return True


def set_attempt_checkpoint(conn, attempt_id, fact, checkpoint_at):
    if attempt_id is None:
        return False
    row = conn.execute("SELECT checkpoint_at FROM attempt WHERE attempt_id=?",
                       (attempt_id,)).fetchone()
    if row is None:
        return False
    previous = row["checkpoint_at"]
    if previous:
        try:
            if domain.parse_time(checkpoint_at) <= domain.parse_time(previous):
                return False
        except Exception:
            return False
    conn.execute("UPDATE attempt SET checkpoint_head=?, checkpoint_diff_hash=?, checkpoint_at=? "
                 "WHERE attempt_id=?",
                 (fact.get("head"), fact.get("diff_hash"), checkpoint_at, attempt_id))
    return True


def split_list(values):
    out = []
    for v in values or []:
        for part in str(v).split(","):
            part = part.strip()
            if part:
                out.append(part)
    return out


def parse_criterion(spec):
    if "=" not in spec:
        raise TaskStateError("validation_failed",
                             "Criterion must look like AC-1=text, got %r" % spec)
    ac_id, text = spec.split("=", 1)
    ac_id, text = ac_id.strip(), text.strip()
    if not ac_id or not text:
        raise TaskStateError("validation_failed", "Criterion needs id and text: %r" % spec)
    return ac_id, text


def caller_match(task, attempt_id, epoch):
    """True when caller owns the task (epoch + attempt both match)."""
    if not task.get("owner_attempt"):
        return False
    if attempt_id != task.get("owner_attempt"):
        return False
    try:
        if int(epoch) != int(task.get("claim_epoch")):
            return False
    except (TypeError, ValueError):
        return False
    return True


# --- mutation wrapper ----------------------------------------------------------

def do_mutation(conn, command, request_id_in, payload, actor, task_id, effect):
    request_id = request_id_in or new_uuid4()
    if not is_uuid_any(request_id):
        raise TaskStateError("validation_failed", "Invalid --request-id (need UUID)")
    digest = sha256_hex(canonical_json(payload))
    conn.execute("BEGIN IMMEDIATE;")
    try:
        existing = conn.execute("SELECT payload_digest, result_json FROM mutation WHERE request_id=?",
                                (request_id,)).fetchone()
        if existing is not None:
            if existing["payload_digest"] != digest:
                raise TaskStateError("request_conflict",
                                     "request_id reused with different payload")
            result = json.loads(existing["result_json"])
            try:
                conn.execute("ROLLBACK;")
            except sqlite3.Error:
                pass
            do_mutation.last_replay = True
            return result
        result = effect()
        if not isinstance(result, dict):
            result = {"value": result}
        result = dict(result)
        result.setdefault("request_id", request_id)
        recorded_at = now_iso()
        conn.execute("INSERT INTO mutation(request_id, command, actor, task_id, payload_digest, "
                     "result_json, recorded_at) VALUES(?,?,?,?,?,?,?)",
                     (request_id, command, actor, task_id, digest,
                      json.dumps(result, sort_keys=True), recorded_at))
        conn.execute("COMMIT;")
        do_mutation.last_replay = False
        return result
    except BaseException:
        try:
            conn.execute("ROLLBACK;")
        except sqlite3.Error:
            pass
        raise


# --- derived views ---------------------------------------------------------------

do_mutation.last_replay = False

def task_view(conn, task, live=None):
    criteria = task_criteria(conn, task["task_id"])
    deps = task_dep_refs(conn, task["task_id"])
    grants = all_grants(conn)
    auth = domain.authorization(task, grants)
    entries = [_row_dict(r) for r in
               conn.execute("SELECT * FROM journal WHERE task_id=? ORDER BY recorded_at DESC LIMIT 50",
                            (task["task_id"],)).fetchall()]
    prog = domain.latest_progress(entries)
    ev_rows = [_row_dict(r) for r in
               conn.execute("SELECT * FROM evidence WHERE task_id=? ORDER BY recorded_at DESC",
                            (task["task_id"],)).fetchall()]
    exp_head, exp_diff, _ = expected_inputs_live(conn, task, live)
    ev_status = []
    import json as _json
    for c in criteria:
        latest = None
        for e in ev_rows:
            if e.get("late"):
                continue
            try:
                acs = _json.loads(e.get("criteria_json") or "[]")
            except Exception:
                acs = []
            if c["ac_id"] in acs:
                latest = e
                break
        if latest is None:
            ev_status.append({"ac_id": c["ac_id"], "status": "missing", "freshness": None})
        else:
            fresh = domain.evidence_freshness(latest, exp_head, exp_diff)
            ev_status.append({"ac_id": c["ac_id"], "status": latest.get("result"),
                              "freshness": fresh,
                              "evidence_id": latest.get("evidence_id")})
    return {"task": task, "criteria": criteria, "deps": deps,
            "derived": {"ready": domain.is_ready(task, dep_lifecycles(conn, task["task_id"])),
                        "health": domain.health(task),
                        "authorization": auth,
                        "reported_progress": prog,
                        "evidence": ev_status}}


def build_context(conn, slug, task, live=None):
    import json as _json
    criteria = task_criteria(conn, task["task_id"])
    deps = task_dep_refs(conn, task["task_id"])
    grants = all_grants(conn)
    exp_head, exp_diff, _ = expected_inputs_live(conn, task, live)
    ev_rows = [_row_dict(r) for r in
               conn.execute("SELECT * FROM evidence WHERE task_id=? ORDER BY recorded_at DESC",
                            (task["task_id"],)).fetchall()]
    crit_status = []
    for c in criteria:
        latest = None
        for e in ev_rows:
            if e.get("late"):
                continue
            try:
                acs = _json.loads(e.get("criteria_json") or "[]")
            except Exception:
                acs = []
            if c["ac_id"] in acs:
                latest = e
                break
        if latest is None:
            crit_status.append({"ac_id": c["ac_id"], "text": domain.truncate(c["text"]),
                                "evidence": None})
        else:
            crit_status.append({"ac_id": c["ac_id"], "text": domain.truncate(c["text"]),
                                "evidence": {
                                    "evidence_id": latest["evidence_id"],
                                    "result": latest.get("result"),
                                    "kind": latest.get("kind"),
                                    "freshness": domain.evidence_freshness(latest, exp_head, exp_diff),
                                    "summary": domain.truncate(latest.get("summary") or ""),
                                    "command": domain.truncate(latest.get("command") or ""),
                                    "recorded_at": latest.get("recorded_at")}})

    def cap_entries(rows, limit):
        capped = []
        for r in rows[:limit]:
            c = dict(r)
            if c.get("body") is not None:
                c["body"] = domain.truncate(c["body"])
            if c.get("data_json"):
                try:
                    dj = _json.loads(c["data_json"])
                    c["data"] = dj
                except Exception:
                    c["data"] = c["data_json"]
            c.pop("data_json", None)
            capped.append(c)
        return capped, max(0, len(rows) - limit)

    decisions = [_row_dict(r) for r in conn.execute(
        "SELECT * FROM journal WHERE task_id=? AND kind='decision' AND (status IS NULL OR status!='superseded') "
        "ORDER BY recorded_at DESC", (task["task_id"],)).fetchall()]
    failed = [_row_dict(r) for r in conn.execute(
        "SELECT * FROM journal WHERE task_id=? AND kind='failed_approach' ORDER BY recorded_at DESC",
        (task["task_id"],)).fetchall()]
    openqb = [_row_dict(r) for r in conn.execute(
        "SELECT * FROM journal WHERE task_id=? AND kind IN ('question','blocker') AND status='open' "
        "ORDER BY recorded_at DESC", (task["task_id"],)).fetchall()]
    handoffs = [_row_dict(r) for r in conn.execute(
        "SELECT * FROM journal WHERE task_id=? AND kind='handoff' ORDER BY recorded_at DESC LIMIT 1",
        (task["task_id"],)).fetchall()]
    latest_ev = {}
    for e in ev_rows:
        try:
            acs = _json.loads(e.get("criteria_json") or "[]")
        except Exception:
            acs = []
        key = tuple(sorted(acs)) if acs else ("__task__",)
        if key not in latest_ev:
            latest_ev[key] = e
    latest_ev_list = []
    for e in list(latest_ev.values())[:10]:
        c = dict(e)
        if c.get("summary"):
            c["summary"] = domain.truncate(c["summary"])
        latest_ev_list.append(c)
    dec, dec_omit = cap_entries(decisions, 10)
    fai, fai_omit = cap_entries(failed, 20)
    oqb, oqb_omit = cap_entries(openqb, 20)
    model = {"contract_version": 1, "view": "context", "generated_at": now_iso(),
             "source": {"project": slug, "db_seq": store_mod.db_seq(conn)},
             "task": {k: (domain.truncate(v) if k in ("title", "hold_reason") and v else v)
                      for k, v in task.items()},
             "derived": {"ready": domain.is_ready(task, dep_lifecycles(conn, task["task_id"])),
                         "health": domain.health(task),
                         "authorization": domain.authorization(task, grants),
                         "reported_progress": domain.latest_progress(
                             [_row_dict(r) for r in conn.execute(
                                 "SELECT * FROM journal WHERE task_id=?", (task["task_id"],)).fetchall()])},
             "criteria": crit_status, "deps": deps,
             "decisions": {"items": dec, "omitted": dec_omit},
             "failed_approaches": {"items": fai, "omitted": fai_omit},
             "open_questions_blockers": {"items": oqb, "omitted": oqb_omit},
             "latest_handoff": cap_entries(handoffs, 1)[0][:1],
             "latest_evidence": latest_ev_list}
    return model


def attention_for_conn(conn, slug, live=None):
    items = []
    now = datetime.datetime.now(datetime.timezone.utc)
    for r in conn.execute("SELECT * FROM task").fetchall():
        t = _row_dict(r)
        # stalled
        if t.get("lifecycle") == "active":
            lease = domain.parse_time(t.get("lease_expires_at"))
            if lease is not None and lease <= now:
                items.append({"type": "stalled", "project": slug, "ref": t["ref"],
                              "since": t.get("lease_expires_at"),
                              "detail": "lease expired; owner_attempt=%s" % (t.get("owner_attempt") or "-")})
        # on-hold
        if t.get("hold"):
            items.append({"type": "on_hold", "project": slug, "ref": t["ref"],
                          "since": t.get("updated_at"),
                          "detail": t.get("hold_reason") or "held"})
        # verified awaiting acceptance
        if t.get("lifecycle") == "verified":
            items.append({"type": "verified_awaiting_acceptance", "project": slug, "ref": t["ref"],
                          "since": t.get("updated_at"), "detail": "verified; needs accept"})
            # stale evidence on verified tasks
            exp_head, exp_diff, _ = expected_inputs_live(conn, t, live)
            ev_rows = [_row_dict(e) for e in conn.execute(
                "SELECT * FROM evidence WHERE task_id=?", (t["task_id"],)).fetchall()]
            crit = task_criteria(conn, t["task_id"])
            gaps = domain.verify_gaps(t, crit, ev_rows, exp_head, exp_diff)
            if gaps:
                items.append({"type": "stale_evidence", "project": slug, "ref": t["ref"],
                              "since": t.get("updated_at"),
                              "detail": "verified but evidence gaps: %s" % json.dumps(gaps, sort_keys=True)})
    for r in conn.execute("SELECT j.*, t.ref AS ref FROM journal j JOIN task t ON t.task_id=j.task_id "
                          "WHERE j.kind IN ('question','blocker') AND j.status='open'").fetchall():
        items.append({"type": "open_%s" % r["kind"], "project": slug, "ref": r["ref"],
                      "since": r["recorded_at"], "detail": (r["body"] or "")[:300]})
    return items


# --- command handlers -----------------------------------------------------------

def cmd_project_init(conn, slug, args, actor, observed_at, fact, host):
    require_human(args_human)
    disclosure = args.disclosure or "internal"
    if disclosure not in ("public", "internal", "restricted"):
        raise TaskStateError("validation_failed", "Bad disclosure: %r" % disclosure)
    payload = {"command": "project.init", "slug": slug, "disclosure": disclosure}
    def effect():
        exists = conn.execute("SELECT slug FROM project WHERE slug=?", (slug,)).fetchone()
        if exists is not None:
            raise TaskStateError("project_exists", "Project already exists: %s" % slug)
        pid = new_uuid4()
        created = now_iso()
        conn.execute("INSERT INTO project(project_id, slug, disclosure, created_at) VALUES(?,?,?,?)",
                     (pid, slug, disclosure, created))
        return {"project": {"project_id": pid, "slug": slug, "disclosure": disclosure,
                            "created_at": created}}
    return do_mutation(conn, "project.init", args.request_id, payload, actor, None, effect)


def cmd_task_add(conn, slug, args, actor, observed_at, fact, host):
    title = (args.title or "").strip()
    if not title:
        raise TaskStateError("validation_failed", "task add needs --title")
    kind = args.kind or "code"
    if kind not in domain.VALID_KINDS:
        raise TaskStateError("validation_failed", "Bad kind: %r" % kind)
    spec_id = getattr(args, "spec_id", None)
    if spec_id is not None and not is_uuid4(spec_id):
        raise TaskStateError("validation_failed", "Bad --spec-id (need UUID4)")
    crits = []
    for raw in (getattr(args, "criterion", None) or []):
        ac_id, text = parse_criterion(raw)
        crits.append({"ac_id": ac_id, "text": text})
    if len({c["ac_id"] for c in crits}) != len(crits):
        raise TaskStateError("validation_failed", "Duplicate criterion ids")
    dep_refs = split_list(getattr(args, "depends_on", None) or [])
    payload = {"command": "task.add", "project": slug, "title": title, "kind": kind,
               "spec_id": spec_id, "criteria": crits, "depends_on": sorted(dep_refs)}
    def effect():
        dep_ids = []
        for ref in dep_refs:
            if ref == "":
                continue
            dep_ids.append(ref_to_id(conn, ref))
        task_id = new_uuid4()
        n = int(conn.execute("SELECT value FROM meta WHERE key='next_ref_n'").fetchone()["value"])
        ref = "%s-%d" % (slug, n)
        created = now_iso()
        conn.execute("INSERT INTO task(task_id, ref, title, kind, spec_id, lifecycle, hold, version, "
                     "claim_epoch, created_at, updated_at) VALUES(?,?,?,?,?,'open',0,1,0,?,?)",
                     (task_id, ref, title, kind, spec_id, created, created))
        for c in crits:
            conn.execute("INSERT INTO criterion(task_id, ac_id, text) VALUES(?,?,?)",
                         (task_id, c["ac_id"], c["text"]))
        for did in dep_ids:
            if did == task_id:
                raise TaskStateError("self_dependency", "Task depends on itself")
            conn.execute("INSERT INTO task_dep(task_id, depends_on) VALUES(?,?)", (task_id, did))
        check_cycle(conn, task_id, dep_ids)
        conn.execute("UPDATE meta SET value=? WHERE key='next_ref_n'", (str(n + 1),))
        return {"ref": ref, "task_id": task_id, "version": 1}
    return do_mutation(conn, "task.add", args.request_id, payload, actor, None, effect)


def cmd_grant_add(conn, slug, args, actor, observed_at, fact, host):
    require_human(args_human)
    kind = args.kind
    if kind not in ("execute", "publish"):
        raise TaskStateError("validation_failed", "Bad grant kind: %r" % kind)
    source = (args.source or "").strip()
    if not source:
        raise TaskStateError("validation_failed", "grant add needs --source")
    task_refs = split_list(getattr(args, "task", None) or [])
    # also accept --tasks alias if present
    task_refs += split_list(getattr(args, "tasks", None) or [])
    scope_project = bool(getattr(args, "scope_project", False) or getattr(args, "project_scope", False))
    if task_refs and scope_project:
        raise TaskStateError("validation_failed", "grant add: --task ... or --scope-project, not both")
    if not task_refs and not scope_project:
        raise TaskStateError("validation_failed", "grant add needs --task REF ... or --scope-project")
    for ref in task_refs:
        fetch_task(conn, ref)
    try:
        user = getpass.getuser()
    except Exception:
        user = "human"
    payload = {"command": "grant.add", "project": slug, "kind": kind,
               "tasks": sorted(task_refs), "scope_project": scope_project, "source": source}
    def effect():
        gid = new_uuid4()
        scope = {"project": True} if scope_project else {"tasks": sorted(task_refs)}
        created = now_iso()
        conn.execute("INSERT INTO grant_(grant_id, kind, scope_json, granted_by, source, recorded_via, "
                     "created_at) VALUES(?,?,?,?,?,'human-cli',?)",
                     (gid, kind, json.dumps(scope, sort_keys=True), user, source, created))
        return {"grant_id": gid, "kind": kind, "scope": scope}
    return do_mutation(conn, "grant.add", args.request_id, payload, actor, None, effect)


def _claim_effect(conn, slug, task, actor, observed_at, fact, host, cache_op=None):
    if task.get("owner_attempt"):
        row = conn.execute("SELECT actor, host, lease_expires_at FROM task t LEFT JOIN attempt a "
                           "ON a.attempt_id=t.owner_attempt WHERE t.task_id=?",
                           (task["task_id"],)).fetchone()
        raise TaskStateError("already_claimed",
                             "Task %s already claimed" % task["ref"],
                             details=[{"owner_attempt": task.get("owner_attempt"),
                                       "actor": row["actor"] if row else None,
                                       "host": row["host"] if row else None,
                                       "lease_expires_at": task.get("lease_expires_at")}])
    if task.get("hold"):
        raise TaskStateError("on_hold", "Task %s is on hold" % task["ref"])
    if task["lifecycle"] != "open":
        raise TaskStateError("not_claimable", "Task %s is %s, not open" % (task["ref"], task["lifecycle"]))
    deps = dep_lifecycles(conn, task["task_id"])
    if any(lc not in domain.READY_DEPS for lc in deps):
        raise TaskStateError("blocked", "Task %s has unsatisfied dependencies" % task["ref"])
    if task.get("spec_id"):
        auth = domain.authorization(task, all_grants(conn))
        if not auth.get("execute"):
            raise TaskStateError("not_authorized", "No execute grant covers %s" % task["ref"])
    old_epoch = int(task.get("claim_epoch") or 0)
    new_epoch = old_epoch + 1
    attempt_id = new_uuid4()
    recorded = now_iso()
    lease = (datetime.datetime.now(datetime.timezone.utc) +
             datetime.timedelta(seconds=lease_seconds())).replace(microsecond=0).isoformat()
    cur = conn.execute("UPDATE task SET claim_epoch=?, owner_attempt=?, lifecycle='active', "
                       "lease_expires_at=?, version=version+1, updated_at=? "
                       "WHERE task_id=? AND claim_epoch=? AND owner_attempt IS NULL",
                       (new_epoch, attempt_id, lease, recorded, task["task_id"], old_epoch))
    if cur.rowcount != 1:
        row = conn.execute("SELECT owner_attempt, claim_epoch FROM task WHERE task_id=?",
                           (task["task_id"],)).fetchone()
        raise TaskStateError("already_claimed", "Task %s already claimed" % task["ref"],
                             details=[{"owner_attempt": row["owner_attempt"] if row else None,
                                       "claim_epoch": row["claim_epoch"] if row else None}])
    conn.execute("INSERT INTO attempt(attempt_id, task_id, claim_epoch, actor, host, worktree, branch, "
                 "start_head, start_diff_hash, last_head, last_diff_hash, facts_observed_at, started_at) "
                 "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (attempt_id, task["task_id"], new_epoch, actor, host, fact.get("worktree"),
                  fact.get("branch"), fact.get("head"), fact.get("diff_hash"), fact.get("head"),
                  fact.get("diff_hash"), observed_at, recorded))
    version = conn.execute("SELECT version FROM task WHERE task_id=?",
                           (task["task_id"],)).fetchone()["version"]
    if cache_op is not None:
        cache_op["write"] = (slug, task["ref"], attempt_id, new_epoch)
    else:
        write_cache(slug, task["ref"], attempt_id, new_epoch)
    return {"ref": task["ref"], "attempt_id": attempt_id, "epoch": new_epoch,
            "lease_expires_at": lease, "version": version}


def cmd_claim(conn, slug, args, actor, observed_at, fact, host):
    if getattr(args, "new", None):
        title = args.new.strip()
        if not title:
            raise TaskStateError("validation_failed", "claim --new needs a title")
        kind = getattr(args, "kind", None) or "code"
        if kind not in domain.VALID_KINDS:
            raise TaskStateError("validation_failed", "Bad kind: %r" % kind)
        crits = []
        for raw in (getattr(args, "criterion", None) or []):
            ac_id, text = parse_criterion(raw)
            crits.append({"ac_id": ac_id, "text": text})
        payload = {"command": "claim.new", "project": slug, "title": title, "kind": kind,
                   "criteria": crits}
        cache_op = {}
        def effect():
            task_id = new_uuid4()
            n = int(conn.execute("SELECT value FROM meta WHERE key='next_ref_n'").fetchone()["value"])
            ref = "%s-%d" % (slug, n)
            created = now_iso()
            conn.execute("INSERT INTO task(task_id, ref, title, kind, lifecycle, hold, version, "
                         "claim_epoch, created_at, updated_at) VALUES(?,?,?,?,'open',0,1,0,?,?)",
                         (task_id, ref, title, kind, created, created))
            for c in crits:
                conn.execute("INSERT INTO criterion(task_id, ac_id, text) VALUES(?,?,?)",
                             (task_id, c["ac_id"], c["text"]))
            conn.execute("UPDATE meta SET value=? WHERE key='next_ref_n'", (str(n + 1),))
            task = _row_dict(conn.execute("SELECT * FROM task WHERE task_id=?", (task_id,)).fetchone())
            res = _claim_effect(conn, slug, task, actor, observed_at, fact, host, cache_op)
            res["task_id"] = task_id
            return res
        result = do_mutation(conn, "claim.new", args.request_id, payload, actor, None, effect)
        if cache_op.get("write") and not getattr(do_mutation, "last_replay", False):
            write_cache(*cache_op["write"])
        return result
    ref = getattr(args, "ref", None) or getattr(args, "task", None)
    if not ref:
        raise TaskStateError("validation_failed", "claim needs a REF or --new TITLE")
    payload = {"command": "claim", "project": slug, "ref": ref}
    cache_op = {}
    def effect():
        task = fetch_task(conn, ref)
        return _claim_effect(conn, slug, task, actor, observed_at, fact, host, cache_op)
    result = do_mutation(conn, "claim", args.request_id, payload, actor, None, effect)
    if cache_op.get("write") and not getattr(do_mutation, "last_replay", False):
        write_cache(*cache_op["write"])
    return result


def _resolve_owner(conn, slug, args):
    cache = read_cache()
    project = getattr(args, "project", None) or cache.get("project") or slug
    ref = getattr(args, "task", None) or getattr(args, "ref", None) or cache.get("ref")
    attempt_id = getattr(args, "attempt", None)
    epoch = getattr(args, "epoch", None)
    if attempt_id is None and epoch is None:
        if cache.get("project") == slug and cache.get("ref") == ref and ref is not None:
            attempt_id = cache.get("attempt_id")
            epoch = cache.get("epoch")
    else:
        if attempt_id is None and cache.get("project") == slug and cache.get("ref") == ref:
            attempt_id = cache.get("attempt_id")
        if epoch is None and cache.get("project") == slug and cache.get("ref") == ref:
            epoch = cache.get("epoch")
    return project, ref, attempt_id, epoch


def cmd_heartbeat(conn, slug, args, actor, observed_at, fact, host):
    _p, ref, attempt_id, epoch = _resolve_owner(conn, slug, args)
    if not ref:
        raise TaskStateError("validation_failed", "heartbeat needs --task or cached claim")
    if attempt_id is None or epoch is None:
        raise TaskStateError("stale_claim", "No claim context for heartbeat")
    payload = {"command": "heartbeat", "project": slug, "ref": ref,
               "attempt": attempt_id, "epoch": int(epoch)}
    def effect():
        task = fetch_task(conn, ref)
        if not caller_match(task, attempt_id, epoch):
            raise TaskStateError("stale_claim", "Claim epoch/attempt does not match %s" % ref)
        update_attempt_facts(conn, attempt_id, fact, observed_at)
        lease = (datetime.datetime.now(datetime.timezone.utc) +
                 datetime.timedelta(seconds=lease_seconds())).replace(microsecond=0).isoformat()
        recorded = now_iso()
        # A lease renewal is not a task change; bumping version would make
        # every heartbeat invalidate a human's --expect-version.
        conn.execute("UPDATE task SET lease_expires_at=?, updated_at=? WHERE task_id=?",
                     (lease, recorded, task["task_id"]))
        version = conn.execute("SELECT version FROM task WHERE task_id=?",
                               (task["task_id"],)).fetchone()["version"]
        return {"ref": ref, "lease_expires_at": lease, "version": version}
    return do_mutation(conn, "heartbeat", args.request_id, payload, actor, None, effect)


def cmd_release(conn, slug, args, actor, observed_at, fact, host):
    _p, ref, attempt_id, epoch = _resolve_owner(conn, slug, args)
    if not ref:
        raise TaskStateError("validation_failed", "release needs --task or cached claim")
    if attempt_id is None or epoch is None:
        raise TaskStateError("stale_claim", "No claim context for release")
    reason = getattr(args, "reason", None)
    payload = {"command": "release", "project": slug, "ref": ref,
               "attempt": attempt_id, "epoch": int(epoch), "reason": reason}
    cache_op = {}
    def effect():
        task = fetch_task(conn, ref)
        if not caller_match(task, attempt_id, epoch):
            raise TaskStateError("stale_claim", "Claim epoch/attempt does not match %s" % ref)
        update_attempt_facts(conn, attempt_id, fact, observed_at)
        recorded = now_iso()
        conn.execute("UPDATE attempt SET ended_at=?, end='released' WHERE attempt_id=?",
                     (recorded, attempt_id))
        conn.execute("UPDATE task SET owner_attempt=NULL, lifecycle='open', version=version+1, "
                     "updated_at=? WHERE task_id=?", (recorded, task["task_id"]))
        if reason:
            conn.execute("INSERT INTO journal(entry_id, task_id, attempt_id, kind, body, status, late, actor, "
                         "host, observed_at, recorded_at) VALUES(?,?,?,?,?,'resolved',0,?,?,?,?)",
                         (new_uuid4(), task["task_id"], attempt_id, "note",
                          "release: " + str(reason), actor, host, observed_at, recorded))
        version = conn.execute("SELECT version FROM task WHERE task_id=?",
                               (task["task_id"],)).fetchone()["version"]
        cache_op["clear"] = True
        return {"ref": ref, "version": version}
    result = do_mutation(conn, "release", args.request_id, payload, actor, None, effect)
    if cache_op.get("clear") and not getattr(do_mutation, "last_replay", False):
        clear_cache(slug, ref, attempt_id, epoch)
    return result


def cmd_takeover(conn, slug, args, actor, observed_at, fact, host):
    ref = getattr(args, "ref", None) or getattr(args, "task", None)
    if not ref:
        raise TaskStateError("validation_failed", "takeover needs a REF")
    reason = (getattr(args, "reason", None) or "").strip()
    if not reason:
        raise TaskStateError("validation_failed", "takeover needs --reason")
    force = bool(getattr(args, "force", False))
    payload = {"command": "takeover", "project": slug, "ref": ref,
               "reason": reason, "force": force}
    cache_op = {}
    def effect():
        task = fetch_task(conn, ref)
        if not task.get("owner_attempt"):
            raise TaskStateError("takeover_not_needed", "Task %s is not claimed" % ref)
        if task.get("hold"):
            raise TaskStateError("on_hold", "Task %s is on hold" % ref)
        if task.get("spec_id"):
            auth = domain.authorization(task, all_grants(conn))
            if not auth.get("execute"):
                raise TaskStateError("not_authorized", "No execute grant covers %s" % ref)
        now = datetime.datetime.now(datetime.timezone.utc)
        lease = domain.parse_time(task.get("lease_expires_at"))
        expired = lease is not None and lease <= now
        if not expired and not force:
            raise TaskStateError("lease_active", "Owner lease still active; use --force (human-only)")
        if force:
            require_human(args_human)
        old_attempt = task.get("owner_attempt")
        recorded = now_iso()
        conn.execute("UPDATE attempt SET ended_at=?, end='superseded' WHERE attempt_id=?",
                     (recorded, old_attempt))
        new_epoch = int(task.get("claim_epoch") or 0) + 1
        new_attempt = new_uuid4()
        lease_new = (now + datetime.timedelta(seconds=lease_seconds())).replace(
            microsecond=0).isoformat()
        conn.execute("UPDATE task SET claim_epoch=?, owner_attempt=?, lifecycle='active', "
                     "lease_expires_at=?, version=version+1, updated_at=? WHERE task_id=?",
                     (new_epoch, new_attempt, lease_new, recorded, task["task_id"]))
        conn.execute("INSERT INTO attempt(attempt_id, task_id, claim_epoch, actor, host, worktree, branch, "
                     "start_head, start_diff_hash, last_head, last_diff_hash, facts_observed_at, started_at) "
                     "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (new_attempt, task["task_id"], new_epoch, actor, host, fact.get("worktree"),
                      fact.get("branch"), fact.get("head"), fact.get("diff_hash"), fact.get("head"),
                      fact.get("diff_hash"), observed_at, recorded))
        # Record the reason as a note-less journal? Keep takeover reason in result + journal note.
        conn.execute("INSERT INTO journal(entry_id, task_id, attempt_id, kind, body, status, late, actor, "
                     "host, observed_at, recorded_at) VALUES(?,?,?,?,?,'resolved',0,?,?,?,?)",
                     (new_uuid4(), task["task_id"], new_attempt, "note",
                      "takeover: " + reason, actor, host, observed_at, recorded))
        cache_op["write"] = (slug, ref, new_attempt, new_epoch)
        version = conn.execute("SELECT version FROM task WHERE task_id=?",
                               (task["task_id"],)).fetchone()["version"]
        return {"ref": ref, "attempt_id": new_attempt, "epoch": new_epoch,
                "lease_expires_at": lease_new, "version": version}
    result = do_mutation(conn, "takeover", args.request_id, payload, actor, None, effect)
    if cache_op.get("write") and not getattr(do_mutation, "last_replay", False):
        write_cache(*cache_op["write"])
    return result


def cmd_note(conn, slug, args, actor, observed_at, fact, host):
    _p, ref, attempt_id, epoch = _resolve_owner(conn, slug, args)
    if not ref:
        raise TaskStateError("validation_failed", "note needs --task or cached claim")
    kind = args.kind
    if kind not in ("decision", "finding", "failed_approach", "blocker", "question",
                    "progress", "handoff", "note"):
        raise TaskStateError("validation_failed", "Bad note kind: %r" % kind)
    body = (args.body or "")
    if not body.strip():
        raise TaskStateError("validation_failed", "note needs --body")
    data_raw = getattr(args, "data", None)
    if data_raw:
        try:
            data_obj = json.loads(data_raw)
        except ValueError:
            raise TaskStateError("validation_failed", "note --data must be JSON")
        data_json = json.dumps(data_obj, sort_keys=True)
    else:
        data_json = None
    supersedes = getattr(args, "supersedes", None)
    resolves = getattr(args, "resolves", None)
    payload = {"command": "note", "project": slug, "ref": ref, "kind": kind, "body": body,
               "data": data_json, "supersedes": supersedes, "resolves": resolves,
               "attempt": attempt_id, "epoch": epoch}
    def effect():
        task = fetch_task(conn, ref)
        if attempt_id is None:
            late = 0
            eff_attempt = None
        elif caller_match(task, attempt_id, epoch):
            late = 0
            eff_attempt = attempt_id
            update_attempt_facts(conn, attempt_id, fact, observed_at)
            set_attempt_checkpoint(conn, attempt_id, fact, observed_at)
        else:
            late = 1
            eff_attempt = attempt_id
        if kind in ("question", "blocker", "decision"):
            status = "open"
        else:
            status = "resolved"
        entry_id = new_uuid4()
        recorded = now_iso()
        conn.execute("INSERT INTO journal(entry_id, task_id, attempt_id, kind, body, data_json, status, "
                     "late, actor, host, observed_at, recorded_at, request_id) "
                     "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (entry_id, task["task_id"], eff_attempt, kind, body, data_json, status,
                       late, actor, host, observed_at, recorded, args.request_id))
        applied = {"superseded": False, "resolved": False}
        if not late:
            if supersedes:
                tgt = conn.execute("SELECT entry_id, task_id FROM journal WHERE entry_id=?",
                                   (supersedes,)).fetchone()
                if tgt is None or tgt["task_id"] != task["task_id"]:
                    raise TaskStateError("validation_failed", "Unknown --supersedes entry")
                conn.execute("UPDATE journal SET status='superseded', superseded_by=? WHERE entry_id=?",
                             (entry_id, supersedes))
                applied["superseded"] = True
            if resolves:
                tgt = conn.execute("SELECT entry_id, task_id FROM journal WHERE entry_id=?",
                                   (resolves,)).fetchone()
                if tgt is None or tgt["task_id"] != task["task_id"]:
                    raise TaskStateError("validation_failed", "Unknown --resolves entry")
                conn.execute("UPDATE journal SET status='resolved' WHERE entry_id=?", (resolves,))
                applied["resolved"] = True
        return {"entry_id": entry_id, "late": late, "status": status, "applied": applied}
    return do_mutation(conn, "note", args.request_id, payload, actor, None, effect)


def cmd_evidence(conn, slug, args, actor, observed_at, fact, host):
    _p, ref, attempt_id, epoch = _resolve_owner(conn, slug, args)
    if not ref:
        raise TaskStateError("validation_failed", "evidence needs --task or cached claim")
    kind = args.kind
    result = args.result
    if kind not in ("test", "check", "review", "run", "manual"):
        raise TaskStateError("validation_failed", "Bad evidence kind: %r" % kind)
    if result not in ("pass", "fail", "inconclusive", "unavailable"):
        raise TaskStateError("validation_failed", "Bad evidence result: %r" % result)
    ac_list = split_list(getattr(args, "criteria", None) or [])
    artifacts = {}
    for raw in (getattr(args, "artifact", None) or []):
        if "=" not in raw:
            raise TaskStateError("validation_failed", "Artifact must be path=sha256, got %r" % raw)
        k, v = raw.split("=", 1)
        artifacts[k.strip()] = v.strip()
    payload = {"command": "evidence", "project": slug, "ref": ref, "kind": kind, "result": result,
               "criteria": sorted(ac_list), "cmd": getattr(args, "command", None),
               "summary": getattr(args, "summary", None), "artifacts": artifacts,
               "attempt": attempt_id, "epoch": epoch}
    def effect():
        task = fetch_task(conn, ref)
        known = {c["ac_id"] for c in task_criteria(conn, task["task_id"])}
        for ac in ac_list:
            if ac not in known:
                raise TaskStateError("validation_failed", "Unknown criterion %s for %s" % (ac, ref))
        if attempt_id is None:
            late = 0
            eff_attempt = None
        elif caller_match(task, attempt_id, epoch):
            late = 0
            eff_attempt = attempt_id
            update_attempt_facts(conn, attempt_id, fact, observed_at)
            set_attempt_checkpoint(conn, attempt_id, fact, observed_at)
        else:
            late = 1
            eff_attempt = attempt_id
        eid = new_uuid4()
        recorded = now_iso()
        inputs = {"commit": fact.get("head"), "diff_hash": fact.get("diff_hash"),
                  "branch": fact.get("branch"), "worktree": fact.get("worktree")}
        conn.execute("INSERT INTO evidence(evidence_id, task_id, attempt_id, criteria_json, kind, result, "
                     "command, summary, inputs_json, artifact_refs_json, late, actor, host, observed_at, "
                     "recorded_at, request_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (eid, task["task_id"], eff_attempt, json.dumps(sorted(ac_list)),
                       kind, result, getattr(args, "command", None), getattr(args, "summary", None),
                       json.dumps(inputs, sort_keys=True), json.dumps(artifacts, sort_keys=True),
                       late, actor, host, observed_at, recorded, args.request_id))
        return {"evidence_id": eid, "late": late}
    return do_mutation(conn, "evidence", args.request_id, payload, actor, None, effect)


def cmd_verify(conn, slug, args, actor, observed_at, fact, host):
    _p, ref, attempt_id, epoch = _resolve_owner(conn, slug, args)
    if not ref:
        raise TaskStateError("validation_failed", "verify needs --task or cached claim")
    if attempt_id is None or epoch is None:
        raise TaskStateError("stale_claim", "No claim context for verify")
    payload = {"command": "verify", "project": slug, "ref": ref,
               "attempt": attempt_id, "epoch": int(epoch)}
    cache_op = {}
    def effect():
        task = fetch_task(conn, ref)
        if not caller_match(task, attempt_id, epoch):
            raise TaskStateError("stale_claim", "Claim epoch/attempt does not match %s" % ref)
        update_attempt_facts(conn, attempt_id, fact, observed_at)
        exp_head, exp_diff, _ = expected_inputs(conn, task)
        crit = task_criteria(conn, task["task_id"])
        ev_rows = [_row_dict(r) for r in conn.execute(
            "SELECT * FROM evidence WHERE task_id=?", (task["task_id"],)).fetchall()]
        gaps = domain.verify_gaps(task, crit, ev_rows, exp_head, exp_diff)
        if gaps:
            raise TaskStateError("verification_incomplete",
                                 "Task %s is not ready to verify" % ref, details=gaps)
        import json as _json
        unknowns = []
        live_rows = [e for e in ev_rows if not e.get("late")]
        if crit:
            for c in crit:
                ac = c["ac_id"]
                best = None
                for e in live_rows:
                    try:
                        acs = _json.loads(e.get("criteria_json") or "[]")
                    except Exception:
                        acs = []
                    if ac in acs and e.get("result") == "pass":
                        if best is None or str(e.get("recorded_at") or "") >= str(best.get("recorded_at") or ""):
                            best = e
                if best is not None and domain.evidence_freshness(best, exp_head, exp_diff) == "unknown":
                    unknowns.append(ac)
        else:
            for e in live_rows:
                if e.get("result") == "pass" and domain._is_task_level(e) and \
                        domain.evidence_freshness(e, exp_head, exp_diff) == "unknown":
                    unknowns = ["task"]
                    break
        recorded = now_iso()
        set_attempt_checkpoint(conn, attempt_id, fact, observed_at)
        conn.execute("UPDATE attempt SET ended_at=?, end='verified' WHERE attempt_id=?",
                     (recorded, attempt_id))
        conn.execute("UPDATE task SET owner_attempt=NULL, lifecycle='verified', version=version+1, "
                     "updated_at=? WHERE task_id=?", (recorded, task["task_id"]))
        version = conn.execute("SELECT version FROM task WHERE task_id=?",
                               (task["task_id"],)).fetchone()["version"]
        cache_op["clear"] = True
        return {"ref": ref, "version": version, "lifecycle": "verified",
                "freshness_unknown": unknowns}
    result = do_mutation(conn, "verify", args.request_id, payload, actor, None, effect)
    if cache_op.get("clear") and not getattr(do_mutation, "last_replay", False):
        clear_cache(slug, ref, attempt_id, epoch)
    return result


def _expect_version_check(task, expect):
    if expect is None:
        raise TaskStateError("validation_failed", "This command needs --expect-version")
    try:
        expect = int(expect)
    except (TypeError, ValueError):
        raise TaskStateError("validation_failed", "Bad --expect-version")
    if int(task.get("version") or 0) != expect:
        raise TaskStateError("stale_version",
                             "Task %s version %s != expected %s" % (task["ref"], task["version"], expect))


def cmd_task_hold(conn, slug, args, actor, observed_at, fact, host):
    require_human(args_human)
    ref = getattr(args, "ref", None) or getattr(args, "task", None)
    payload = {"command": "task.hold", "project": slug, "ref": ref,
               "reason": args.reason, "expect_version": getattr(args, "expect_version", None)}
    def effect():
        task = fetch_task(conn, ref)
        _expect_version_check(task, getattr(args, "expect_version", None))
        recorded = now_iso()
        conn.execute("UPDATE task SET hold=1, hold_reason=?, version=version+1, updated_at=? WHERE task_id=?",
                     (args.reason, recorded, task["task_id"]))
        version = conn.execute("SELECT version FROM task WHERE task_id=?",
                               (task["task_id"],)).fetchone()["version"]
        return {"ref": ref, "version": version, "hold": 1}
    return do_mutation(conn, "task.hold", args.request_id, payload, actor, None, effect)


def cmd_task_unhold(conn, slug, args, actor, observed_at, fact, host):
    require_human(args_human)
    ref = getattr(args, "ref", None) or getattr(args, "task", None)
    payload = {"command": "task.unhold", "project": slug, "ref": ref,
               "expect_version": getattr(args, "expect_version", None)}
    def effect():
        task = fetch_task(conn, ref)
        _expect_version_check(task, getattr(args, "expect_version", None))
        recorded = now_iso()
        conn.execute("UPDATE task SET hold=0, hold_reason=NULL, version=version+1, updated_at=? "
                     "WHERE task_id=?", (recorded, task["task_id"]))
        version = conn.execute("SELECT version FROM task WHERE task_id=?",
                               (task["task_id"],)).fetchone()["version"]
        return {"ref": ref, "version": version, "hold": 0}
    return do_mutation(conn, "task.unhold", args.request_id, payload, actor, None, effect)


def cmd_task_cancel(conn, slug, args, actor, observed_at, fact, host):
    require_human(args_human)
    ref = getattr(args, "ref", None) or getattr(args, "task", None)
    payload = {"command": "task.cancel", "project": slug, "ref": ref,
               "expect_version": getattr(args, "expect_version", None)}
    def effect():
        task = fetch_task(conn, ref)
        _expect_version_check(task, getattr(args, "expect_version", None))
        if task["lifecycle"] in ("accepted", "cancelled", "superseded"):
            raise TaskStateError("invalid_lifecycle", "Cannot cancel task in %s" % task["lifecycle"])
        recorded = now_iso()
        if task.get("lifecycle") == "active" and task.get("owner_attempt"):
            conn.execute("UPDATE attempt SET ended_at=?, end='cancelled' WHERE attempt_id=?",
                         (recorded, task["owner_attempt"]))
            conn.execute("UPDATE task SET lifecycle='cancelled', owner_attempt=NULL, "
                         "lease_expires_at=NULL, version=version+1, updated_at=? WHERE task_id=?",
                         (recorded, task["task_id"]))
        else:
            conn.execute("UPDATE task SET lifecycle='cancelled', version=version+1, updated_at=? WHERE task_id=?",
                         (recorded, task["task_id"]))
        version = conn.execute("SELECT version FROM task WHERE task_id=?",
                               (task["task_id"],)).fetchone()["version"]
        return {"ref": ref, "lifecycle": "cancelled", "version": version}
    return do_mutation(conn, "task.cancel", args.request_id, payload, actor, None, effect)


def cmd_accept(conn, slug, args, actor, observed_at, fact, host):
    require_human(args_human)
    ref = getattr(args, "ref", None) or getattr(args, "task", None)
    payload = {"command": "accept", "project": slug, "ref": ref,
               "expect_version": getattr(args, "expect_version", None)}
    def effect():
        task = fetch_task(conn, ref)
        _expect_version_check(task, getattr(args, "expect_version", None))
        if task["lifecycle"] != "verified":
            raise TaskStateError("invalid_lifecycle", "Only verified tasks can be accepted")
        recorded = now_iso()
        conn.execute("UPDATE task SET lifecycle='accepted', version=version+1, updated_at=? WHERE task_id=?",
                     (recorded, task["task_id"]))
        version = conn.execute("SELECT version FROM task WHERE task_id=?",
                               (task["task_id"],)).fetchone()["version"]
        return {"ref": ref, "lifecycle": "accepted", "version": version}
    return do_mutation(conn, "accept", args.request_id, payload, actor, None, effect)


def cmd_reopen(conn, slug, args, actor, observed_at, fact, host):
    require_human(args_human)
    ref = getattr(args, "ref", None) or getattr(args, "task", None)
    payload = {"command": "reopen", "project": slug, "ref": ref,
               "expect_version": getattr(args, "expect_version", None)}
    def effect():
        task = fetch_task(conn, ref)
        _expect_version_check(task, getattr(args, "expect_version", None))
        if task["lifecycle"] not in ("verified", "accepted"):
            raise TaskStateError("invalid_lifecycle", "Only verified/accepted tasks can be reopened")
        recorded = now_iso()
        conn.execute("UPDATE task SET lifecycle='open', version=version+1, updated_at=? WHERE task_id=?",
                     (recorded, task["task_id"]))
        version = conn.execute("SELECT version FROM task WHERE task_id=?",
                               (task["task_id"],)).fetchone()["version"]
        return {"ref": ref, "lifecycle": "open", "version": version}
    return do_mutation(conn, "reopen", args.request_id, payload, actor, None, effect)


def cmd_handoff(conn, slug, args, actor, observed_at, fact, host):
    _p, ref, attempt_id, epoch = _resolve_owner(conn, slug, args)
    if not ref:
        raise TaskStateError("validation_failed", "handoff needs --task or cached claim")
    next_action = (getattr(args, "next_action", None) or "").strip()
    if not next_action:
        raise TaskStateError("validation_failed", "handoff needs --next-action")
    risks = getattr(args, "risk", None) or []
    dnr = getattr(args, "do_not_repeat", None) or []
    summary = getattr(args, "summary", None)
    release = bool(getattr(args, "release", False))
    payload = {"command": "handoff", "project": slug, "ref": ref, "next_action": next_action,
               "risks": risks, "do_not_repeat": dnr, "summary": summary, "release": release,
               "attempt": attempt_id, "epoch": epoch}
    cache_op = {}
    def effect():
        task = fetch_task(conn, ref)
        if attempt_id is None:
            late = 0
            eff_attempt = None
            owner_match = False
        elif caller_match(task, attempt_id, epoch):
            late = 0
            eff_attempt = attempt_id
            update_attempt_facts(conn, attempt_id, fact, observed_at)
            set_attempt_checkpoint(conn, attempt_id, fact, observed_at)
            owner_match = True
        else:
            late = 1
            eff_attempt = attempt_id
            owner_match = False
        diffstat = None
        wt = fact.get("worktree")
        if wt:
            try:
                import subprocess as _sp
                p = _sp.run(["git", "diff", "HEAD", "--stat", "--no-color"],
                            cwd=wt, capture_output=True, timeout=10)
                if p.returncode == 0:
                    diffstat = p.stdout.decode("utf-8", errors="replace")[:2000]
            except Exception:
                diffstat = None
        dh = fact.get("diff_hash")
        dirty = None if dh is None else bool(dh != facts.EMPTY_HASH)
        data = {"next_action": next_action, "risks": risks, "do_not_repeat": dnr,
                "summary": summary,
                "facts": {"head": fact.get("head"), "branch": fact.get("branch"),
                          "worktree": fact.get("worktree"), "diff_hash": dh,
                          "dirty": dirty, "diffstat": diffstat}}
        entry_id = new_uuid4()
        recorded = now_iso()
        conn.execute("INSERT INTO journal(entry_id, task_id, attempt_id, kind, body, data_json, status, "
                     "late, actor, host, observed_at, recorded_at, request_id) "
                     "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (entry_id, task["task_id"], eff_attempt, "handoff",
                      summary or next_action, json.dumps(data, sort_keys=True), "resolved",
                      late, actor, host, observed_at, recorded, args.request_id))
        released = False
        if release and not late and owner_match and eff_attempt is not None:
            conn.execute("UPDATE attempt SET ended_at=?, end='handed_off' WHERE attempt_id=?",
                         (recorded, eff_attempt))
            conn.execute("UPDATE task SET owner_attempt=NULL, lifecycle='open', version=version+1, "
                         "updated_at=? WHERE task_id=?", (recorded, task["task_id"]))
            cache_op["clear"] = True
            released = True
        return {"entry_id": entry_id, "late": late, "released": released}
    result = do_mutation(conn, "handoff", args.request_id, payload, actor, None, effect)
    if cache_op.get("clear") and not getattr(do_mutation, "last_replay", False):
        clear_cache(slug, ref, attempt_id, epoch)
    return result


# --- read commands ----------------------------------------------------------------

def cmd_project_show(conn, slug):
    row = conn.execute("SELECT * FROM project WHERE slug=?", (slug,)).fetchone()
    if row is None:
        raise TaskStateError("project_not_found", "Unknown project: %s" % slug)
    return {"project": _row_dict(row)}


def cmd_context(conn, slug, args, live=None):
    ref = getattr(args, "ref", None) or getattr(args, "task", None)
    if not ref:
        cache = read_cache()
        ref = cache.get("ref")
    if not ref:
        raise TaskStateError("validation_failed", "context needs a REF or cached claim")
    task = fetch_task(conn, ref)
    return build_context(conn, slug, task, live)


def cmd_attention(root, slug, args, live=None):
    if getattr(args, "all", False):
        items = []
        for db in sorted(root.glob("*.db")):
            s = db.stem
            try:
                conn = store_mod.connect(db)
            except Exception as exc:
                items.append({"type": "store_error", "project": s, "since": None,
                              "detail": str(exc)[:500]})
                continue
            try:
                store_mod.ensure_schema(conn, slug=s, root=root)
                items.extend(attention_for_conn(conn, s))
            except Exception as exc:
                items.append({"type": "store_error", "project": s, "since": None,
                              "detail": str(exc)[:500]})
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        return {"items": items}
    if not slug:
        raise TaskStateError("validation_failed", "attention needs --project or --all")
    conn, _ = store_mod.open_project_db(slug, root=root)
    try:
        return {"items": attention_for_conn(conn, slug, live)}
    finally:
        conn.close()


# --- argparse -----------------------------------------------------------------------

def add_common(p):
    p.add_argument("--project", default=None)
    p.add_argument("--task", default=None)
    p.add_argument("--attempt", default=None)
    p.add_argument("--epoch", default=None, type=int)
    p.add_argument("--actor", default=None)
    p.add_argument("--observed-at", default=None)
    p.add_argument("--request-id", default=None)
    p.add_argument("--json", action="store_true")


def build_parser():
    ap = argparse.ArgumentParser(prog="taskstate", description="taskstate Phase 1 local core")
    ap.add_argument("--json", action="store_true", help="no-op, output is always JSON")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("project"); ps = p.add_subparsers(dest="sub", required=True)
    pi = ps.add_parser("init"); pi.add_argument("--slug", required=True)
    pi.add_argument("--disclosure", default="internal", choices=["public", "internal", "restricted"])
    add_common(pi)
    psh = ps.add_parser("show"); add_common(psh)

    t = sub.add_parser("task"); ts = t.add_subparsers(dest="sub", required=True)
    ta = ts.add_parser("add"); ta.add_argument("--title", required=True)
    ta.add_argument("--kind", default="code", choices=["code", "research", "operation"])
    ta.add_argument("--spec-id", default=None)
    ta.add_argument("--criterion", action="append", default=[])
    ta.add_argument("--depends-on", action="append", default=[])
    add_common(ta)
    tsh = ts.add_parser("show"); tsh.add_argument("ref", nargs="?"); add_common(tsh)
    th = ts.add_parser("hold"); th.add_argument("ref", nargs="?"); th.add_argument("--reason", required=True)
    th.add_argument("--expect-version", required=True); add_common(th)
    tu = ts.add_parser("unhold"); tu.add_argument("ref", nargs="?")
    tu.add_argument("--expect-version", required=True); add_common(tu)
    tc = ts.add_parser("cancel"); tc.add_argument("ref", nargs="?")
    tc.add_argument("--expect-version", required=True); add_common(tc)

    g = sub.add_parser("grant"); gs = g.add_subparsers(dest="sub", required=True)
    ga = gs.add_parser("add"); ga.add_argument("--kind", required=True, choices=["execute", "publish"])
    ga.add_argument("--task", action="append", default=[], dest="task")
    ga.add_argument("--tasks", action="append", default=[])
    ga.add_argument("--scope-project", action="store_true", default=False)
    ga.add_argument("--project-scope", action="store_true", default=False)
    ga.add_argument("--source", required=True)
    ga.add_argument("--project", default=None); ga.add_argument("--actor", default=None)
    ga.add_argument("--observed-at", default=None); ga.add_argument("--request-id", default=None)
    ga.add_argument("--json", action="store_true"); ga.add_argument("--attempt", default=None)
    ga.add_argument("--epoch", default=None, type=int)

    c = sub.add_parser("claim"); c.add_argument("ref", nargs="?")
    c.add_argument("--new", default=None)
    c.add_argument("--kind", default="code", choices=["code", "research", "operation"])
    c.add_argument("--criterion", action="append", default=[])
    add_common(c)

    h = sub.add_parser("heartbeat"); add_common(h)
    r = sub.add_parser("release"); r.add_argument("--reason", default=None); add_common(r)
    to = sub.add_parser("takeover"); to.add_argument("ref", nargs="?")
    to.add_argument("--reason", required=True); to.add_argument("--force", action="store_true")
    add_common(to)

    n = sub.add_parser("note"); n.add_argument("--kind", required=True)
    n.add_argument("--body", required=True); n.add_argument("--data", default=None)
    n.add_argument("--supersedes", default=None); n.add_argument("--resolves", default=None)
    add_common(n)

    e = sub.add_parser("evidence"); e.add_argument("--result", required=True)
    e.add_argument("--kind", required=True)
    e.add_argument("--criteria", action="append", default=[])
    e.add_argument("--command", default=None); e.add_argument("--summary", default=None)
    e.add_argument("--artifact", action="append", default=[])
    add_common(e)

    v = sub.add_parser("verify"); add_common(v)
    a = sub.add_parser("accept"); a.add_argument("ref", nargs="?")
    a.add_argument("--expect-version", required=True); add_common(a)
    ro = sub.add_parser("reopen"); ro.add_argument("ref", nargs="?")
    ro.add_argument("--expect-version", required=True); add_common(ro)

    ho = sub.add_parser("handoff"); ho.add_argument("--next-action", required=True)
    ho.add_argument("--risk", action="append", default=[])
    ho.add_argument("--do-not-repeat", action="append", default=[], dest="do_not_repeat")
    ho.add_argument("--summary", default=None); ho.add_argument("--release", action="store_true")
    add_common(ho)

    cx = sub.add_parser("context"); cx.add_argument("ref", nargs="?"); add_common(cx)
    at = sub.add_parser("attention"); at.add_argument("--all", action="store_true")
    add_common(at)
    b = sub.add_parser("backup"); add_common(b)
    ex = sub.add_parser("export"); ex.add_argument("--out", required=True); add_common(ex)
    hp = sub.add_parser("hook")
    hp.add_argument("event", choices=["session-start", "stop", "pre-tool-use", "session-end", "replay", "guard"])
    hp.add_argument("--runtime", required=True, choices=["claude", "codex"])
    return ap


args_human = None


def require_project_row(conn, slug):
    row = conn.execute("SELECT slug FROM project WHERE slug=?", (slug,)).fetchone()
    if row is None:
        raise TaskStateError("project_not_found", "Unknown project: %s" % slug)


def _resolve_slug(args):
    slug = getattr(args, "project", None)
    if slug:
        return slug
    cache = read_cache()
    if cache.get("project"):
        return cache["project"]
    # project init/show path: slug may come from --slug
    if getattr(args, "slug", None):
        return args.slug
    # attention --all / backup / export without project handled by caller
    return None


def _requires_human(args):
    cmd = getattr(args, "cmd", None)
    if cmd == "project" and getattr(args, "sub", None) == "init":
        return True
    if cmd == "grant" and getattr(args, "sub", None) == "add":
        return True
    if cmd == "takeover" and getattr(args, "force", False):
        return True
    if cmd in {"accept", "reopen"}:
        return True
    if cmd == "task" and getattr(args, "sub", None) in {"hold", "unhold", "cancel"}:
        return True
    return False


def run(argv=None, human=None):
    global args_human
    args_human = human
    ap = build_parser()
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        if getattr(exc, "code", 2) == 0:
            raise
        return 2, {"ok": False, "error": {"code": "validation_failed",
                                          "message": "Argument parsing failed"}}
    cmd = args.cmd
    if _requires_human(args) and not is_human_allowed(human):
        return 2, {"ok": False, "error": {
            "code": "human_only",
            "message": "This command is human-only (interactive TTY without agent session required)"}}
    if cmd == "hook":
        import hooks
        event = "pre-tool-use" if args.event == "guard" else args.event
        code, output = hooks.run_cli([event, "--runtime", args.runtime])
        if output is None:
            return code, {"ok": True, "result": {"event": event, "runtime": args.runtime}}
        return code, output
    actor = current_actor(getattr(args, "actor", None))
    host = current_host()
    if hasattr(args, "request_id") and not getattr(args, "request_id", None):
        args.request_id = new_uuid4()
    observed_at = parse_observed(getattr(args, "observed_at", None))
    fact = facts.collect()
    root = store_mod.state_root()
    try:
        if cmd == "project" and args.sub == "init":
            slug = args.slug
            conn, _ = store_mod.open_project_db(slug, root=root)
            try:
                result = cmd_project_init(conn, slug, args, actor, observed_at, fact, host)
                seq = store_mod.db_seq(conn)
                store_mod.maybe_daily_backup(conn, slug, root=root)
            finally:
                conn.close()
            return 0, {"ok": True, "result": result, "db_seq": seq}
        if cmd == "project" and args.sub == "show":
            slug = _resolve_slug(args)
            if not slug:
                raise TaskStateError("validation_failed", "project show needs --project")
            conn, _ = store_mod.open_project_db(slug, root=root)
            try:
                result = cmd_project_show(conn, slug)
                seq = store_mod.db_seq(conn)
            finally:
                conn.close()
            return 0, {"ok": True, "result": result, "db_seq": seq}
        if cmd == "attention":
            slug = _resolve_slug(args)
            if getattr(args, "all", False):
                result = cmd_attention(root, None, args, fact)
                # db_seq across all: max
                seq = 0
                for db in root.glob("*.db"):
                    try:
                        c = store_mod.connect(db)
                        seq = max(seq, store_mod.db_seq(c))
                        c.close()
                    except sqlite3.Error:
                        pass
                return 0, {"ok": True, "result": result, "db_seq": seq}
            if not slug:
                raise TaskStateError("validation_failed", "attention needs --project or --all")
            result = cmd_attention(root, slug, args, fact)
            conn, _ = store_mod.open_project_db(slug, root=root)
            try:
                require_project_row(conn, slug)
                seq = store_mod.db_seq(conn)
            finally:
                conn.close()
            return 0, {"ok": True, "result": result, "db_seq": seq}
        if cmd == "backup":
            slug = _resolve_slug(args)
            if slug:
                slugs = [slug]
            else:
                cache = read_cache()
                slugs = [cache["project"]] if cache.get("project") else \
                    [p.stem for p in sorted(root.glob("*.db"))]
                if not slugs:
                    raise TaskStateError("validation_failed", "backup needs --project")
            paths = []
            for s in slugs:
                conn, _ = store_mod.open_project_db(s, root=root)
                try:
                    paths.append(store_mod.backup_db(conn, s, root=root))
                finally:
                    conn.close()
            # db_seq of first
            conn, _ = store_mod.open_project_db(slugs[0], root=root)
            try:
                seq = store_mod.db_seq(conn)
            finally:
                conn.close()
            return 0, {"ok": True, "result": {"backups": paths}, "db_seq": seq}
        if cmd == "export":
            slug = _resolve_slug(args)
            if not slug:
                raise TaskStateError("validation_failed", "export needs --project")
            conn, _ = store_mod.open_project_db(slug, root=root)
            try:
                require_project_row(conn, slug)
                written = store_mod.export_db(conn, args.out)
                seq = store_mod.db_seq(conn)
            finally:
                conn.close()
            return 0, {"ok": True, "result": {"files": written}, "db_seq": seq}
        # all remaining commands need a project slug
        slug = _resolve_slug(args)
        if not slug:
            raise TaskStateError("validation_failed", "This command needs --project (or cached project)")
        conn, _ = store_mod.open_project_db(slug, root=root)
        try:
            require_project_row(conn, slug)
            if cmd == "task" and args.sub == "add":
                result = cmd_task_add(conn, slug, args, actor, observed_at, fact, host)
            elif cmd == "task" and args.sub == "show":
                ref = args.ref or args.task or read_cache().get("ref")
                if not ref:
                    raise TaskStateError("validation_failed", "task show needs a REF")
                result = task_view(conn, fetch_task(conn, ref), fact)
            elif cmd == "task" and args.sub == "hold":
                result = cmd_task_hold(conn, slug, args, actor, observed_at, fact, host)
            elif cmd == "task" and args.sub == "unhold":
                result = cmd_task_unhold(conn, slug, args, actor, observed_at, fact, host)
            elif cmd == "task" and args.sub == "cancel":
                result = cmd_task_cancel(conn, slug, args, actor, observed_at, fact, host)
            elif cmd == "grant" and args.sub == "add":
                result = cmd_grant_add(conn, slug, args, actor, observed_at, fact, host)
            elif cmd == "claim":
                result = cmd_claim(conn, slug, args, actor, observed_at, fact, host)
            elif cmd == "heartbeat":
                result = cmd_heartbeat(conn, slug, args, actor, observed_at, fact, host)
            elif cmd == "release":
                result = cmd_release(conn, slug, args, actor, observed_at, fact, host)
            elif cmd == "takeover":
                result = cmd_takeover(conn, slug, args, actor, observed_at, fact, host)
            elif cmd == "note":
                result = cmd_note(conn, slug, args, actor, observed_at, fact, host)
            elif cmd == "evidence":
                result = cmd_evidence(conn, slug, args, actor, observed_at, fact, host)
            elif cmd == "verify":
                result = cmd_verify(conn, slug, args, actor, observed_at, fact, host)
            elif cmd == "accept":
                result = cmd_accept(conn, slug, args, actor, observed_at, fact, host)
            elif cmd == "reopen":
                result = cmd_reopen(conn, slug, args, actor, observed_at, fact, host)
            elif cmd == "handoff":
                result = cmd_handoff(conn, slug, args, actor, observed_at, fact, host)
            elif cmd == "context":
                result = cmd_context(conn, slug, args, fact)
                seq = store_mod.db_seq(conn)
                return 0, {"ok": True, "result": result, "db_seq": seq}
            else:
                raise TaskStateError("validation_failed", "Unknown command")
            seq = store_mod.db_seq(conn)
            if cmd not in ("context",):
                try:
                    store_mod.maybe_daily_backup(conn, slug, root=root)
                except Exception:
                    pass
            return 0, {"ok": True, "result": result, "db_seq": seq}
        finally:
            conn.close()
    except TaskStateError as exc:
        payload = {"ok": False, "error": {"code": exc.code, "message": exc.message}}
        if exc.details:
            payload["error"]["details"] = exc.details
        return 2, payload
    except store_mod.StoreError as exc:
        return 2, {"ok": False, "error": {"code": exc.code, "message": exc.message}}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "render":
        import render
        code, output = render.main(sys.argv[2:])
        sys.stdout.write(output)
        sys.exit(code)
    if len(sys.argv) > 1 and sys.argv[1] == "hook":
        import hooks
        event = sys.argv[2] if len(sys.argv) > 2 else ""
        runtime = ""
        tail = sys.argv[3:]
        for index, arg in enumerate(tail):
            if arg == "--runtime" and index + 1 < len(tail):
                runtime = tail[index + 1]
                break
            if arg.startswith("--runtime="):
                runtime = arg.split("=", 1)[1]
                break
        if event == "guard":
            event = "pre-tool-use"
        sys.exit(hooks.main([event, "--runtime", runtime]))
    code, payload = run(sys.argv[1:], human=None)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    sys.stdout.flush()
    # Map validation/domain (2) vs ok (0); unexpected handled below.
    sys.exit(code)


if __name__ == "__main__":
    try:
        main()
    except TaskStateError as exc:
        sys.stdout.write(json.dumps(
            {"ok": False, "error": {"code": exc.code, "message": exc.message}}) + "\n")
        sys.exit(2)
    except SystemExit:
        raise
    except Exception as exc:  # unexpected -> exit 1
        sys.stdout.write(json.dumps(
            {"ok": False, "error": {"code": "internal_error", "message": str(exc)}}) + "\n")
        sys.exit(1)
