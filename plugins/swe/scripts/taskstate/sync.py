"""Home-initiated taskstate synchronization and the satellite RPC entry point."""
from __future__ import annotations

import datetime
import json
import os
import shlex
import subprocess

import domain
import registry
import store as store_mod

TASK_COLUMNS = (
    "task_id", "ref", "title", "kind", "spec_id", "lifecycle", "hold",
    "hold_reason", "version", "claim_epoch", "owner_attempt", "lease_expires_at",
    "created_at", "updated_at", "authority_host", "delegation_epoch", "origin_host",
    "revoke_pending", "revoke_force", "synced_at",
)
ATTEMPT_COLUMNS = (
    "attempt_id", "task_id", "claim_epoch", "actor", "host", "worktree", "branch",
    "start_head", "last_head", "last_diff_hash", "facts_observed_at", "started_at",
    "ended_at", "end", "checkpoint_head", "checkpoint_diff_hash", "checkpoint_at",
    "start_diff_hash", "origin_host",
)
JOURNAL_COLUMNS = (
    "entry_id", "task_id", "attempt_id", "kind", "body", "data_json", "status",
    "superseded_by", "late", "actor", "host", "observed_at", "recorded_at",
    "request_id", "origin_host",
)
EVIDENCE_COLUMNS = (
    "evidence_id", "task_id", "attempt_id", "criteria_json", "kind", "result",
    "command", "summary", "inputs_json", "artifact_refs_json", "late", "actor", "host",
    "observed_at", "recorded_at", "request_id", "origin_host",
)
SESSION_COLUMNS = (
    "runtime", "session_id", "attempt_id", "task_id", "host", "cwd", "source",
    "started_at", "last_seen_at", "head", "diff_hash", "end_reason", "end_observed",
    "reminded_head", "reminded_diff_hash", "end_inferred", "origin_host",
)
JOB_COLUMNS = (
    "cluster", "job_id", "task_id", "attempt_id", "submitted_by", "host", "last_state",
    "last_state_at", "exit_code", "acknowledged", "observed_at", "recorded_at",
    "request_id", "origin_host",
)
STATUS_RANK = {"open": 0, "resolved": 1, "superseded": 2}
SYNC_STALE_DEFAULT = 600


