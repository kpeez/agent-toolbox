#!/usr/bin/env python3
# Installed Knap 0.6.0 probes: help exposes syntax/tags plus blockquote/table;
# include is unknown and whitespace-control dashes raise PARSE_ERROR.
# Missing values render empty, output is not auto-escaped, escape_md escapes
# ASCII punctuation, and ?? treats zero/false as missing.
# Oversized probes enforce a 1 MiB template and 5 MiB value/output limit;
# knap validate checks static syntax/filter names, not runtime data presence.
"""Taskstate read-model validation, Knap rendering, and CLI."""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
TEMPLATE_FILES = {
    "context": TEMPLATE_DIR / "context.md",
    "handoff": TEMPLATE_DIR / "handoff.md",
    "task": TEMPLATE_DIR / "task.md",
    "attention": TEMPLATE_DIR / "attention.md",
}
CONTRACT_VERSION = 1
TEXT_CAP = 2000
MAX_KNAP_BYTES = 5_000_000
LIST_CAPS = {
    "decisions": 10,
    "failed_approaches": 20,
    "open_questions_blockers": 20,
    "items": 200,
}
VIEWS = tuple(TEMPLATE_FILES)
LIFECYCLES = ("proposed", "open", "active", "verified", "accepted", "cancelled", "superseded")
HEALTH = ("running", "stalled", "orphaned", "idle")
TASK_KINDS = ("code", "research", "operation")
JOURNAL_KINDS = ("decision", "finding", "failed_approach", "blocker", "question", "progress", "handoff", "note")
JOURNAL_STATUSES = ("open", "resolved", "superseded")
EVIDENCE_RESULTS = ("pass", "fail", "inconclusive", "unavailable", "missing")
FRESHNESS = ("current", "stale", "unknown")
EVIDENCE_GAPS = ("stale", "missing", "unavailable", "inconclusive", "failing", "unknown")
YES_NO = ("yes", "no")
BOOLEAN_DISPLAY = ("yes", "no", "none")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import facts
import store as store_mod
import taskstate


class RenderError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")


def _single_line(value):
    if value is None:
        text = "none"
    elif isinstance(value, bool):
        text = "yes" if value else "no"
    elif isinstance(value, (int, float)):
        text = str(value)
    else:
        text = str(value)
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")


def _multiline(value):
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).replace("\r\n", "\n").replace("\r", "\n")


def _display(value):
    return _single_line(value)


def _boolean_display(value):
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int) and value in (0, 1):
        return "no" if value == 0 else "yes"
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("yes", "true", "1"):
            return "yes"
        if lowered in ("no", "false", "0"):
            return "no"
        if lowered in ("none", "null", ""):
            return "none"
    return _single_line(value)


def _collection(items):
    return {"items": list(items), "omitted": 0}


def _journal_item(row, actor=None):
    return {
        "entry_id": _single_line(row.get("entry_id")),
        "kind": _single_line(row.get("kind")),
        "body": _multiline(row.get("body")),
        "status": _single_line(row.get("status")),
        "superseded_by": _single_line(row.get("superseded_by")),
        "actor": _single_line(actor if actor is not None else row.get("actor")),
        "recorded_at": _single_line(row.get("recorded_at")),
    }


def _empty_handoff():
    return {
        "recorded": "no",
        "entry_id": "none",
        "kind": "handoff",
        "body": "none",
        "actor": "none",
        "recorded_at": "none",
        "next_action": "none",
        "summary": "none",
        "risks": [],
        "do_not_repeat": [],
        "facts": {
            "head": "none",
            "branch": "none",
            "worktree": "none",
            "dirty": "no",
            "diff_hash": "none",
            "diffstat": "none",
        },
    }


def _handoff_item(row):
    if not row:
        return _empty_handoff()
    data = row.get("data")
    if not isinstance(data, dict):
        data = {}
    facts = data.get("facts")
    if not isinstance(facts, dict):
        facts = {}
    return {
        "recorded": "yes",
        "entry_id": _single_line(row.get("entry_id")),
        "kind": "handoff",
        "body": _multiline(row.get("body")),
        "actor": _single_line(row.get("actor")),
        "recorded_at": _single_line(row.get("recorded_at")),
        "next_action": _multiline(data.get("next_action") or row.get("body")),
        "summary": _multiline(data.get("summary")),
        "risks": [_multiline(value) for value in (data.get("risks") or [])],
        "do_not_repeat": [_multiline(value) for value in (data.get("do_not_repeat") or [])],
        "facts": {
            "head": _single_line(facts.get("head")),
            "branch": _single_line(facts.get("branch")),
            "worktree": _single_line(facts.get("worktree")),
            "dirty": _boolean_display(facts.get("dirty")),
            "diff_hash": _single_line(facts.get("diff_hash")),
            "diffstat": _multiline(facts.get("diffstat")),
        },
    }


