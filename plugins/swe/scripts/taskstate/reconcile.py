"""Read-only Slurm observation and durable reconciliation for taskstate."""
from __future__ import annotations

import datetime
import os
import re
import shutil
import subprocess
import uuid

import domain
import taskstate as taskstate_mod
from taskstate import TaskStateError, caller_match, do_mutation, fetch_task, read_cache
from taskstate import lease_seconds, now_iso, update_attempt_facts

CLUSTER_RE = re.compile(r"^[A-Za-z0-9._-]+$")
JOB_ID_RE = re.compile(r"^[0-9]+(_[0-9]+)?(\[[0-9,-]+\])?$")
NONTERMINAL_STATES = {
    "PENDING", "RUNNING", "CONFIGURING", "COMPLETING", "SUSPENDED"
}
FAILED_STATES = {
    "FAILED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL", "PREEMPTED",
    "BOOT_FAIL", "DEADLINE"
}
SLURM_COMMANDS = {"squeue", "sacct"}


def _add_common(parser, include_task=True):
    parser.add_argument("--project", default=None)
    if include_task:
        parser.add_argument("--task", default=None)
    parser.add_argument("--attempt", default=None)
    parser.add_argument("--epoch", default=None, type=int)
    parser.add_argument("--actor", default=None)
    parser.add_argument("--observed-at", default=None)
    parser.add_argument("--request-id", default=None)
    parser.add_argument("--json", action="store_true")


def add_subparsers(sub):
    job = sub.add_parser("job")
    jobs = job.add_subparsers(dest="sub", required=True)

    add = jobs.add_parser("add")
    add.add_argument("--cluster", required=True)
    add.add_argument("--id", required=True, dest="job_id")
    _add_common(add)

    ack = jobs.add_parser("ack")
    ack.add_argument("--cluster", required=True)
    ack.add_argument("--id", required=True, dest="job_id")
    _add_common(ack, include_task=False)

    reconcile = sub.add_parser("reconcile")
    reconcile.add_argument("--no-slurm", action="store_true")
    _add_common(reconcile, include_task=False)
    return sub


def _job_values(args):
    cluster = getattr(args, "cluster", None)
    job_id = getattr(args, "job_id", None)
    if job_id is None:
        job_id = getattr(args, "id", None)
    if not isinstance(cluster, str) or not CLUSTER_RE.match(cluster):
        raise TaskStateError("validation_failed", "Invalid Slurm cluster: %r" % (cluster,))
    if not isinstance(job_id, str) or not JOB_ID_RE.match(job_id):
        raise TaskStateError("validation_failed", "Invalid Slurm job id: %r" % (job_id,))
    return cluster, job_id


def _request_id(args):
    value = getattr(args, "request_id", None)
    if not value:
        value = str(uuid.uuid4())
        setattr(args, "request_id", value)
    return value


def _observed_at(value):
    if not value:
        return now_iso()
    try:
        parsed = domain.parse_time(value)
    except (TypeError, ValueError, OverflowError):
        raise TaskStateError("validation_failed", "Invalid observed_at: %r" % (value,))
    if parsed is None:
        return now_iso()
    return parsed.astimezone(datetime.timezone.utc).isoformat(timespec="microseconds")


def _attempt_and_task(conn, ref, attempt_id):
    attempt = None
    if attempt_id is not None:
        row = conn.execute("SELECT * FROM attempt WHERE attempt_id=?", (attempt_id,)).fetchone()
        if row is None:
            raise TaskStateError("attempt_not_found", "Unknown attempt: %s" % attempt_id)
        attempt = dict(row)
    if ref:
        task = fetch_task(conn, ref)
    elif attempt is not None:
        row = conn.execute("SELECT * FROM task WHERE task_id=?", (attempt["task_id"],)).fetchone()
        if row is None:
            raise TaskStateError("task_not_found", "Unknown task for attempt: %s" % attempt_id)
        task = dict(row)
    else:
        raise TaskStateError(
            "validation_failed", "job add needs --task when no attempt is supplied")
    if attempt is not None and attempt["task_id"] != task["task_id"]:
        raise TaskStateError(
            "validation_failed", "Attempt does not belong to task %s" % task["ref"])
    return task, attempt