class SyncError(Exception):
    def __init__(self, code, message, details=None, unreachable=False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or []
        self.unreachable = unreachable


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")


def parse_time(value):
    if not value:
        return None
    try:
        return domain.parse_time(value)
    except (TypeError, ValueError, OverflowError):
        return None


def meta_key(host, kind):
    return "sync.%s.%s" % (host, kind)


def get_sync_meta(conn, host):
    return {
        "last_sync_ok_at": store_mod.get_meta(conn, meta_key(host, "last_sync_ok_at")),
        "last_sync_error": store_mod.get_meta(conn, meta_key(host, "last_sync_error")),
        "last_sync_at": store_mod.get_meta(conn, "last_sync_at"),
    }


def set_sync_meta(conn, host, kind, value):
    if value is None:
        try:
            conn.execute("DELETE FROM meta WHERE key=?", (meta_key(host, kind),))
        except Exception:
            pass
    else:
        store_mod.set_meta(conn, meta_key(host, kind), value)


def role_for(project):
    try:
        return registry.project_role(project)
    except registry.RegistryError as exc:
        raise SyncError("registry_invalid", str(exc))


def _configured(role):
    return bool(role and role.get("configured"))


def freshness(project, conn=None):
    role = role_for(project)
    if not _configured(role) or role.get("is_home"):
        return {"configured": _configured(role), "home_copy": False,
                "last_sync_at": None, "label": "local"}
    last = store_mod.get_meta(conn, "last_sync_at") if conn is not None else None
    return {"configured": True, "home_copy": True, "last_sync_at": last,
            "label": "home copy as of %s" % (last or "never")}


def _stale_seconds():
    try:
        value = int(os.environ.get("TASKSTATE_SYNC_STALE_SECONDS", str(SYNC_STALE_DEFAULT)))
        return max(0, value)
    except ValueError:
        return SYNC_STALE_DEFAULT


def _rows(conn, query, params=()):
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def _table_rows(conn, table, where="", params=()):
    query = "SELECT * FROM %s" % table
    if where:
        query += " WHERE " + where
    return _rows(conn, query, params)


def _task_int(row, name, default=0):
    try:
        return int(row.get(name) or default)
    except (TypeError, ValueError):
        return default


def _valid_task_row(row):
    return isinstance(row, dict) and isinstance(row.get("task_id"), str) \
        and isinstance(row.get("ref"), str) and isinstance(row.get("title"), str) \
        and isinstance(row.get("kind"), str) and isinstance(row.get("lifecycle"), str) \
        and bool(row.get("task_id")) and bool(row.get("ref"))


def _valid_rows(value):
    return isinstance(value, list) and all(isinstance(item, dict) for item in value)


def _clean_row(row, columns):
    return {column: row.get(column) for column in columns if column in row}


def _select_one(conn, table, column, value):
    return conn.execute("SELECT * FROM %s WHERE %s=?" % (table, column),
                        (value,)).fetchone()


def _select_task(conn, task_id=None, ref=None):
    if task_id:
        row = _select_one(conn, "task", "task_id", task_id)
        if row is not None:
            return dict(row)
    if ref:
        row = _select_one(conn, "task", "ref", ref)
        if row is not None:
            return dict(row)
    return None


def _insert_task(conn, row):
    values = []
    for column in TASK_COLUMNS:
        value = row.get(column)
        if column == "hold" and value is None:
            value = 0
        if column == "version" and value is None:
            value = 1
        if column == "claim_epoch" and value is None:
            value = 0
        if column == "delegation_epoch" and value is None:
            value = 0
        if column in ("revoke_pending", "revoke_force") and value is None:
            value = 0
        values.append(value)
    conn.execute(
        "INSERT INTO task(%s) VALUES(%s)" % (",".join(TASK_COLUMNS), ",".join("?" for _ in TASK_COLUMNS)),
        tuple(values))


def _update_task(conn, row):
    values = []
    columns = []
    for column in TASK_COLUMNS:
        if column == "task_id":
            continue
        columns.append(column)
        values.append(row.get(column))
    values.append(row.get("task_id"))
    conn.execute("UPDATE task SET %s WHERE task_id=?" % ",".join("%s=?" % c for c in columns),
                 tuple(values))


def _update_related_task_copy(conn, task_id, criteria, deps):
    conn.execute("DELETE FROM criterion WHERE task_id=?", (task_id,))
    conn.execute("DELETE FROM task_dep WHERE task_id=?", (task_id,))
    for criterion in criteria:
        if not isinstance(criterion, dict):
            continue
        ac_id = criterion.get("ac_id")
        text = criterion.get("text")
        if isinstance(ac_id, str) and isinstance(text, str):
            conn.execute("INSERT INTO criterion(task_id,ac_id,text) VALUES(?,?,?)",
                         (task_id, ac_id, text))
    for dependency in deps:
        if not isinstance(dependency, dict):
            continue
        depends_on = dependency.get("depends_on")
        if isinstance(depends_on, str) and _select_task(conn, task_id=depends_on) is not None:
            conn.execute("INSERT OR IGNORE INTO task_dep(task_id,depends_on) VALUES(?,?)",
                         (task_id, depends_on))


def _upsert_owned(conn, table, columns, row, primary, origin):
    if not isinstance(row, dict):
        return False
    if table == "journal":
        if row.get("origin_host") not in (None, origin):
            return False
    elif row.get("origin_host") != origin:
        return False
    values = _clean_row(row, columns)
    defaults = {"end_inferred": 0, "end_observed": 0, "late": 0,
                "acknowledged": 0}
    for column, default in defaults.items():
        if values.get(column) is None:
            values[column] = default
    if any(values.get(column) is None for column in primary):
        return False
    existing = conn.execute(
        "SELECT * FROM %s WHERE %s" % (table, " AND ".join("%s=?" % p for p in primary)),
        tuple(values[p] for p in primary)).fetchone()
    if existing is None:
        names = tuple(columns)
        conn.execute("INSERT INTO %s(%s) VALUES(%s)" %
                     (table, ",".join(names), ",".join("?" for _ in names)),
                     tuple(values.get(name) for name in names))
        return True
    if table == "journal":
        old_status = existing["status"] or "open"
        new_status = values.get("status") or "open"
        if STATUS_RANK.get(new_status, -1) >= STATUS_RANK.get(old_status, -1):
            if STATUS_RANK.get(new_status, -1) > STATUS_RANK.get(old_status, -1) or values.get("superseded_by"):
                conn.execute("UPDATE journal SET status=?, superseded_by=? WHERE entry_id=?",
                             (new_status, existing["superseded_by"] or values.get("superseded_by"),
                              values["entry_id"]))
        return False
    names = [name for name in columns if name not in primary]
    if names:
        conn.execute("UPDATE %s SET %s WHERE %s" %
                     (table, ",".join("%s=?" % name for name in names),
                      " AND ".join("%s=?" % p for p in primary)),
                     tuple(values.get(name) for name in names) + tuple(values[p] for p in primary))
    return False


def _pull_task_rows(conn, satellite):
    tasks = _table_rows(
        conn, "task",
        "authority_host=? OR origin_host=? OR (synced_at IS NOT NULL AND delegation_epoch>0)",
        (satellite, satellite))
    ids = set(row["task_id"] for row in tasks)
    criteria = [row for row in _table_rows(conn, "criterion") if row.get("task_id") in ids]
    deps = [row for row in _table_rows(conn, "task_dep") if row.get("task_id") in ids]
    return tasks, criteria, deps


def _owned_rows(conn, origin):
    result = {}
    for table in ("attempt", "session", "journal", "evidence", "job"):
        result[table] = _table_rows(conn, table, "origin_host=?", (origin,))
    return result


def _project_row(conn, project):
    row = conn.execute("SELECT * FROM project WHERE slug=?", (project,)).fetchone()
    return dict(row) if row is not None else None


def pull_payload(conn, project, from_home):
    data = registry.load()
    if data is None:
        raise SyncError("registry_invalid", "registry is not configured")
    role = registry.project_role(project, data)
    if not role["configured"]:
        raise SyncError("registry_invalid", "project is not registered: %s" % project)
    if role["is_home"]:
        raise SyncError("not_satellite", "rpc is only available on a satellite")
    if from_home != role["home"]:
        raise SyncError("forbidden_home", "from_home does not match project home")
    tasks, criteria, deps = _pull_task_rows(conn, role["self"])
    return {
        "v": 1,
        "op": "pull",
        "project": project,
        "from_home": from_home,
        "tasks": tasks,
        "criteria": criteria,
        "task_deps": deps,
        "attempts": _owned_rows(conn, role["self"])["attempt"],
        "sessions": _owned_rows(conn, role["self"])["session"],
        "journal": _table_rows(
            conn, "journal",
            "origin_host=? OR (origin_host IS NULL AND (status!='open' OR superseded_by IS NOT NULL))",
            (role["self"],)),
        "evidence": _owned_rows(conn, role["self"])["evidence"],
        "jobs": _owned_rows(conn, role["self"])["job"],
        "last_sync_at": store_mod.get_meta(conn, "last_sync_at"),
    }


def _insert_project(conn, project_row, project):
    if not isinstance(project_row, dict):
        raise SyncError("validation_failed", "push requires project_row")
    slug = project_row.get("slug") or project
    if slug != project:
        raise SyncError("validation_failed", "project row slug mismatch")
    existing = conn.execute("SELECT * FROM project WHERE slug=?", (project,)).fetchone()
    if existing is not None:
        return
    pid = project_row.get("project_id")
    disclosure = project_row.get("disclosure", "internal")
    created = project_row.get("created_at") or now_iso()
    if not isinstance(pid, str) or not pid:
        pid = project + "-" + role_for(project)["self"]
    if disclosure not in ("public", "internal", "restricted"):
        raise SyncError("validation_failed", "invalid project disclosure")
    try:
        conn.execute("INSERT INTO project(project_id,slug,disclosure,created_at) VALUES(?,?,?,?)",
                     (pid, project, disclosure, created))
    except Exception as exc:
        raise SyncError("project_exists", "could not create project: %s" % exc)


def _incoming_tasks(request):
    tasks = request.get("tasks")
    if not _valid_rows(tasks):
        raise SyncError("validation_failed", "push tasks must be a list of objects")
    return tasks


def _task_should_replace(existing, incoming):
    old_epoch = _task_int(existing, "delegation_epoch")
    new_epoch = _task_int(incoming, "delegation_epoch")
    if new_epoch < old_epoch:
        return False
    if new_epoch > old_epoch:
        return True
    if incoming.get("revoke_pending") or incoming.get("revoke_force"):
        return True
    old_updated = str(existing.get("updated_at") or "")
    new_updated = str(incoming.get("updated_at") or "")
    if new_updated and old_updated and new_updated < old_updated:
        return False
    if incoming.get("authority_host") != existing.get("authority_host"):
        return True
    if incoming.get("revoke_pending") or incoming.get("revoke_force"):
        return True
    return True


def _end_revoked_attempt(conn, task, stamp):
    attempt_id = task.get("owner_attempt")
    if attempt_id:
        conn.execute("UPDATE attempt SET ended_at=?, end='superseded' WHERE attempt_id=?",
                     (stamp, attempt_id))
    conn.execute("UPDATE task SET owner_attempt=NULL, lifecycle='open', lease_expires_at=NULL, "
                 "version=version+1, updated_at=? WHERE task_id=?", (stamp, task["task_id"]))


def _apply_push_tasks(conn, request, role, project):
    incoming_tasks = _incoming_tasks(request)
    incoming_by_id = {}
    for row in incoming_tasks:
        if not _valid_task_row(row):
            raise SyncError("validation_failed", "invalid task row")
        task_id = row["task_id"]
        if task_id in incoming_by_id:
            raise SyncError("validation_failed", "duplicate task id")
        incoming_by_id[task_id] = row
    criteria = request.get("criteria", [])
    deps = request.get("task_deps", request.get("deps", []))
    if not _valid_rows(criteria) or not _valid_rows(deps):
        raise SyncError("validation_failed", "invalid task relations")
    criteria_by_id = {}
    deps_by_id = {}
    for row in criteria:
        criteria_by_id.setdefault(row.get("task_id"), []).append(row)
    for row in deps:
        deps_by_id.setdefault(row.get("task_id"), []).append(row)
    returned_value = request.get("returned")
    if not isinstance(returned_value, list) or any(not isinstance(item, str) for item in returned_value):
        raise SyncError("validation_failed", "returned must be a list of task ids")
    returned = set(returned_value)
    relinquished = []
    blocked = []
    accepted = []
    stamp = now_iso()
    for incoming in incoming_tasks:
        task_id = incoming["task_id"]
        existing = _select_task(conn, task_id=task_id, ref=incoming.get("ref"))
        if existing is not None and existing.get("ref") != incoming.get("ref"):
            raise SyncError("validation_failed", "task identity mismatch")
        if existing is None:
            _insert_task(conn, incoming)
            existing = dict(incoming)
            accepted.append(task_id)
        elif (existing.get("authority_host") == role["self"] and
              not (_task_int(incoming, "delegation_epoch") > _task_int(existing, "delegation_epoch")
                   and incoming.get("authority_host") != role["self"])):
            # This machine owns the task: the home's copy may predate local
            # claims or progress, so only its revoke request is taken.
            if incoming.get("revoke_pending"):
                conn.execute("UPDATE task SET revoke_pending=1, revoke_force=? WHERE task_id=?",
                             (1 if incoming.get("revoke_force") else 0, task_id))
            continue
        elif _task_should_replace(existing, incoming):
            merged = dict(incoming)
            merged["synced_at"] = incoming.get("synced_at") or stamp
            _update_task(conn, merged)
            existing = merged
            accepted.append(task_id)
        _update_related_task_copy(conn, task_id, criteria_by_id.get(task_id, []),
                                  deps_by_id.get(task_id, []))
    for task_id in returned:
        task = _select_task(conn, task_id=task_id)
        if task is None:
            continue
        if task.get("authority_host") == role["self"]:
            conn.execute("UPDATE task SET authority_host=NULL, revoke_pending=0, revoke_force=0, "
                         "version=version+1, updated_at=? WHERE task_id=?", (stamp, task_id))
            relinquished.append(task_id)
    for task in _table_rows(conn, "task", "revoke_pending=1"):
        if task.get("authority_host") != role["self"]:
            continue
        task_id = task.get("task_id")
        if not task_id:
            continue
        if task.get("owner_attempt"):
            if _task_int(task, "revoke_force"):
                _end_revoked_attempt(conn, task, stamp)
                conn.execute("UPDATE task SET authority_host=NULL, revoke_pending=0, "
                             "revoke_force=0, version=version+1, "
                             "updated_at=? WHERE task_id=?", (stamp, task_id))
                relinquished.append(task_id)
            else:
                blocked.append(task_id)
        else:
            conn.execute("UPDATE task SET authority_host=NULL, revoke_pending=0, "
                         "revoke_force=0, version=version+1, "
                         "updated_at=? WHERE task_id=?", (stamp, task_id))
            relinquished.append(task_id)
    for table, columns, primary in (
            ("attempt", ATTEMPT_COLUMNS, ("attempt_id",)),
            ("session", SESSION_COLUMNS, ("runtime", "session_id")),
            ("journal", JOURNAL_COLUMNS, ("entry_id",)),
            ("evidence", EVIDENCE_COLUMNS, ("evidence_id",)),
            ("job", JOB_COLUMNS, ("cluster", "job_id"))):
        rows = request.get("jobs" if table == "job" else table + "s", [])
        if table == "journal":
            rows = request.get("journal", [])
        if table == "evidence":
            rows = request.get("evidence", [])
        if not _valid_rows(rows):
            raise SyncError("validation_failed", "invalid %s rows" % table)
        for row in rows:
            if row.get("origin_host") is not None:
                continue
            if table in ("attempt", "journal", "evidence", "job"):
                task_id = row.get("task_id")
                if task_id and _select_task(conn, task_id=task_id) is None:
                    continue
            _upsert_owned(conn, table, columns, row, primary, None)
    store_mod.set_meta(conn, "last_sync_at", stamp)
    store_mod.set_meta(conn, meta_key(role["home"], "last_sync_ok_at"), stamp)
    return {"v": 1, "op": "push", "project": project,
            "from_home": role["home"], "tasks": accepted,
            "relinquished": sorted(set(relinquished)),
            "blocked": sorted(set(blocked)), "last_sync_at": stamp}


def push_payload(conn, project, role, returned):
    project_row = _project_row(conn, project)
    if project_row is None:
        raise SyncError("project_not_found", "home project store is missing")
    payload = {
        "v": 1,
        "op": "push",
        "project": project,
        "from_home": role["self"],
        "project_row": project_row,
        "tasks": _table_rows(conn, "task"),
        "criteria": _table_rows(conn, "criterion"),
        "task_deps": _table_rows(conn, "task_dep"),
        "grants": _table_rows(conn, "grant_"),
        "attempts": _table_rows(conn, "attempt", "origin_host IS NULL"),
        "sessions": _table_rows(conn, "session", "origin_host IS NULL"),
        "journal": _table_rows(conn, "journal", "origin_host IS NULL"),
        "evidence": _table_rows(conn, "evidence", "origin_host IS NULL"),
        "jobs": _table_rows(conn, "job", "origin_host IS NULL"),
        "returned": list(returned or []),
    }
    return payload


def apply_pull(conn, project, satellite, response):
    if not isinstance(response, dict):
        raise SyncError("protocol_error", "pull response is not an object")
    if response.get("v") != 1 or response.get("op") != "pull":
        raise SyncError("protocol_error", "invalid pull response envelope")
    tasks = response.get("tasks", [])
    criteria = response.get("criteria", [])
    deps = response.get("task_deps", response.get("deps", []))
    if not _valid_rows(tasks) or not _valid_rows(criteria) or not _valid_rows(deps):
        raise SyncError("protocol_error", "pull response rows are invalid")
    criteria_by_id = {}
    deps_by_id = {}
    for row in criteria:
        criteria_by_id.setdefault(row.get("task_id"), []).append(row)
    for row in deps:
        deps_by_id.setdefault(row.get("task_id"), []).append(row)
    owned = {}
    for key in ("attempts", "sessions", "journal", "evidence", "jobs"):
        rows = response.get(key, [])
        if not _valid_rows(rows):
            raise SyncError("protocol_error", "invalid %s rows" % key)
        owned[key] = rows
    accepted = []
    auto_returned = []
    stamp = response.get("last_sync_at") or now_iso()
    for incoming in tasks:
        if not _valid_task_row(incoming):
            raise SyncError("protocol_error", "invalid task row")
        if incoming.get("origin_host") not in (None, satellite) and incoming.get("authority_host") != satellite:
            continue
        existing = _select_task(conn, task_id=incoming.get("task_id"), ref=incoming.get("ref"))
        if existing is None:
            if incoming.get("origin_host") != satellite:
                continue
            merged = dict(incoming)
            if merged.get("lifecycle") in ("verified", "cancelled"):
                merged["authority_host"] = None
                merged["revoke_pending"] = 0
                merged["revoke_force"] = 0
                merged["delegation_epoch"] = _task_int(incoming, "delegation_epoch") + 1
                auto_returned.append(incoming["task_id"])
            _insert_task(conn, merged)
            existing = merged
            accepted.append(incoming["task_id"])
        else:
            eligible = (existing.get("authority_host") == satellite or
                        existing.get("origin_host") == satellite or
                        incoming.get("origin_host") == satellite)
            if not eligible:
                continue
            incoming_epoch = _task_int(incoming, "delegation_epoch")
            existing_epoch = _task_int(existing, "delegation_epoch")
            if incoming_epoch < existing_epoch:
                continue
            if (existing.get("authority_host") == satellite and
                    incoming.get("authority_host") is None and
                    incoming.get("lifecycle") not in ("verified", "cancelled") and
                    incoming_epoch <= existing_epoch and
                    str(incoming.get("updated_at") or "") <= str(existing.get("updated_at") or "")):
                continue
            if (existing.get("authority_host") != satellite and
                    not _task_should_replace(existing, incoming)):
                continue
            merged = dict(incoming)
            if existing.get("authority_host") == satellite:
                merged["revoke_pending"] = int(existing.get("revoke_pending") or incoming.get("revoke_pending") or 0)
                merged["revoke_force"] = int(existing.get("revoke_force") or incoming.get("revoke_force") or 0)
                merged["version"] = max(int(existing.get("version") or 0),
                                        int(incoming.get("version") or 0))
                if str(existing.get("updated_at") or "") > str(merged.get("updated_at") or ""):
                    merged["updated_at"] = existing.get("updated_at")
            should_return = (existing.get("authority_host") == satellite and
                             (incoming.get("lifecycle") in ("verified", "cancelled") or
                              (incoming.get("authority_host") is None and
                               (incoming_epoch > _task_int(existing, "delegation_epoch") or
                                str(incoming.get("updated_at") or "") > str(existing.get("updated_at") or "")))))
            if should_return:
                merged["authority_host"] = None
                merged["revoke_pending"] = 0
                merged["revoke_force"] = 0
                merged["delegation_epoch"] = max(_task_int(existing, "delegation_epoch"),
                                                  _task_int(incoming, "delegation_epoch")) + 1
                auto_returned.append(incoming["task_id"])
            merged["synced_at"] = stamp
            _update_task(conn, merged)
            accepted.append(incoming["task_id"])
        _update_related_task_copy(conn, incoming["task_id"],
                                  criteria_by_id.get(incoming["task_id"], []),
                                  deps_by_id.get(incoming["task_id"], []))
    owned_count = 0
    for table, columns, primary in (
            ("attempt", ATTEMPT_COLUMNS, ("attempt_id",)),
            ("session", SESSION_COLUMNS, ("runtime", "session_id")),
            ("journal", JOURNAL_COLUMNS, ("entry_id",)),
            ("evidence", EVIDENCE_COLUMNS, ("evidence_id",)),
            ("job", JOB_COLUMNS, ("cluster", "job_id"))):
        key = {"attempt": "attempts", "session": "sessions", "journal": "journal",
               "evidence": "evidence", "job": "jobs"}[table]
        for row in owned[key]:
            if table == "journal":
                if row.get("origin_host") not in (None, satellite):
                    continue
            elif row.get("origin_host") != satellite:
                continue
            if table in ("attempt", "journal", "evidence", "job"):
                task_id = row.get("task_id")
                if task_id and _select_task(conn, task_id=task_id) is None:
                    continue
            if _upsert_owned(conn, table, columns, row, primary, satellite):
                owned_count += 1
    return {"tasks": accepted, "auto_returned": sorted(set(auto_returned)),
            "owned_rows": owned_count}


def apply_push_result(conn, project, satellite, result):
    if not isinstance(result, dict):
        raise SyncError("protocol_error", "push response is not an object")
    if result.get("v") != 1 or result.get("op") != "push":
        raise SyncError("protocol_error", "invalid push response envelope")
    relinquished = result.get("relinquished", [])
    blocked = result.get("blocked", [])
    if not isinstance(relinquished, list) or not isinstance(blocked, list):
        raise SyncError("protocol_error", "push response lists are invalid")
    finalized = []
    stamp = now_iso()
    for task_id in relinquished:
        if not isinstance(task_id, str):
            continue
        task = _select_task(conn, task_id=task_id)
        if task is None or task.get("authority_host") != satellite:
            continue
        conn.execute("UPDATE task SET authority_host=NULL, revoke_pending=0, revoke_force=0, "
                     "delegation_epoch=delegation_epoch+1, version=version+1, updated_at=? "
                     "WHERE task_id=?", (stamp, task_id))
        finalized.append(task_id)
    set_sync_meta(conn, satellite, "last_sync_error", None)
    set_sync_meta(conn, satellite, "last_sync_ok_at", stamp)
    return {"finalized": finalized, "blocked": blocked,
            "last_sync_ok_at": stamp}


def _parse_response(result):
    if result.returncode == 255:
        raise SyncError("unreachable", "satellite SSH returned 255", unreachable=True)
    if result.returncode != 0:
        detail = (result.stderr or "").strip()[:500]
        try:
            failed_payload = json.loads(result.stdout)
        except (TypeError, ValueError):
            failed_payload = None
        if isinstance(failed_payload, dict) and failed_payload.get("ok") is False:
            error = failed_payload.get("error") or {}
            raise SyncError(error.get("code") or "remote_error",
                            error.get("message") or "satellite rejected request")
        raise SyncError("remote_error", "satellite command failed: %s" % (detail or result.returncode))
    try:
        payload = json.loads(result.stdout)
    except (TypeError, ValueError) as exc:
        raise SyncError("remote_protocol_error", "satellite returned invalid JSON: %s" % exc)
    if not isinstance(payload, dict):
        raise SyncError("remote_protocol_error", "satellite response is not an object")
    if payload.get("ok") is False:
        error = payload.get("error") or {}
        raise SyncError(error.get("code") or "remote_error",
                        error.get("message") or "satellite rejected request")
    if payload.get("ok") is not True or not isinstance(payload.get("result"), dict):
        raise SyncError("remote_protocol_error", "satellite response has no result")
    return payload["result"]


def rpc_call(project, satellite, config, request, timeout=60):
    ssh_text = os.environ.get("TASKSTATE_SSH",
                              "ssh -o BatchMode=yes -o ConnectTimeout=5")
    try:
        command = shlex.split(ssh_text)
    except ValueError as exc:
        raise SyncError("validation_failed", "invalid TASKSTATE_SSH: %s" % exc)
    if not command or not isinstance(config, dict):
        raise SyncError("registry_invalid", "satellite host configuration is missing")
    command.extend([str(config.get("ssh") or satellite), str(config.get("python")),
                    str(config.get("taskstate")), "rpc"])
    try:
        result = subprocess.run(command, input=json.dumps(request, sort_keys=True),
                                capture_output=True, text=True, timeout=timeout,
                                check=False)
    except subprocess.TimeoutExpired:
        raise SyncError("unreachable", "satellite SSH timed out", unreachable=True)
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise SyncError("unreachable", "satellite SSH unavailable: %s" % exc, unreachable=True)
    return _parse_response(result)


def _record_sync_error(conn, satellite, message):
    set_sync_meta(conn, satellite, "last_sync_error", message[:1000])


def sync_project(project, role, host_filter=None, actor="taskstate", observed_at=None):
    if not role.get("configured") or not role.get("is_home"):
        if role.get("configured"):
            raise SyncError("home_only", "sync runs on the project home only")
        return {"project": project, "hosts": [], "synced": 0}
    try:
        data = registry.load()
    except registry.RegistryError as exc:
        raise SyncError("registry_invalid", str(exc))
    satellites = list(role.get("satellites") or [])
    if host_filter:
        if host_filter not in satellites:
            raise SyncError("validation_failed", "unknown satellite: %s" % host_filter)
        satellites = [host_filter]
    results = []
    for satellite in satellites:
        config = data["hosts"].get(satellite) if data else None
        if config is None:
            results.append({"host": satellite, "status": "error",
                            "code": "registry_invalid", "error": "satellite is not configured"})
            continue
        conn, path = store_mod.open_project_db(project)
        try:
            pull_request = {"v": 1, "op": "pull", "project": project,
                            "from_home": role["self"]}
            try:
                pulled = rpc_call(project, satellite, config, pull_request, timeout=30)
                if (pulled.get("project") != project or
                        pulled.get("from_home") != role["self"]):
                    raise SyncError("protocol_error", "pull response identity mismatch")
                # The pull is committed before the push so the home's write lock
                # is never held across a network round trip. This is safe:
                # auto-returned tasks are verified (unclaimable on either side),
                # and delegation/revocation finalize only after the satellite
                # confirms in the push response.
                conn.execute("BEGIN IMMEDIATE;")
                try:
                    pull_result = apply_pull(conn, project, satellite, pulled)
                    conn.execute("COMMIT;")
                except BaseException:
                    conn.execute("ROLLBACK;")
                    raise
                push_request = push_payload(conn, project, role,
                                            pull_result.get("auto_returned", []))
                pushed = rpc_call(project, satellite, config, push_request, timeout=30)
                if (pushed.get("project") != project or
                        pushed.get("from_home") != role["self"]):
                    raise SyncError("protocol_error", "push response identity mismatch")
                conn.execute("BEGIN IMMEDIATE;")
                try:
                    push_result = apply_push_result(conn, project, satellite, pushed)
                    conn.execute("COMMIT;")
                except BaseException:
                    conn.execute("ROLLBACK;")
                    raise
                results.append({"host": satellite, "status": "ok", "pull": pull_result,
                                "push": push_result})
            except SyncError as exc:
                try:
                    conn.execute("BEGIN IMMEDIATE;")
                    _record_sync_error(conn, satellite, exc.message)
                    conn.execute("COMMIT;")
                except Exception:
                    try:
                        conn.execute("ROLLBACK;")
                    except Exception:
                        pass
                results.append({"host": satellite, "status": "error", "code": exc.code,
                                "error": exc.message, "unreachable": exc.unreachable})
        finally:
            conn.close()
    return {"project": project, "hosts": results,
            "synced": sum(1 for item in results if item.get("status") == "ok")}


def _rpc_push(conn, project, request, role):
    if request.get("from_home") != role["home"]:
        raise SyncError("forbidden_home", "from_home does not match project home")
    if role["is_home"]:
        raise SyncError("not_satellite", "rpc is only available on a satellite")
    if request.get("v") != 1 or request.get("op") != "push":
        raise SyncError("validation_failed", "invalid push request")
    for key in ("tasks", "criteria", "task_deps", "grants", "attempts", "sessions",
                "journal", "evidence", "jobs", "returned"):
        if key not in request:
            raise SyncError("validation_failed", "push missing %s" % key)
    conn.execute("BEGIN IMMEDIATE;")
    try:
        _insert_project(conn, request.get("project_row"), project)
        result = _apply_push_tasks(conn, request, role, project)
        for row in request.get("grants", []):
            if not isinstance(row, dict) or not row.get("grant_id"):
                raise SyncError("validation_failed", "invalid grant row")
            if conn.execute("SELECT 1 FROM grant_ WHERE grant_id=?", (row["grant_id"],)).fetchone() is None:
                conn.execute("INSERT INTO grant_(grant_id,kind,scope_json,granted_by,source,"
                             "recorded_via,created_at) VALUES(?,?,?,?,?,?,?)",
                             (row.get("grant_id"), row.get("kind"), row.get("scope_json", "{}"),
                              row.get("granted_by", "home"), row.get("source", "sync"),
                              row.get("recorded_via", "sync"), row.get("created_at") or now_iso()))
        conn.execute("COMMIT;")
        return result
    except BaseException:
        try:
            conn.execute("ROLLBACK;")
        except Exception:
            pass
        raise


def rpc_dispatch(request, root=None):
    try:
        data = registry.load()
        if data is None:
            raise SyncError("registry_invalid", "registry is not configured")
        if not isinstance(request, dict) or request.get("v") != 1:
            raise SyncError("validation_failed", "rpc requires JSON object with v=1")
        op = request.get("op")
        if op not in ("pull", "push", "ping"):
            raise SyncError("validation_failed", "unsupported rpc operation")
        common = {"v", "op", "project", "from_home"}
        allowed = set(common)
        if op == "push":
            allowed.update({"project_row", "tasks", "criteria", "task_deps", "deps",
                            "grants", "attempts", "sessions", "journal", "evidence",
                            "jobs", "returned", "payload"})
        unknown = set(request) - allowed
        if unknown:
            raise SyncError("validation_failed", "unknown rpc fields: %s" %
                            ",".join(sorted(unknown)))
        if op == "push" and isinstance(request.get("payload"), dict):
            nested = dict(request["payload"])
            nested.update({key: request[key] for key in ("v", "op", "project", "from_home")
                           if key in request})
            request = nested
        project = request.get("project")
        if not isinstance(project, str):
            raise SyncError("validation_failed", "rpc project is required")
        config = data["projects"].get(project)
        if config is None:
            raise SyncError("registry_invalid", "project is not registered")
        if request.get("from_home") != config["home"]:
            raise SyncError("forbidden_home", "from_home does not match project home")
        role = registry.project_role(project, data)
        if role["is_home"]:
            raise SyncError("not_satellite", "rpc is only available on a satellite")
        if op == "ping":
            return {"v": 1, "op": "ping", "project": project, "self": role["self"]}
        if root is None:
            root = store_mod.state_root()
        if op == "pull":
            conn, _ = store_mod.open_project_db(project, root=root, create=True)
            try:
                return pull_payload(conn, project, request["from_home"])
            finally:
                conn.close()
        conn, _ = store_mod.open_project_db(project, root=root, create=True)
        try:
            return _rpc_push(conn, project, request, role)
        finally:
            conn.close()
    except SyncError as exc:
        raise
    except registry.RegistryError as exc:
        raise SyncError("registry_invalid", str(exc))
    except store_mod.StoreError as exc:
        raise SyncError(exc.code, exc.message)
    except Exception as exc:
        raise SyncError("rpc_error", str(exc))


def attention_items(conn, project):
    role = role_for(project)
    label = freshness(project, conn).get("label")
    items = []
    for row in _table_rows(conn, "task"):
        authority = row.get("authority_host")
        if authority:
            detail = "delegated to authority host %s" % authority
            if _configured(role) and not role.get("is_home"):
                detail += "; " + label
            items.append({"type": "delegated_task", "project": project,
                          "ref": row["ref"], "since": row.get("updated_at"),
                          "detail": detail, "authority_host": authority})
        if row.get("revoke_pending") and row.get("owner_attempt"):
            items.append({"type": "revoke_blocked", "project": project,
                          "ref": row["ref"], "since": row.get("updated_at"),
                          "detail": "revoke is blocked by the current satellite claim; authority host %s" %
                                    (authority or "unknown"),
                          "authority_host": authority})
    if _configured(role) and role.get("is_home"):
        threshold = _stale_seconds()
        current = datetime.datetime.now(datetime.timezone.utc)
        data = registry.load()
        for satellite in role.get("satellites", []):
            last = store_mod.get_meta(conn, meta_key(satellite, "last_sync_ok_at"))
            last_dt = parse_time(last)
            if last_dt is None or (current - last_dt).total_seconds() > threshold:
                items.append({"type": "satellite_stale", "project": project,
                              "ref": satellite, "since": last,
                              "detail": "no successful satellite sync in over %d seconds" % threshold,
                              "authority_host": satellite})
    if _configured(role) and not role.get("is_home"):
        for item in items:
            if "detail" in item and label not in item["detail"]:
                item["detail"] = item["detail"] + "; " + label
    return items