def _reported_progress(value, handoff=None):
    if not value:
        return {
            "recorded": "no",
            "entry_id": "none",
            "kind": "none",
            "body": "none",
            "actor": "none",
            "recorded_at": "none",
            "label": "agent-reported",
        }
    actor = "unavailable from Phase 1 read model"
    if handoff and handoff.get("recorded") == "yes" and handoff.get("entry_id") == value.get("entry_id"):
        actor = handoff.get("actor")
    return {
        "recorded": "yes",
        "entry_id": _single_line(value.get("entry_id")),
        "kind": _single_line(value.get("kind")),
        "body": _multiline(value.get("body")),
        "actor": _single_line(actor),
        "recorded_at": _single_line(value.get("recorded_at")),
        "label": "agent-reported",
    }


def _authorization(value):
    value = value or {}
    return {
        "execute": _boolean_display(value.get("execute")),
        "publish": _boolean_display(value.get("publish")),
        "via": [_single_line(item) for item in (value.get("via") or [])],
    }


def _sync_model(value):
    value = value if isinstance(value, dict) else {}
    return {
        "label": _single_line(value.get("label") or "local"),
        "last_sync_at": _single_line(value.get("last_sync_at")),
        "home_copy": _boolean_display(value.get("home_copy")),
    }


def _task_model(task, include_hold_reason=False):
    result = {
        "ref": _single_line(task.get("ref")),
        "title": _single_line(task.get("title")),
        "kind": _single_line(task.get("kind")),
        "lifecycle": _single_line(task.get("lifecycle")),
        "hold": _boolean_display(task.get("hold")),
        "spec_id": _single_line(task.get("spec_id")),
        "authority_host": _single_line(task.get("authority_host") or "local/home"),
        "delegation_epoch": _single_line(task.get("delegation_epoch") or 0),
        "revoke_pending": _boolean_display(task.get("revoke_pending")),
        "sync": _sync_model(task.get("sync")),
    }
    if include_hold_reason:
        result["hold_reason"] = _single_line(task.get("hold_reason"))
    return result


def _derived_model(derived, handoff=None):
    return {
        "ready": _boolean_display((derived or {}).get("ready")),
        "health": _single_line((derived or {}).get("health")),
        "authorization": _authorization((derived or {}).get("authorization")),
        "reported_progress": _reported_progress((derived or {}).get("reported_progress"), handoff),
    }


def _context_evidence(criterion):
    evidence = criterion.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}
    return {
        "evidence_id": _single_line(evidence.get("evidence_id")),
        "result": _single_line(evidence.get("result") or "missing"),
        "kind": _single_line(evidence.get("kind")),
        "freshness": _single_line(evidence.get("freshness") or "unknown"),
        "summary": _multiline(evidence.get("summary")),
        "command": _multiline(evidence.get("command")),
        "recorded_at": _single_line(evidence.get("recorded_at")),
    }


def _criterion_model(criterion):
    return {
        "ac_id": _single_line(criterion.get("ac_id")),
        "text": _multiline(criterion.get("text")),
        "evidence": _context_evidence(criterion),
    }


def _deps_model(items):
    return [
        {
            "ref": _single_line(item.get("ref")),
            "lifecycle": _single_line(item.get("lifecycle")),
        }
        for item in (items or [])
    ]


def _split_evidence(criteria):
    verified = []
    gaps = []
    for criterion in criteria:
        evidence = criterion["evidence"]
        if evidence["result"] == "pass" and evidence["freshness"] == "current":
            verified.append(dict(criterion))
            continue
        if evidence["result"] == "missing":
            gap = "missing"
        elif evidence["result"] == "unavailable":
            gap = "unavailable"
        elif evidence["result"] == "inconclusive":
            gap = "inconclusive"
        elif evidence["result"] != "pass":
            gap = "failing"
        elif evidence["freshness"] == "stale":
            gap = "stale"
        else:
            gap = "unknown"
        item = dict(criterion)
        item["gap"] = gap
        gaps.append(item)
    return verified, gaps