def _job_owner_context(slug, args):
    ref = getattr(args, "task", None) or None
    attempt_id = getattr(args, "attempt", None) or None
    epoch = getattr(args, "epoch", None)
    cache = read_cache()
    if cache.get("project") == slug and cache.get("ref"):
        if ref is None:
            ref = cache["ref"]
        if ref == cache["ref"]:
            if attempt_id is None:
                attempt_id = cache.get("attempt_id")
            if epoch is None:
                epoch = cache.get("epoch")
    return ref, attempt_id, epoch


def _job_add(conn, slug, args, actor, observed_at, fact, host):
    cluster, job_id = _job_values(args)
    ref, attempt_id, epoch = _job_owner_context(slug, args)
    if ref:
        task = fetch_task(conn, ref)
        role = taskstate_mod.authority_context(slug)
        authoritative = taskstate_mod.is_authoritative(task, role.get("self"),
                                                       role.get("is_home", True))
        if not authoritative:
            attempt_id = None
            epoch = None
            _attempt = None
        else:
            task, _attempt = _attempt_and_task(conn, ref, attempt_id)
    else:
        task, _attempt = _attempt_and_task(conn, ref, attempt_id)
        role = taskstate_mod.authority_context(slug)
        authoritative = taskstate_mod.is_authoritative(task, role.get("self"),
                                                       role.get("is_home", True))
        if not authoritative:
            attempt_id = None
            epoch = None
    request_id = _request_id(args)
    payload = {
        "command": "job.add", "project": slug, "cluster": cluster, "job_id": job_id,
        "ref": task["ref"], "attempt": attempt_id, "epoch": epoch
    }

    def effect():
        current_task, attempt = _attempt_and_task(conn, ref, attempt_id)
        late = 0
        if attempt_id is not None:
            if caller_match(current_task, attempt_id, epoch):
                update_attempt_facts(conn, attempt_id, fact if isinstance(fact, dict) else {}, observed_at)
            else:
                late = 1
        existing = conn.execute(
            "SELECT * FROM job WHERE cluster=? AND job_id=?", (cluster, job_id)).fetchone()
        result = {
            "cluster": cluster, "job_id": job_id, "ref": current_task["ref"],
            "task_id": current_task["task_id"], "attempt_id": attempt_id, "late": late
        }
        if existing is not None:
            if existing["task_id"] != current_task["task_id"] or existing["attempt_id"] != attempt_id:
                raise TaskStateError(
                    "job_exists", "Slurm job already exists: %s/%s" % (cluster, job_id),
                    details=[{"task_id": existing["task_id"], "attempt_id": existing["attempt_id"]}])
            result["last_state"] = existing["last_state"]
            result["acknowledged"] = existing["acknowledged"]
            return result
        recorded_at = now_iso()
        conn.execute(
            "INSERT INTO job(cluster, job_id, task_id, attempt_id, submitted_by, host, last_state, "
            "last_state_at, exit_code, acknowledged, observed_at, recorded_at, request_id, origin_host) "
            "VALUES(?,?,?,?,?,?,NULL,NULL,NULL,0,?,?,?,?)",
            (cluster, job_id, current_task["task_id"], attempt_id, actor, host,
             observed_at, recorded_at, request_id, taskstate_mod._origin_host(slug)))
        result["last_state"] = None
        result["acknowledged"] = 0
        return result

    return do_mutation(conn, "job.add", request_id, payload, actor,
                       task["task_id"], effect)


def _job_ack(conn, slug, args, actor, observed_at, fact, host):
    cluster, job_id = _job_values(args)
    request_id = _request_id(args)
    payload = {"command": "job.ack", "project": slug,
               "cluster": cluster, "job_id": job_id}

    def effect():
        row = conn.execute(
            "SELECT j.*, t.ref AS ref FROM job j JOIN task t ON t.task_id=j.task_id "
            "WHERE j.cluster=? AND j.job_id=?", (cluster, job_id)).fetchone()
        if row is None:
            raise TaskStateError(
                "job_not_found", "Unknown Slurm job: %s/%s" % (cluster, job_id))
        conn.execute(
            "UPDATE job SET acknowledged=1 WHERE cluster=? AND job_id=?",
            (cluster, job_id))
        return {"cluster": cluster, "job_id": job_id, "ref": row["ref"],
                "acknowledged": 1}

    return do_mutation(conn, "job.ack", request_id, payload, actor, None, effect)


def _state_category(state):
    if state is None:
        return None
    normalized = str(state).strip().upper()
    if normalized == "UNOBSERVABLE":
        return "unobservable"
    if normalized == "MISSING":
        return "missing"
    if normalized in NONTERMINAL_STATES:
        return "nonterminal"
    if normalized == "COMPLETED":
        return "finished"
    if normalized in FAILED_STATES or normalized.startswith("CANCELLED"):
        return "failed"
    return None