def _task_evidence(criteria, evidence_rows):
    by_id = {row.get("ac_id"): row for row in (evidence_rows or [])}
    result = []
    for criterion in criteria or []:
        evidence = by_id.get(criterion.get("ac_id")) or {}
        result.append({
            "ac_id": _single_line(criterion.get("ac_id")),
            "text": _multiline(criterion.get("text")),
            "evidence": {
                "evidence_id": _single_line(evidence.get("evidence_id")),
                "result": _single_line(evidence.get("status") or "missing"),
                "kind": "none",
                "freshness": _single_line(evidence.get("freshness") or "unknown"),
                "summary": "none",
                "command": "none",
                "recorded_at": "none",
            },
        })
    return result


def _header(view, project, db_seq, missing):
    return {
        "contract_version": CONTRACT_VERSION,
        "view": view,
        "generated_at": _now_iso(),
        "source": {"project": _single_line(project), "db_seq": int(db_seq)},
        "missing": list(missing),
        "truncated": [],
    }


def _task_with_sync(raw):
    value = dict(raw.get("task") or {})
    if raw.get("sync") is not None:
        value["sync"] = raw["sync"]
    return value


def _context_read_model(conn, project, task, db_seq):
    raw = taskstate.build_context(conn, project, task, facts.collect())
    handoff = _handoff_item((raw.get("latest_handoff") or [None])[0])
    criteria = [_criterion_model(item) for item in (raw.get("criteria") or [])]
    missing = []
    if not criteria:
        missing.append("criteria")
    elif any(item["evidence"]["result"] == "missing" for item in criteria):
        missing.append("evidence")
    if handoff["recorded"] == "no":
        missing.append("handoff")
    model = _header("context", project, db_seq, missing)
    model.update({
        "task": _task_model(_task_with_sync(raw) or task),
        "derived": _derived_model(raw.get("derived"), handoff),
        "criteria": criteria,
        "decisions": _collection(_journal_item(item) for item in (raw.get("decisions", {}).get("items") or [])),
        "failed_approaches": _collection(_journal_item(item) for item in (raw.get("failed_approaches", {}).get("items") or [])),
        "open_questions_blockers": _collection(_journal_item(item) for item in (raw.get("open_questions_blockers", {}).get("items") or [])),
        "latest_handoff": handoff,
        "deps": _deps_model(raw.get("deps")),
    })
    for name, value in (raw.get("decisions") or {}).items():
        if name == "omitted":
            model["decisions"]["omitted"] = int(value or 0)
    for name, value in (raw.get("failed_approaches") or {}).items():
        if name == "omitted":
            model["failed_approaches"]["omitted"] = int(value or 0)
    for name, value in (raw.get("open_questions_blockers") or {}).items():
        if name == "omitted":
            model["open_questions_blockers"]["omitted"] = int(value or 0)
    return model


def _handoff_read_model(conn, project, task, db_seq):
    raw = taskstate.build_context(conn, project, task, facts.collect())
    handoff = _handoff_item((raw.get("latest_handoff") or [None])[0])
    criteria = [_criterion_model(item) for item in (raw.get("criteria") or [])]
    verified, gaps = _split_evidence(criteria)
    missing = ["handoff"] if handoff["recorded"] == "no" else []
    if not criteria:
        missing.append("criteria")
    elif any(item["evidence"]["result"] == "missing" for item in criteria):
        missing.append("evidence")
    model = _header("handoff", project, db_seq, missing)
    model.update({
        "task": _task_model(_task_with_sync(raw) or task),
        "derived": _derived_model(raw.get("derived"), handoff),
        "handoff": handoff,
        "criteria": criteria,
        "verified_current": verified,
        "evidence_gaps": gaps,
        "decisions": _collection(_journal_item(item) for item in (raw.get("decisions", {}).get("items") or [])),
        "failed_approaches": _collection(_journal_item(item) for item in (raw.get("failed_approaches", {}).get("items") or [])),
        "open_questions_blockers": _collection(_journal_item(item) for item in (raw.get("open_questions_blockers", {}).get("items") or [])),
    })
    for name, value in (raw.get("decisions") or {}).items():
        if name == "omitted":
            model["decisions"]["omitted"] = int(value or 0)
    for name, value in (raw.get("failed_approaches") or {}).items():
        if name == "omitted":
            model["failed_approaches"]["omitted"] = int(value or 0)
    for name, value in (raw.get("open_questions_blockers") or {}).items():
        if name == "omitted":
            model["open_questions_blockers"]["omitted"] = int(value or 0)
    return model


def _task_read_model(conn, project, task, db_seq):
    raw = taskstate.task_view(conn, task, facts.collect(), project)
    task_data = _task_model(_task_with_sync(raw) or task, include_hold_reason=True)
    criteria = _task_evidence(raw.get("criteria"), (raw.get("derived") or {}).get("evidence"))
    missing = []
    if not criteria:
        missing.append("criteria")
    elif any(item["evidence"]["result"] == "missing" for item in criteria):
        missing.append("evidence")
    if not (raw.get("derived") or {}).get("reported_progress"):
        missing.append("reported_progress")
    model = _header("task", project, db_seq, missing)
    model.update({
        "task": task_data,
        "lifecycle": {
            "state": task_data["lifecycle"],
            "ready": _boolean_display((raw.get("derived") or {}).get("ready")),
            "hold": task_data["hold"],
            "hold_reason": task_data["hold_reason"],
        },
        "execution_health": {"state": _single_line((raw.get("derived") or {}).get("health"))},
        "authorization": _authorization((raw.get("derived") or {}).get("authorization")),
        "reported_progress": _reported_progress((raw.get("derived") or {}).get("reported_progress")),
        "verified_evidence": criteria,
    })
    return model


def _attention_item(item):
    return {
        "type": _single_line(item.get("type")),
        "project": _single_line(item.get("project")),
        "ref": _single_line(item.get("ref")),
        "since": _single_line(item.get("since")),
        "detail": _multiline(item.get("detail")),
    }


def _attention_all(db_seq):
    root = store_mod.state_root()
    items = []
    max_seq = 0
    missing = []
    sync_values = []
    databases = sorted(root.glob("*.db"))
    if not databases:
        missing.append("projects")
    for database in databases:
        slug = database.stem
        conn = None
        try:
            conn, _ = store_mod.open_project_db(slug, create=False)
            seq = store_mod.db_seq(conn)
            max_seq = max(max_seq, seq)
            sync_values.append(taskstate._sync_info(slug, conn))
            items.extend(_attention_item(item) for item in taskstate.attention_for_conn(conn, slug))
        except Exception as exc:
            items.append(_attention_item({
                "type": "store_error",
                "project": slug,
                "ref": "none",
                "since": None,
                "detail": exc,
            }))
        finally:
            if conn is not None:
                conn.close()
    if not items:
        missing.append("attention_items")
    model = _header("attention", "all", max(max_seq, db_seq), missing)
    model["items"] = _collection(items)
    selected_sync = next((value for value in sync_values if value.get("home_copy")),
                         {"label": "local", "last_sync_at": None, "home_copy": False})
    model["sync"] = _sync_model(selected_sync)
    return model


def _attention_read_model(project, db_seq, all_projects=False):
    if all_projects:
        return _attention_all(db_seq)
    conn = None
    sync_raw = None
    try:
        conn, _ = store_mod.open_project_db(project, create=False)
        seq = store_mod.db_seq(conn)
        raw_items = taskstate.attention_for_conn(conn, project)
        sync_raw = taskstate._sync_info(project, conn)
    finally:
        if conn is not None:
            conn.close()
    missing = ["attention_items"] if not raw_items else []
    model = _header("attention", project, max(seq, db_seq), missing)
    model["items"] = _collection(_attention_item(item) for item in raw_items)
    model["sync"] = _sync_model(sync_raw)
    return model


def build_read_model(view, project=None, ref=None, all_projects=False):
    if view not in VIEWS:
        raise RenderError("contract_invalid", "Unknown read-model view: %s" % view)
    if view == "attention" and all_projects:
        return _attention_all(0)
    if not project:
        raise RenderError("contract_invalid", "A project is required for the %s view" % view)
    if view != "attention" and not ref:
        raise RenderError("contract_invalid", "A task REF is required for the %s view" % view)
    if view == "attention":
        return _attention_read_model(project, 0)
    conn = None
    try:
        conn, _ = store_mod.open_project_db(project, create=False)
        task = taskstate.fetch_task(conn, ref)
        db_seq = store_mod.db_seq(conn)
        if view == "context":
            return _context_read_model(conn, project, task, db_seq)
        if view == "handoff":
            return _handoff_read_model(conn, project, task, db_seq)
        return _task_read_model(conn, project, task, db_seq)
    finally:
        if conn is not None:
            conn.close()


build_model = build_read_model


def _kind_matches(value, kind):
    if kind == "object":
        return isinstance(value, dict)
    if kind == "array":
        return isinstance(value, list)
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return type(value) is int
    return False