def _ssh_alias(cluster):
    suffix = re.sub(r"[^A-Za-z0-9]", "_", cluster.upper())
    value = os.environ.get("TASKSTATE_SLURM_SSH_" + suffix)
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith("-"):
        raise TaskStateError("validation_failed", "Invalid Slurm SSH alias")
    return value


def _run_slurm(command, cluster):
    if not command or os.path.basename(command[0]) not in SLURM_COMMANDS:
        raise AssertionError("reconcile may invoke only squeue or sacct")
    alias = _ssh_alias(cluster)
    if alias is not None:
        invocation = [
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", alias
        ] + list(command)
    else:
        if shutil.which(command[0]) is None:
            return None
        invocation = list(command)
    try:
        result = subprocess.run(
            invocation, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError, TimeoutError, UnicodeError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _first_line(output):
    for line in (output or "").splitlines():
        if line.strip():
            return line.strip()
    return None


def _unobservable():
    return {"state": "unobservable", "exit_code": None, "category": "unobservable"}


def _observe_job(cluster, job_id):
    queue_output = _run_slurm(["squeue", "-h", "-j", job_id, "-o", "%T"], cluster)
    # squeue exits non-zero ("Invalid job id specified") once a job has left
    # the queue, so a failed squeue falls through to sacct; only a failed
    # sacct as well makes the job unobservable.
    queue_state = _first_line(queue_output) if queue_output is not None else None
    if queue_state is not None:
        category = _state_category(queue_state)
        if category is None:
            return _unobservable()
        return {"state": queue_state, "exit_code": None, "category": category}
    accounting_output = _run_slurm(
        ["sacct", "-n", "-X", "-P", "-j", job_id, "-o", "State,ExitCode"], cluster)
    if accounting_output is None:
        return _unobservable()
    accounting_state = _first_line(accounting_output)
    if accounting_state is None:
        return {"state": "missing", "exit_code": None, "category": "missing"}
    parts = accounting_state.split("|", 1)
    state = parts[0].strip()
    exit_code = parts[1].strip() if len(parts) == 2 and parts[1].strip() else None
    category = _state_category(state)
    if category is None:
        return _unobservable()
    return {"state": state, "exit_code": exit_code, "category": category}


def _is_terminal(state):
    return _state_category(state) in {"finished", "failed", "missing"}


def _not_older_observation(new_value, old_value):
    if not old_value:
        return True
    try:
        return domain.parse_time(new_value) >= domain.parse_time(old_value)
    except (TypeError, ValueError, OverflowError):
        return True


def _stalled_tasks(conn, now):
    stalled = []
    rows = conn.execute(
        "SELECT task_id, ref, owner_attempt, lease_expires_at FROM task "
        "WHERE lifecycle='active' AND owner_attempt IS NOT NULL "
        "AND lease_expires_at IS NOT NULL ORDER BY ref").fetchall()
    for row in rows:
        try:
            lease = domain.parse_time(row["lease_expires_at"])
        except (TypeError, ValueError, OverflowError):
            lease = None
        if lease is not None and lease <= now:
            stalled.append({
                "ref": row["ref"], "task_id": row["task_id"],
                "owner_attempt": row["owner_attempt"],
                "lease_expires_at": row["lease_expires_at"]
            })
    return stalled


def _reconcile(conn, slug, args, observed_at):
    stamp = _observed_at(observed_at)
    now = domain.parse_time(stamp)
    observations = []
    unobservable = []
    jobs_checked = 0
    if not getattr(args, "no_slurm", False):
        rows = conn.execute(
            "SELECT * FROM job WHERE acknowledged=0 ORDER BY cluster, job_id").fetchall()
        for row in rows:
            if _is_terminal(row["last_state"]):
                continue
            jobs_checked += 1
            observation = _observe_job(row["cluster"], row["job_id"])
            observations.append((row, observation))
            if observation["category"] == "unobservable":
                unobservable.append({
                    "cluster": row["cluster"], "job_id": row["job_id"],
                    "state": observation["state"]
                })
    sessions_orphaned = 0
    job_changes = []
    conn.execute("BEGIN IMMEDIATE;")
    try:
        for row, observation in observations:
            current = conn.execute(
                "SELECT * FROM job WHERE cluster=? AND job_id=?",
                (row["cluster"], row["job_id"])).fetchone()
            if current is None or current["acknowledged"]:
                continue
            if not _not_older_observation(stamp, current["observed_at"]):
                continue
            previous_state = current["last_state"]
            previous_exit = current["exit_code"]
            changed = previous_state != observation["state"] or previous_exit != observation["exit_code"]
            updated = conn.execute(
                "UPDATE job SET last_state=?, last_state_at=?, exit_code=?, observed_at=? "
                "WHERE cluster=? AND job_id=? AND acknowledged=0",
                (observation["state"], stamp, observation["exit_code"], stamp,
                 row["cluster"], row["job_id"]))
            if updated.rowcount == 1 and changed:
                job_changes.append({
                    "cluster": current["cluster"], "job_id": current["job_id"],
                    "previous_state": previous_state, "state": observation["state"],
                    "exit_code": observation["exit_code"],
                    "classification": observation["category"]
                })
        cutoff = now - datetime.timedelta(seconds=lease_seconds())
        stale_sessions = conn.execute(
            "SELECT runtime, session_id, last_seen_at FROM session WHERE end_observed=0 "
            "AND end_inferred=0 AND last_seen_at IS NOT NULL").fetchall()
        for row in stale_sessions:
            try:
                last_seen = domain.parse_time(row["last_seen_at"])
            except (TypeError, ValueError, OverflowError):
                continue
            if last_seen is None or last_seen >= cutoff:
                continue
            updated = conn.execute(
                "UPDATE session SET end_inferred=1 WHERE runtime=? AND session_id=? "
                "AND end_observed=0 AND end_inferred=0",
                (row["runtime"], row["session_id"]))
            sessions_orphaned += updated.rowcount
        conn.execute("COMMIT;")
    except BaseException:
        try:
            conn.execute("ROLLBACK;")
        except Exception:
            pass
        raise
    return {
        "jobs_checked": jobs_checked,
        "job_changes": job_changes,
        "sessions_orphaned": sessions_orphaned,
        "stalled_tasks": _stalled_tasks(conn, now),
        "unobservable": unobservable
    }


def _job_attention_type(state):
    category = _state_category(state)
    return {
        "finished": "job_finished",
        "failed": "job_failed",
        "missing": "job_missing",
        "unobservable": "job_unobservable"
    }.get(category)


def attention_items(conn, slug):
    items = []
    rows = conn.execute(
        "SELECT j.*, t.ref AS ref FROM job j JOIN task t ON t.task_id=j.task_id "
        "WHERE j.acknowledged=0 ORDER BY j.recorded_at, j.cluster, j.job_id").fetchall()
    for row in rows:
        item_type = _job_attention_type(row["last_state"])
        if item_type is None:
            continue
        state = row["last_state"]
        detail = "cluster %s job %s state %s" % (row["cluster"], row["job_id"], state)
        if row["exit_code"] is not None:
            detail += " exit_code %s" % row["exit_code"]
        items.append({
            "type": item_type, "project": slug, "ref": row["ref"],
            "since": row["last_state_at"] or row["observed_at"] or row["recorded_at"],
            "detail": detail
        })
    sessions = conn.execute(
        "SELECT s.*, t.ref AS ref FROM session s JOIN attempt a ON a.attempt_id=s.attempt_id "
        "JOIN task t ON t.task_id=a.task_id AND (s.task_id IS NULL OR s.task_id=t.task_id) "
        "WHERE s.end_inferred=1 AND s.end_observed=0 "
        "AND s.attempt_id=t.owner_attempt ORDER BY s.last_seen_at, s.runtime, s.session_id").fetchall()
    for row in sessions:
        items.append({
            "type": "orphaned_session", "project": slug, "ref": row["ref"],
            "since": row["last_seen_at"],
            "detail": "session %s:%s ended without a handoff; attempt %s still owns the task" % (
                row["runtime"], row["session_id"], row["attempt_id"])
        })
    return items


def dispatch(conn, slug, args, actor, observed_at, fact, host, human):
    command = getattr(args, "cmd", None)
    subcommand = getattr(args, "sub", None)
    if command == "job" and subcommand == "add":
        return _job_add(conn, slug, args, actor, _observed_at(observed_at), fact, host)
    if command == "job" and subcommand == "ack":
        return _job_ack(conn, slug, args, actor, _observed_at(observed_at), fact, host)
    if command == "reconcile":
        return _reconcile(conn, slug, args, observed_at)
    raise TaskStateError("validation_failed", "Unknown reconciliation command")