def _check_object(value, path, schema, exact=True):
    if not isinstance(value, dict):
        raise RenderError("contract_invalid", "%s must be an object" % path)
    expected = set(schema)
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected) if exact else []
    if missing or extra:
        details = []
        if missing:
            details.append("missing %s" % ", ".join(missing))
        if extra:
            details.append("unexpected %s" % ", ".join(extra))
        raise RenderError("contract_invalid", "%s keys invalid: %s" % (path, "; ".join(details)))
    for key, (kind, choices) in schema.items():
        item = value[key]
        item_path = "%s.%s" % (path, key)
        if not _kind_matches(item, kind):
            raise RenderError("contract_invalid", "%s must be %s" % (item_path, kind))
        if choices is not None and item not in choices:
            raise RenderError("contract_invalid", "%s has invalid enum value %r" % (item_path, item))


def _check_array(value, path):
    if not isinstance(value, list):
        raise RenderError("contract_invalid", "%s must be an array" % path)


def _check_string_list(value, path):
    if not isinstance(value, list):
        raise RenderError("contract_invalid", "%s must be an array" % path)
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise RenderError("contract_invalid", "%s[%d] must be a string" % (path, index))


def _check_nonnegative(value, path):
    if type(value) is not int or value < 0:
        raise RenderError("contract_invalid", "%s must be a nonnegative integer" % path)


def _authorization_schema():
    return {
        "execute": ("string", YES_NO),
        "publish": ("string", YES_NO),
        "via": ("array", None),
    }


def _sync_schema():
    return {
        "label": ("string", None),
        "last_sync_at": ("string", None),
        "home_copy": ("string", YES_NO),
    }


def _task_schema(include_hold_reason=False):
    schema = {
        "ref": ("string", None),
        "title": ("string", None),
        "kind": ("string", TASK_KINDS),
        "lifecycle": ("string", LIFECYCLES),
        "hold": ("string", YES_NO),
        "spec_id": ("string", None),
        "authority_host": ("string", None),
        "delegation_epoch": ("string", None),
        "revoke_pending": ("string", YES_NO),
        "sync": ("object", None),
    }
    if include_hold_reason:
        schema["hold_reason"] = ("string", None)
    return schema


def _journal_schema(kind=None):
    schema = {
        "entry_id": ("string", None),
        "kind": ("string", kind if isinstance(kind, tuple) else ((kind,) if kind else JOURNAL_KINDS)),
        "body": ("string", None),
        "status": ("string", JOURNAL_STATUSES),
        "superseded_by": ("string", None),
        "actor": ("string", None),
        "recorded_at": ("string", None),
    }
    return schema


def _collection_schema():
    return {"items": ("array", None), "omitted": ("integer", None)}


def _evidence_schema():
    return {
        "evidence_id": ("string", None),
        "result": ("string", EVIDENCE_RESULTS),
        "kind": ("string", None),
        "freshness": ("string", FRESHNESS),
        "summary": ("string", None),
        "command": ("string", None),
        "recorded_at": ("string", None),
    }


def _criterion_schema():
    return {
        "ac_id": ("string", None),
        "text": ("string", None),
        "evidence": ("object", None),
    }


def _handoff_schema():
    return {
        "recorded": ("string", YES_NO),
        "entry_id": ("string", None),
        "kind": ("string", ("handoff",)),
        "body": ("string", None),
        "actor": ("string", None),
        "recorded_at": ("string", None),
        "next_action": ("string", None),
        "summary": ("string", None),
        "risks": ("array", None),
        "do_not_repeat": ("array", None),
        "facts": ("object", None),
    }


def _reported_schema():
    return {
        "recorded": ("string", YES_NO),
        "entry_id": ("string", None),
        "kind": ("string", ("progress", "handoff", "none")),
        "body": ("string", None),
        "actor": ("string", None),
        "recorded_at": ("string", None),
        "label": ("string", ("agent-reported",)),
    }


def _derived_schema():
    return {
        "ready": ("string", YES_NO),
        "health": ("string", HEALTH),
        "authorization": ("object", None),
        "reported_progress": ("object", None),
    }


def _check_authorization(value, path):
    _check_object(value, path, _authorization_schema())
    _check_string_list(value["via"], path + ".via")


def _check_journal(value, path, kind=None):
    _check_object(value, path, _journal_schema(kind))
    if not value["entry_id"] or not value["body"] or not value["actor"] or not value["recorded_at"]:
        raise RenderError("contract_invalid", "%s must include entry_id, body, actor, and recorded_at" % path)


def _check_collection(value, path):
    _check_object(value, path, _collection_schema())
    _check_nonnegative(value["omitted"], path + ".omitted")


def _check_journal_collection(value, path, kind=None):
    _check_collection(value, path)
    for index, item in enumerate(value["items"]):
        _check_journal(item, "%s.items[%d]" % (path, index), kind)


def _check_evidence(value, path):
    _check_object(value, path, _evidence_schema())


def _check_criterion(value, path):
    _check_object(value, path, _criterion_schema())
    if not value["ac_id"] or not value["text"]:
        raise RenderError("contract_invalid", "%s must include ac_id and text" % path)
    _check_evidence(value["evidence"], path + ".evidence")


def _check_handoff(value, path):
    _check_object(value, path, _handoff_schema())
    if value["recorded"] == "yes" and (not value["entry_id"] or not value["body"] or not value["actor"] or not value["recorded_at"]):
        raise RenderError("contract_invalid", "%s must include entry_id, body, actor, and recorded_at" % path)
    _check_string_list(value["risks"], path + ".risks")
    _check_string_list(value["do_not_repeat"], path + ".do_not_repeat")
    _check_object(value["facts"], path + ".facts", {
        "head": ("string", None),
        "branch": ("string", None),
        "worktree": ("string", None),
        "dirty": ("string", BOOLEAN_DISPLAY),
        "diff_hash": ("string", None),
        "diffstat": ("string", None),
    })


def _check_reported(value, path):
    _check_object(value, path, _reported_schema())
    if value["recorded"] == "yes" and (not value["entry_id"] or not value["body"] or not value["actor"] or not value["recorded_at"]):
        raise RenderError("contract_invalid", "%s must include entry_id, body, actor, and recorded_at" % path)


def _check_derived(value, path):
    _check_object(value, path, _derived_schema())
    _check_authorization(value["authorization"], path + ".authorization")
    _check_reported(value["reported_progress"], path + ".reported_progress")


def _view_keys():
    return {
        "context": {"task", "derived", "criteria", "decisions", "failed_approaches", "open_questions_blockers", "latest_handoff", "deps"},
        "handoff": {"task", "derived", "handoff", "criteria", "verified_current", "evidence_gaps", "decisions", "failed_approaches", "open_questions_blockers"},
        "task": {"task", "lifecycle", "execution_health", "authorization", "reported_progress", "verified_evidence"},
        "attention": {"items", "sync"},
    }


def _check_context(model):
    _check_object(model["task"], "task", _task_schema())
    _check_object(model["task"]["sync"], "task.sync", _sync_schema())
    _check_derived(model["derived"], "derived")
    _check_string_list(model["derived"]["authorization"]["via"], "derived.authorization.via")
    _check_array(model["criteria"], "criteria")
    _check_array(model["deps"], "deps")
    for index, item in enumerate(model["criteria"]):
        _check_criterion(item, "criteria[%d]" % index)
    _check_journal_collection(model["decisions"], "decisions", "decision")
    _check_journal_collection(model["failed_approaches"], "failed_approaches", "failed_approach")
    _check_journal_collection(model["open_questions_blockers"], "open_questions_blockers", ("question", "blocker"))
    _check_handoff(model["latest_handoff"], "latest_handoff")
    for index, item in enumerate(model["deps"]):
        _check_object(item, "deps[%d]" % index, {
            "ref": ("string", None),
            "lifecycle": ("string", LIFECYCLES),
        })


def _check_handoff_view(model):
    _check_object(model["task"], "task", _task_schema())
    _check_object(model["task"]["sync"], "task.sync", _sync_schema())
    _check_derived(model["derived"], "derived")
    _check_authorization(model["derived"]["authorization"], "derived.authorization")
    _check_handoff(model["handoff"], "handoff")
    for name in ("criteria", "verified_current", "evidence_gaps"):
        _check_array(model[name], name)
    for name in ("criteria", "verified_current"):
        for index, item in enumerate(model[name]):
            _check_criterion(item, "%s[%d]" % (name, index))
    for index, item in enumerate(model["evidence_gaps"]):
        _check_object(item, "evidence_gaps[%d]" % index, dict(_criterion_schema(), gap=("string", EVIDENCE_GAPS)))
        _check_evidence(item["evidence"], "evidence_gaps[%d].evidence" % index)
        if not item["ac_id"] or not item["text"]:
            raise RenderError("contract_invalid", "evidence_gaps[%d] must include ac_id and text" % index)
    for name, kind in (("decisions", "decision"),
                       ("failed_approaches", "failed_approach"),
                       ("open_questions_blockers", ("question", "blocker"))):
        _check_journal_collection(model[name], name, kind)


def _check_task(model):
    _check_object(model["task"], "task", _task_schema(include_hold_reason=True))
    _check_object(model["task"]["sync"], "task.sync", _sync_schema())
    _check_array(model["verified_evidence"], "verified_evidence")
    _check_object(model["lifecycle"], "lifecycle", {
        "state": ("string", LIFECYCLES),
        "ready": ("string", YES_NO),
        "hold": ("string", YES_NO),
        "hold_reason": ("string", None),
    })
    _check_object(model["execution_health"], "execution_health", {
        "state": ("string", HEALTH),
    })
    _check_authorization(model["authorization"], "authorization")
    _check_reported(model["reported_progress"], "reported_progress")
    for index, item in enumerate(model["verified_evidence"]):
        _check_criterion(item, "verified_evidence[%d]" % index)


def _check_attention(model):
    _check_collection(model["items"], "items")
    _check_object(model["sync"], "sync", _sync_schema())
    for index, item in enumerate(model["items"]["items"]):
        _check_object(item, "items.items[%d]" % index, {
            "type": ("string", None),
            "project": ("string", None),
            "ref": ("string", None),
            "since": ("string", None),
            "detail": ("string", None),
        })


def _truncate_text(value, path, truncated):
    if len(value) <= TEXT_CAP:
        return value
    marker_prefix = "…[truncated "
    marker_start = value.rfind(marker_prefix)
    original_length = len(value)
    if marker_start >= 0 and value.endswith(" chars]"):
        digits = value[marker_start + len(marker_prefix):-len(" chars]")]
        if digits.isdigit():
            original_length = marker_start + int(digits)
    count = original_length
    marker = "…[truncated %d chars]" % count
    keep = TEXT_CAP - len(marker)
    if keep < 0:
        raise RenderError("contract_invalid", "%s is too large to truncate safely" % path)
    result = value[:keep] + marker
    truncated.append(path)
    return result


def _walk_strings(value, path, truncated):
    if isinstance(value, str):
        return _truncate_text(value, path, truncated)
    if isinstance(value, list):
        return [_walk_strings(item, "%s[%d]" % (path, index), truncated) for index, item in enumerate(value)]
    if isinstance(value, dict):
        return {
            key: _walk_strings(item, "%s.%s" % (path, key), truncated)
            for key, item in value.items()
        }
    return value


def _cap_collections(model):
    for name, cap in LIST_CAPS.items():
        if name not in model:
            continue
        collection = model[name]
        omitted = collection["omitted"]
        if len(collection["items"]) > cap:
            omitted += len(collection["items"]) - cap
            collection["items"] = collection["items"][:cap]
        collection["omitted"] = omitted


def validate(view, model):
    if view not in VIEWS:
        raise RenderError("contract_invalid", "Unknown read-model view: %s" % view)
    if not isinstance(model, dict):
        raise RenderError("contract_invalid", "Read model must be an object")
    common = {
        "contract_version": ("integer", (CONTRACT_VERSION,)),
        "view": ("string", (view,)),
        "generated_at": ("string", None),
        "source": ("object", None),
        "missing": ("array", None),
        "truncated": ("array", None),
    }
    _check_object(model, "model", common, exact=False)
    _check_object(model["source"], "source", {
        "project": ("string", None),
        "db_seq": ("integer", None),
    })
    _check_nonnegative(model["source"]["db_seq"], "source.db_seq")
    _check_string_list(model["missing"], "missing")
    _check_string_list(model["truncated"], "truncated")
    if set(model) != set(common) | _view_keys()[view]:
        expected = set(common) | _view_keys()[view]
        raise RenderError("contract_invalid", "model keys invalid for view %s" % view)
    if view == "context":
        _check_context(model)
    elif view == "handoff":
        _check_handoff_view(model)
    elif view == "task":
        _check_task(model)
    else:
        _check_attention(model)
    _cap_collections(model)
    original_truncated = list(model["truncated"])
    walked = _walk_strings(model, "model", original_truncated)
    model.clear()
    model.update(walked)
    model["truncated"] = list(dict.fromkeys(original_truncated))
    try:
        encoded = json.dumps(model, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise RenderError("contract_invalid", "Read model is not JSON serializable: %s" % exc)
    if len(encoded) >= MAX_KNAP_BYTES:
        raise RenderError("contract_invalid", "Validated read model exceeds Knap's 5 MiB input limit")
    return model


def _knap_binary():
    binary = shutil.which("knap")
    if not binary:
        raise RenderError("knap_missing", "Knap is required for Markdown rendering; use --json to print the validated read model without Node")
    return binary


def _run_knap_version(binary):
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise RenderError("knap_version_unsupported", "Knap version check exceeded 10 seconds")
    except (OSError, subprocess.SubprocessError) as exc:
        raise RenderError("knap_missing", "Knap is unavailable; use --json to print the validated read model without Node (%s)" % exc)
    version = result.stdout.decode("utf-8", errors="replace").strip()
    if result.returncode != 0 or not version.startswith("0.6."):
        detail = result.stderr.decode("utf-8", errors="replace").strip() or version or "unknown version"
        raise RenderError("knap_version_unsupported", "Knap 0.6.x is required; found %s" % detail)


def _invoke_knap(binary, template, payload):
    try:
        result = subprocess.run(
            [binary, "render", str(template), "--data", "-"],
            input=payload,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise RenderError("knap_render_timeout", "Knap rendering exceeded 10 seconds")
    except (OSError, subprocess.SubprocessError) as exc:
        raise RenderError("knap_render_failed", "Knap rendering failed: %s" % exc)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip() or "Knap exited with status %d" % result.returncode
        raise RenderError("knap_render_failed", detail)
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RenderError("knap_render_failed", "Knap returned invalid UTF-8: %s" % exc)


def render_model(view, model, binary=None):
    if view not in VIEWS:
        raise RenderError("contract_invalid", "Unknown read-model view: %s" % view)
    binary = binary or _knap_binary()
    _run_knap_version(binary)
    payload = json.dumps(model, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return _invoke_knap(binary, TEMPLATE_FILES[view], payload)


def render_read_model(view, model):
    validated = validate(view, model)
    return render_model(view, validated)


def _is_agent_docs(path):
    parts = path.parts
    return any(parts[index] == ".agents" and index + 1 < len(parts) and parts[index + 1] == "docs"
               for index in range(len(parts)))


def _atomic_write(path, text):
    # Check the path as given too: .agents/docs is usually a symlink into the
    # vault, so the resolved path alone would not reveal it.
    given = Path(os.path.abspath(os.path.expanduser(path)))
    destination = given.resolve()
    if _is_agent_docs(given) or _is_agent_docs(destination):
        raise RenderError("output_forbidden", "Rendered output must not be written into .agents/docs")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".%s." % destination.name, dir=str(destination.parent))
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
    except OSError as exc:
        raise RenderError("output_write_failed", "Could not write %s: %s" % (destination, exc))


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise RenderError("validation_failed", message)


def _parser():
    parser = _Parser(prog="render.py", description="Build and render taskstate read models")
    parser.add_argument("view", choices=VIEWS)
    parser.add_argument("ref", nargs="?")
    parser.add_argument("--project")
    parser.add_argument("--all", action="store_true", dest="all_projects")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--out")
    return parser


def _error_output(code, message):
    return json.dumps({"ok": False, "error": {"code": code, "message": message}}, ensure_ascii=False) + "\n"


def main(argv=None):
    try:
        args = _parser().parse_args(argv)
        if args.view == "attention":
            if args.all_projects and args.project:
                raise RenderError("validation_failed", "attention accepts --project or --all, not both")
            if not args.all_projects and not args.project:
                raise RenderError("validation_failed", "attention needs --project or --all")
            if args.ref:
                raise RenderError("validation_failed", "attention does not accept a task REF")
        else:
            if args.all_projects:
                raise RenderError("validation_failed", "--all is only valid for attention")
            if not args.project:
                raise RenderError("validation_failed", "%s needs --project" % args.view)
            if not args.ref:
                raise RenderError("validation_failed", "%s needs a task REF" % args.view)
        model = build_read_model(args.view, project=args.project, ref=args.ref, all_projects=args.all_projects)
        model = validate(args.view, model)
        if args.as_json:
            output = json.dumps(model, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        else:
            output = render_model(args.view, model)
        if args.out:
            _atomic_write(args.out, output)
            return 0, ""
        return 0, output
    except Exception as exc:
        code = getattr(exc, "code", "internal_error")
        message = getattr(exc, "message", str(exc))
        return 2, _error_output(code, message)


if __name__ == "__main__":
    exit_code, output_text = main()
    sys.stdout.write(output_text)
    sys.exit(exit_code)
