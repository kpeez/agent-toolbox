"""Simplified supervised workflow runtime for a single local pilot.

Mechanical reliability only: packet validation, the semantic approval digest,
external authority coherence checks, a small atomic JSON store, preview and
publication, issue-note recording, read-only rendering and the evidence checks
an independent audit reuses.

No ownership or lifecycle engine, hooks, queues, event bus, quotas, transition
arbitration or signed grants. Authority is external JSON whose coherence scripts
verify; it is bookkeeping, not cryptographic enforcement, and never replaces the
model's own verification of the actual approval and source.
"""

from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlparse

SCHEMA_VERSION = 1
CONTEXT_ROLES = ("spec", "context", "code", "research", "reference", "policy")
STANDING_VALUES = ("current", "authoritative", "superseded", "draft", "unknown")
ACCESS_VALUES = ("local", "remote", "inaccessible", "unchecked")
DISCLOSURE_VALUES = ("public", "private", "internal")
TASK_KINDS = ("code", "research", "operation")
REQUEST_KINDS = ("start", "progress", "handoff", "review", "evidence", "result")
ADAPTER_KINDS = ("project", "document", "issue", "relation", "comment")

# Bookkeeping never participates in the semantic approval digest.
BOOKKEEPING_METADATA = frozenset({
    "run_id", "status", "approved", "approved_revision", "updated", "created",
    "updated_at", "created_at", "generated_at", "source_frontmatter",
    "context_document", "task_mappings", "blocked", "blocked_reason",
    "generated", "mapping", "mappings", "tracker_container", "tracker_document"})
TASK_BOOKKEEPING = frozenset({"native_id", "mapping", "run_id", "status", "updated_at", "created_at"})
OWNED_FIELDS = {
    "project": (("name", "name"), ("description", "description"), ("content", "content")),
    "document": (("title", "title"), ("content", "content"), ("projectId", "project_id")),
    "issue": (("title", "title"), ("description", "description"),
              ("projectId", "project_id"), ("teamId", "team_id")),
    "relation": (("issueId", "issue_id"), ("relatedIssueId", "related_issue_id"), ("type", "relation_type")),
    "comment": (("body", "body"), ("issueId", "issue_id"))}
PERMISSION_CODES = frozenset({"permission_denied", "permission", "forbidden", "unauthorized",
                              "not_authorized", "403", "401", "access_denied"})
TRACKER_URL_RE = re.compile(r"https?://(?:[\w.-]+\.)?(?:linear\.app|linear\.com)/\S+", re.I)
TRACKER_ID_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,7}-\d+\b")
TRACKER_ID_ALLOW = frozenset({"UTF", "SHA", "ISO", "RFC", "UTC", "MD", "HTTP", "HTTPS", "TLS",
                              "AES", "RSA", "EC", "JSON", "API", "CLI", "CPU", "GPU", "SQL", "CSS",
                              "HTML", "XML", "ID"})
SECRET_PATTERNS = (
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\b")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("credential_assignment", re.compile(r"(?i)\b(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+")))
LOCAL_PATH_PATTERNS = (
    re.compile(r"/Users/[A-Za-z0-9_.-]+"), re.compile(r"/home/[A-Za-z0-9_.-]+"),
    re.compile(r"[A-Za-z]:\\\\?Users\\\\?"), re.compile(r"(?<!\w)~/\S+"))


class CoreError(Exception):
    def __init__(self, code, message, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details if details is not None else []

    def to_dict(self):
        return {"code": self.code, "message": self.message, "details": self.details}


EXIT_CODES = {
    "validation_failed": 2, "bad_request": 2, "state_required": 2, "adapter_required": 2,
    "state_invalid": 2, "authorization_invalid": 3, "authorization_unconfigured": 3,
    "activation_required": 3, "approval_missing": 3, "approval_digest_mismatch": 3,
    "privacy_violation": 3, "public_disabled": 3, "permission_denied": 4, "sync_uncertain": 5,
    "human_edit_conflict": 6, "mapping_missing": 6, "mapping_archived": 6, "project_missing": 6,
    "project_archived": 6, "stale_event": 6, "request_conflict": 6, "sync_conflict": 6,
    "capability_missing": 6}


def error_exit_code(code):
    return EXIT_CODES.get(code, 1)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def parse_time(value):
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_hex(text):
    if not isinstance(text, (bytes, bytearray)):
        text = text.encode("utf-8")
    return hashlib.sha256(text).hexdigest()


def is_uuid4(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return parsed.version == 4


def new_uuid4():
    return str(uuid.uuid4())


def cfg(config, *path, default=None):
    node = config
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write_json(path, payload):
    """Write JSON atomically with mode 0600 so a crash never truncates state."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    handle_fd, temp_path = tempfile.mkstemp(prefix=".runtime-", dir=directory)
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
    except BaseException:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def dump_json(path, payload):
    atomic_write_json(path, payload)


def adapter_code(exc):
    code = getattr(exc, "code", None)
    if code is None:
        code = getattr(exc, "status", None)
    return None if code is None else str(code).strip().lower()


def is_permission_code(code):
    return bool(code) and (code.lower() in PERMISSION_CODES or "permission" in code.lower())


# --- semantic digest -------------------------------------------------------

def _strip_keys(mapping, blocked):
    if not isinstance(mapping, dict):
        return mapping
    return {key: value for key, value in mapping.items() if key not in blocked}


def _normalize_ref(ref):
    if not isinstance(ref, dict):
        return ref
    blocked = BOOKKEEPING_METADATA | {"access", "observed_at", "last_verified_at"}
    return {key: value for key, value in ref.items() if key not in blocked}


def _normalize_task(task):
    if not isinstance(task, dict):
        return task
    result = {key: value for key, value in task.items() if key not in TASK_BOOKKEEPING}
    # PR identities and observed commits are delivery bookkeeping. Completion
    # requirements (checks, branch, reviewers) still participate in approval.
    if isinstance(result.get("completion"), dict):
        result["completion"] = dict(result["completion"])
        result["completion"]["required_prs"] = [
            {k: v for k, v in pr.items() if k not in {"number", "head_sha", "url"}}
            for pr in result["completion"].get("required_prs", [])]
    return result


def semantic_digest(packet):
    spec = packet.get("spec") or {}
    payload = {
        "spec": {"spec_id": spec.get("spec_id"), "title": spec.get("title"),
                 "markdown": spec.get("markdown"),
                 "metadata": _strip_keys(spec.get("metadata") or {}, BOOKKEEPING_METADATA)},
        "context": [_normalize_ref(ref) for ref in packet.get("context") or []],
        "project": _strip_keys(packet.get("project") or {}, BOOKKEEPING_METADATA),
        "tasks": [_normalize_task(task) for task in packet.get("tasks") or []]}
    return sha256_hex(canonical_json(payload))


# --- validation ------------------------------------------------------------

def _resolve_local_ref(ref, config, roots_key, root_field, probe):
    root_id, relative = ref.get(root_field), ref.get("path")
    roots = cfg(config, roots_key, default={})
    if not isinstance(root_id, str) or not isinstance(roots, (dict, list)) or not roots or root_id not in roots:
        return [{"code": "root_not_configured", "path": root_field,
                 "message": "Reference needs a registered documentation or code root"}]
    registered = roots[root_id] if isinstance(roots, dict) else root_id
    root = registered.get("path") if isinstance(registered, dict) else registered
    if not isinstance(root, str) or not root or not os.path.isabs(root) or not isinstance(relative, str):
        return [{"code": "missing_root", "path": root_field,
                 "message": "Local root must resolve from external configuration"}]
    full = Path(root, relative).resolve()
    if Path(relative).is_absolute() or not full.is_relative_to(Path(root).resolve()):
        return [{"code": "path_escape", "path": "path", "message": "Reference escapes its registered root"}]
    if not full.is_file() or (probe is not None and not probe(str(full))):
        return [{"code": "path_missing", "path": relative, "message": "Referenced file is inaccessible"}]
    try:
        if full.stat().st_size > 8 * 1024 * 1024:
            raise OSError("reference exceeds bound")
        actual = sha256_hex(full.read_bytes())
    except OSError:
        return [{"code": "path_unreadable", "path": relative, "message": "Referenced file cannot be verified"}]
    expected = ref.get("content_hash") or (str(ref.get("revision", "")).removeprefix("sha256:"))
    if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
        return [{"code": "content_hash_required", "path": relative,
                 "message": "Supply the observed SHA256 alongside the revision or commit"}]
    if expected != actual:
        return [{"code": "content_hash_mismatch", "path": relative,
                 "message": "Reference changed since its recorded observation"}]
    return []


def collect_validation_errors(packet, config=None, *, path_probe=None, url_checker=None):
    config = config or {}
    if not isinstance(config, dict):
        return [{"code": "not_object", "path": "config", "message": "Configuration must be an object"}]
    if not isinstance(packet, dict):
        return [{"code": "not_object", "path": "", "message": "Packet must be an object"}]
    errors = []

    def fail(code, path, message):
        errors.append({"code": code, "path": path, "message": message})

    if packet.get("schema_version") != 1:
        fail("schema_version", "schema_version", "Expected packet interface version 1")
    spec = packet.get("spec") or {}
    if not isinstance(spec, dict):
        return [{"code": "not_object", "path": "spec", "message": "Expected spec object"}]
    if not is_uuid4(spec.get("spec_id")):
        fail("bad_uuid4", "spec.spec_id", "Stable spec_id must be UUID4")
    for field in ("title", "markdown"):
        if not isinstance(spec.get(field), str) or not spec[field].strip():
            fail("missing", "spec." + field, "Nonempty field required")
    if not isinstance(spec.get("metadata", {}), dict):
        fail("bad_type", "spec.metadata", "Metadata must be an object")
    project = packet.get("project") or {}
    for field in ("name", "summary", "closure"):
        if not isinstance(project, dict) or not isinstance(project.get(field), str) or not project[field].strip():
            fail("missing", "project." + field, "Project orientation and closure contract required")
    context = packet.get("context")
    if not isinstance(context, list):
        fail("missing", "context", "An ordered curated context list is required")
        context = []
    ref_ids = set()
    for i, ref in enumerate(context):
        loc = "context[%d]" % i
        if not isinstance(ref, dict):
            fail("not_object", loc, "Reference must be an object")
            continue
        if not isinstance(ref.get("id"), str) or not ref["id"] or ref["id"] in ref_ids:
            fail("duplicate", loc + ".id", "Reference needs a unique stable identity")
            continue
        ref_ids.add(ref["id"])
        for field in ("title", "role", "relevance", "revision", "knowledge_date", "standing", "access", "disclosure"):
            if not isinstance(ref.get(field), str) or not ref[field].strip():
                fail("missing", loc + "." + field, "Reference field required")
        for field, choices in (("role", CONTEXT_ROLES), ("access", ACCESS_VALUES)):
            if ref.get(field) not in choices:
                fail("bad_value", loc + "." + field, "Unknown reference " + field)
        if not isinstance(ref.get("essential"), bool):
            fail("missing", loc + ".essential", "Explicit essential boolean required")
        try:
            datetime.date.fromisoformat(ref.get("knowledge_date", ""))
        except (ValueError, TypeError):
            fail("bad_date", loc, "knowledge_date must be an ISO date")
        if ref.get("standing") not in (*STANDING_VALUES, "advisory", "evidence", "approved_current"):
            fail("bad_value", loc, "Unknown reference standing")
        if ref.get("essential") and ref.get("standing") in ("superseded", "draft", "unknown"):
            fail("essential_not_current", loc, "Essential governing context must be current")
        if ref.get("disclosure") not in DISCLOSURE_VALUES:
            fail("bad_value", loc, "Unknown disclosure classification")
        if not ref.get("path") and not ref.get("url"):
            fail("missing", loc, "Reference needs a relative path or usable HTTPS link")
        diagnostics = []
        if ref.get("path"):
            is_code = ref.get("role") == "code"
            diagnostics = _resolve_local_ref(ref, config, "code_roots" if is_code else "documentation_roots",
                                             "code_root" if is_code else "documentation_root", path_probe)
        elif ref.get("url"):
            url = urlparse(ref["url"])
            if url.scheme != "https" or not url.hostname or url.hostname in ("localhost", "127.0.0.1", "::1") or url.username or url.password:
                fail("unsafe_url", loc, "Use an approved authenticated HTTPS route, not localhost or embedded credentials")
            elif url_checker is None:
                diagnostics = [{"code": "url_unchecked", "path": loc,
                                "message": "Essential URL needs an explicit verified access observation"}]
            else:
                try:
                    accessible = url_checker(ref["url"]) is True
                except Exception:
                    accessible = False
                if not accessible:
                    diagnostics = [{"code": "url_inaccessible", "path": loc,
                                    "message": "Referenced URL could not be verified"}]
        # Optional inaccessible sources stay visible in the rendered packet;
        # essential sources and path/configuration errors block dependent work.
        for item in diagnostics:
            if ref.get("essential") or item["code"] in ("path_escape", "root_not_configured", "missing_root"):
                errors.append(item)
        if ref.get("essential") and ref.get("access") in ("unchecked", "inaccessible"):
            fail("essential_inaccessible", loc, "Essential access is not verified")
    tasks = packet.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        fail("missing", "tasks", "Nonempty task list required")
        tasks = []
    ids = {t["task_id"] for t in tasks if isinstance(t, dict) and isinstance(t.get("task_id"), str)}
    seen, native_ids = set(), set()
    for i, task in enumerate(tasks):
        loc = "tasks[%d]" % i
        if not isinstance(task, dict):
            fail("not_object", loc, "Task must be an object")
            continue
        tid = task.get("task_id")
        if not isinstance(tid, str) or not tid or tid in seen:
            fail("duplicate", loc, "Unique stable task identity required")
            continue
        seen.add(tid)
        if not is_uuid4(tid):
            fail("bad_uuid4", loc + ".task_id", "Stable task_id must be UUID4")
        native_id = task.get("native_id")
        if native_id is not None:
            if not isinstance(native_id, str) or not native_id.strip():
                fail("bad_value", loc + ".native_id", "Imported issue identity must be a nonempty string")
            elif native_id in native_ids:
                fail("duplicate_mapping", loc + ".native_id", "Logical tasks cannot share an imported issue")
            else:
                native_ids.add(native_id)
        for field in ("title", "outcome"):
            if not isinstance(task.get(field), str) or not task[field]:
                fail("missing", loc + "." + field, "Nonempty task field required")
        if not isinstance(task.get("acceptance"), list) or not task["acceptance"] or not all(
                isinstance(x, str) and x for x in task["acceptance"]):
            fail("missing", loc + ".acceptance", "Observable acceptance criteria required")
        if task.get("kind") not in TASK_KINDS:
            fail("bad_value", loc + ".kind", "Unsupported work kind")
        if task.get("kind") == "operation" and cfg(task, "completion", "review_gate") not in ("none", "independent", "human"):
            fail("bad_value", loc + ".completion.review_gate",
                 "Operational work must explicitly declare none, independent, or human review")
        refs = task.get("context_ids")
        if not isinstance(refs, list) or any(not isinstance(x, str) or x not in ref_ids for x in refs):
            fail("unknown_context", loc + ".context_ids", "Declare the small task context subset")
        deps = task.get("dependencies", [])
        if not isinstance(deps, list):
            fail("bad_type", loc + ".dependencies", "Expected task identity list")
        else:
            for dep in deps:
                if not isinstance(dep, str):
                    fail("bad_type", loc, "Dependency identity must be a string")
                elif dep == tid:
                    fail("self_dependency", loc, "Task depends on itself")
                elif dep not in ids:
                    fail("unknown_dependency", loc, "Dependency is not in this project")
        if task.get("kind") == "code":
            registry = cfg(config, "repositories", default={})
            repo = registry.get(task.get("repository")) if isinstance(registry, dict) else None
            if not repo:
                fail("unknown_repository", loc, "Code repository must be in explicit registry")
            elif not task.get("base_branch") or task["base_branch"] != repo.get("base_branch"):
                fail("branch_mismatch", loc, "Task integration branch must match repository registry")
            completion = task.get("completion", {})
            prs = completion.get("required_prs") if isinstance(completion, dict) else None
            if not isinstance(prs, list) or not prs:
                fail("missing", loc + ".completion.required_prs",
                     "Declare required PR roles; numbers and head revisions may be attached later")
            else:
                for pr in prs:
                    if not isinstance(pr, dict) or not pr.get("repo") or not isinstance(pr.get("required_checks"), list) or not isinstance(pr.get("required_reviewers"), list):
                        fail("missing", loc + ".completion.required_prs",
                             "Each required PR needs repository, checks and review contract")
                    elif repo and pr["repo"] != repo.get("repo"):
                        fail("repository_mismatch", loc, "Required PR repository must match the code registry")
    if len(ids) == len(tasks) and all(
            isinstance(t, dict) and isinstance(t.get("dependencies", []), list)
            and all(isinstance(d, str) for d in t.get("dependencies", [])) for t in tasks):
        _detect_cycles(tasks, errors)
    return errors


def _detect_cycles(tasks, errors):
    graph = {t["task_id"]: list(t.get("dependencies") or [])
             for t in tasks if isinstance(t, dict) and t.get("task_id")}
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
            errors.append({"code": "dependency_cycle", "path": "tasks", "message": "dependency cycle detected"})
            return


def require_valid(packet, config=None, *, path_probe=None, url_checker=None):
    errors = collect_validation_errors(packet, config, path_probe=path_probe, url_checker=url_checker)
    if errors:
        raise CoreError("validation_failed", "packet failed validation", details=errors)
    return True


# --- public text safety ----------------------------------------------------

def scan_public_text(text, config=None):
    privacy = cfg(config or {}, "privacy", default={}) or {}
    text = text or ""
    findings = []
    for token in privacy.get("deny_private") or []:
        if token and token in text:
            findings.append({"code": "private_denylist", "match": str(token)})
    for match in TRACKER_URL_RE.finditer(text):
        findings.append({"code": "tracker_url", "match": match.group(0)[:120]})
    if privacy.get("deny_tracker_ids", True):
        for match in TRACKER_ID_RE.finditer(text):
            if match.group(0).split("-")[0] not in TRACKER_ID_ALLOW:
                findings.append({"code": "tracker_id", "match": match.group(0)})
    if privacy.get("deny_secrets", True):
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append({"code": "secret", "kind": name})
    if privacy.get("deny_local_paths", True):
        for pattern in LOCAL_PATH_PATTERNS:
            for match in pattern.finditer(text):
                findings.append({"code": "local_path", "match": match.group(0)[:120]})
    if privacy.get("deny_tracker_metadata", True) and re.search(r"(?i)\blinear\.app\b|\bissue\s+[A-Z]{2,7}-\d+\b", text):
        findings.append({"code": "tracker_metadata", "match": "tracker reference"})
    return findings


def assert_public_text_safe(text, config=None):
    findings = scan_public_text(text, config)
    if findings:
        raise CoreError("privacy_violation", "text is not safe for a public destination", details=findings)
    return True


# --- durable state: one small atomic JSON store ----------------------------

class Store:
    """One supervised local JSON store: mappings, intents, receipts, metadata."""

    SECTIONS = ("mappings", "intents", "receipts", "meta")

    def __init__(self, path, readonly=False):
        self.path = path
        self.readonly = readonly or path == ":memory:"
        self.data = {"version": 1, "mappings": {}, "intents": {}, "receipts": [], "meta": {}}
        if path != ":memory:" and os.path.isfile(path):
            loaded = load_json(path)
            if not isinstance(loaded, dict) or loaded.get("version") != 1:
                raise CoreError("state_invalid", "State file is not a version 1 store")
            for key in self.SECTIONS:
                if key in loaded:
                    self.data[key] = loaded[key]
        elif path != ":memory:" and not readonly:
            self._persist()

    def _persist(self):
        if not self.readonly and self.path != ":memory:":
            atomic_write_json(self.path, self.data)

    def close(self):
        self._persist()

    def set_meta(self, key, value):
        self.data["meta"][key] = value
        self._persist()

    def get_meta(self, key, default=None):
        return self.data["meta"].get(key, default)

    def allocate_uuid(self, logical_key, kind):
        mapping = self.data["mappings"].get(logical_key)
        if mapping and mapping.get("native_id"):
            return mapping["native_id"]
        native_id, stamp = new_uuid4(), now_iso()
        self.data["mappings"][logical_key] = {
            "logical_key": logical_key, "kind": kind, "native_id": native_id,
            "status": "allocated", "created_at": stamp, "updated_at": stamp}
        self._persist()
        return native_id

    def get_mapping(self, logical_key):
        mapping = self.data["mappings"].get(logical_key)
        return copy.deepcopy(mapping) if mapping else None

    def list_mappings(self, kind=None):
        values = [m for m in self.data["mappings"].values() if kind is None or m.get("kind") == kind]
        return copy.deepcopy(sorted(values, key=lambda m: m["logical_key"]))

    def put_mapping(self, logical_key, kind, native_id, *, payload_digest=None,
                    readback_hash=None, status="active", meta=None):
        existing = self.data["mappings"].get(logical_key) or {}
        stamp = now_iso()
        self.data["mappings"][logical_key] = {
            "logical_key": logical_key, "kind": kind, "native_id": native_id,
            "payload_digest": payload_digest, "readback_hash": readback_hash, "status": status,
            "meta": meta if meta is not None else existing.get("meta"),
            "created_at": existing.get("created_at", stamp), "updated_at": stamp}
        self._persist()

    def put_receipt(self, logical_key, kind, operation, *, native_id=None,
                    payload_digest=None, readback_hash=None, body=None):
        receipt = {"receipt_id": len(self.data["receipts"]) + 1, "logical_key": logical_key,
                   "kind": kind, "operation": operation, "native_id": native_id,
                   "payload_digest": payload_digest, "readback_hash": readback_hash,
                   "body": body, "created_at": now_iso()}
        self.data["receipts"].append(receipt)
        self._persist()
        return receipt["receipt_id"]

    def latest_receipt(self, logical_key, kind=None):
        for receipt in reversed(self.data["receipts"]):
            if receipt["logical_key"] == logical_key and (kind is None or receipt["kind"] == kind):
                return copy.deepcopy(receipt)
        return None

    def get_intent(self, intent_id):
        intent = self.data["intents"].get(intent_id)
        return copy.deepcopy(intent) if intent else None

    def upsert_intent(self, intent_id, operation, logical_key, kind, payload_digest, state, *,
                      native_id=None, detail=None, attempts_delta=0):
        existing = self.data["intents"].get(intent_id) or {}
        stamp = now_iso()
        self.data["intents"][intent_id] = {
            "intent_id": intent_id, "operation": operation, "logical_key": logical_key, "kind": kind,
            "payload_digest": payload_digest, "state": state,
            "attempts": int(existing.get("attempts", 0)) + max(attempts_delta, 0),
            "native_id": native_id, "detail": detail,
            "created_at": existing.get("created_at", stamp), "updated_at": stamp}
        self._persist()


# --- external authority coherence (not authenticity) -----------------------

APPROVAL_FIELDS = ("spec_id", "digest", "approved_by", "source", "approved_at")
PERMISSION_FIELDS = ("spec_id", "authorized_by", "source")


def verify_approval(authority, packet):
    approval = authority.get("spec_approval") if isinstance(authority, dict) else None
    if not isinstance(approval, dict):
        raise CoreError("approval_missing", "A populated external spec approval is required")
    for field in APPROVAL_FIELDS:
        if not isinstance(approval.get(field), str) or not approval[field].strip():
            raise CoreError("authorization_invalid", "Spec approval is missing " + field)
    if not is_uuid4(approval["spec_id"]):
        raise CoreError("authorization_invalid", "Spec approval spec_id must be UUID4")
    if approval["spec_id"] != (packet.get("spec") or {}).get("spec_id"):
        raise CoreError("authorization_invalid", "Spec approval is for a different spec")
    if approval["digest"] != semantic_digest(packet):
        raise CoreError("approval_digest_mismatch", "Spec approval is bound to different content")
    return approval


def verify_permission(authority, packet, action, *, project_id=None):
    permission = authority.get("permission") if isinstance(authority, dict) else None
    if not isinstance(permission, dict):
        raise CoreError("authorization_invalid", "A populated external permission is required")
    for field in PERMISSION_FIELDS:
        if not isinstance(permission.get(field), str) or not permission[field].strip():
            raise CoreError("authorization_invalid", "Permission is missing " + field)
    actions = permission.get("actions")
    if not isinstance(actions, list) or action not in actions:
        raise CoreError("authorization_invalid", "Permission does not allow " + action)
    if not isinstance(permission.get("create_project"), bool):
        raise CoreError("authorization_invalid", "Permission must declare create_project as a boolean")
    if permission["spec_id"] != (packet.get("spec") or {}).get("spec_id"):
        raise CoreError("authorization_invalid", "Permission is for a different spec")
    scoped = permission.get("project_id")
    if scoped is None and not permission["create_project"]:
        raise CoreError("authorization_invalid", "Permission needs an existing project id or explicit creation")
    if project_id is not None and scoped is not None and scoped != project_id:
        raise CoreError("authorization_invalid", "Permission project scope does not match the target project")
    return permission


def authority_report(authority, packet):
    report = {"approval": "absent", "permission": "absent"}
    if isinstance(authority, dict) and isinstance(authority.get("spec_approval"), dict):
        try:
            verify_approval(authority, packet)
            report["approval"] = "coherent"
        except CoreError as exc:
            report["approval"] = exc.code
    if isinstance(authority, dict) and isinstance(authority.get("permission"), dict):
        try:
            verify_permission(authority, packet, "publish")
            report["permission"] = "coherent"
        except CoreError as exc:
            report["permission"] = exc.code
    return report


# --- owned payload hashing -------------------------------------------------

def owned_projection(kind, obj, *, payload=False):
    result = {}
    for payload_key, remote_key in OWNED_FIELDS[kind]:
        key = payload_key if payload else remote_key
        if not isinstance(obj, dict) or key not in obj:
            continue
        value = obj[key]
        if isinstance(value, list):
            value = sorted(value, key=lambda item: canonical_json(item))
        result[remote_key] = value
    return result


def owned_hash(kind, obj, *, payload=False):
    return sha256_hex(canonical_json(owned_projection(kind, obj, payload=payload)))


# --- adapter read/write helpers --------------------------------------------

def remote_get(adapter, kind, native_id, logical_key):
    if adapter is None:
        raise CoreError("adapter_required", "an adapter is required for this operation")
    try:
        remote = adapter.get(kind, native_id)
    except Exception as exc:
        code = adapter_code(exc)
        if is_permission_code(code):
            raise CoreError("permission_denied", "adapter denied read of %s" % logical_key, details=[code]) from None
        raise CoreError("adapter_error", "adapter read failed for %s" % logical_key,
                        details=[code or type(exc).__name__]) from None
    return remote


def safe_readback(adapter, kind, native_id):
    try:
        return adapter.get(kind, native_id), None
    except Exception as exc:
        code = adapter_code(exc)
        if is_permission_code(code):
            raise CoreError("permission_denied", "adapter denied readback", details=[code]) from None
        return None, code or type(exc).__name__


def _block_remote(logical_key, kind, remote):
    if remote is None:
        raise CoreError("mapping_missing",
                        "recorded %s %s is missing remotely; refusing to replace it" % (kind, logical_key))
    if remote.get("archived"):
        raise CoreError("mapping_archived",
                        "recorded %s %s is archived; refusing to replace it" % (kind, logical_key))


def ensure_create(store, adapter, logical_key, kind, payload):
    """Idempotent get-before-create with a durable UUID intent and readback."""
    if store is None or adapter is None:
        raise CoreError("state_required", "Durable state and adapter required")
    digest = owned_hash(kind, payload, payload=True)
    mapping = store.get_mapping(logical_key)
    native_id = mapping["native_id"] if mapping else store.allocate_uuid(logical_key, kind)
    intent_id = "create:" + logical_key
    intent = store.get_intent(intent_id)
    if intent and intent.get("payload_digest") != digest:
        raise CoreError("sync_conflict", "Pending operation content changed; resolve its receipt before continuing")
    remote = remote_get(adapter, kind, native_id, logical_key)
    if remote is not None:
        _block_remote(logical_key, kind, remote)
        if remote.get("id") != native_id:
            raise CoreError("sync_conflict", "Remote identity differs from persisted intent")
        if mapping and mapping.get("readback_hash") and owned_hash(kind, remote) != mapping["readback_hash"]:
            raise CoreError("human_edit_conflict", "Managed resource changed remotely; preserving it")
        # Compare only requested fields; null optional server fields are not payload.
        expected = owned_projection(kind, payload, payload=True)
        if any(owned_projection(kind, remote).get(k) != v for k, v in expected.items()):
            raise CoreError("sync_conflict", "Readback differs from intended publication")
        action = "reuse" if mapping and mapping.get("status") == "active" else "recovered"
        if action != "reuse":
            _finalize_created(store, logical_key, kind, native_id, digest, remote, intent_id, action)
        return {"action": action, "kind": kind, "logical_key": logical_key, "native_id": native_id}, remote
    if mapping and mapping.get("status") == "active":
        _block_remote(logical_key, kind, remote)
    # Persist the complete intent before the network boundary. Reusing the same
    # UUID4 after a definitive absent read cannot create a second resource.
    store.upsert_intent(intent_id, "create", logical_key, kind, digest, "sent",
                        native_id=native_id, detail=canonical_json(payload), attempts_delta=1)
    try:
        adapter.create(kind, native_id, payload)
    except Exception as exc:
        code = adapter_code(exc)
        if is_permission_code(code):
            store.upsert_intent(intent_id, "create", logical_key, kind, digest, "denied", native_id=native_id)
            raise CoreError("permission_denied", "Remote publication denied; no alternate route attempted") from None
        remote, _ = safe_readback(adapter, kind, native_id)
        if remote is None:
            raise CoreError("sync_uncertain",
                            "Write outcome is uncertain; intent retained for read-before-retry") from None
    else:
        remote, _ = safe_readback(adapter, kind, native_id)
    if remote is None:
        raise CoreError("sync_uncertain", "Readback unavailable; durable intent retained")
    _block_remote(logical_key, kind, remote)
    expected = owned_projection(kind, payload, payload=True)
    if remote.get("id") != native_id or any(owned_projection(kind, remote).get(k) != v for k, v in expected.items()):
        raise CoreError("sync_conflict", "Readback did not match the publication; no verified receipt recorded")
    _finalize_created(store, logical_key, kind, native_id, digest, remote, intent_id, "create")
    return {"action": "create", "kind": kind, "logical_key": logical_key, "native_id": native_id}, remote


def _finalize_created(store, logical_key, kind, native_id, payload_digest, remote, intent_id, operation):
    readback = owned_hash(kind, remote)
    store.put_mapping(logical_key, kind, native_id, payload_digest=payload_digest,
                      readback_hash=readback, status="active")
    store.put_receipt(logical_key, kind, operation, native_id=native_id,
                      payload_digest=payload_digest, readback_hash=readback)
    store.upsert_intent(intent_id, "create", logical_key, kind, payload_digest, "verified", native_id=native_id)


# --- Markdown rendering ----------------------------------------------------

def render_reference(ref, config):
    root = ref.get("documentation_root") or ref.get("code_root") or ref.get("documentation_repository", "")
    location = ref.get("url") or str(root) + ":" + str(ref.get("path", ""))
    status = "unchecked URL; no access observation" if ref.get("url") else ref.get("access", "unchecked")
    if ref.get("path"):
        code = ref.get("role") == "code"
        checks = _resolve_local_ref(ref, config, "code_roots" if code else "documentation_roots",
                                    "code_root" if code else "documentation_root", None)
        status = "verified local; remote readers need declared access" if not checks else \
            "inaccessible: " + ", ".join(x["code"] for x in checks)
    host = ref.get("host") or cfg(config, "documentation_roots", root, "host",
                                  default="resolve through operator root registry")
    return [
        "- **" + ref["title"] + "** (" + ref["role"] + ") — " + ref["relevance"],
        "  Location: " + location + "; root: " + str(root) + "; host: " + str(host),
        "  Revision: " + ref["revision"] + "; SHA256: " + str(ref.get("content_hash", "see revision")) +
        "; knowledge date: " + ref["knowledge_date"],
        "  Standing: " + ref["standing"] + "; access: " + status + "; essential: " + str(ref["essential"]).lower()]


def _issue_description(task, packet=None, config=None):
    packet = packet or {"spec": {}, "context": []}
    lines = ["## Outcome", "", str(task["outcome"]), "", "## Scope and acceptance", ""]
    lines.extend("- [ ] " + item for item in task["acceptance"])
    lines += ["", "Non-goals / constraints: " + str(task.get("constraints", "See approved spec.")),
              "", "## Current state", "",
              "Owner: unclaimed. This document does not establish an execution attempt.",
              "Sync: publication is verified only after readback. Never infer permission from tracker status.",
              "", "## Context index — read in this order", "",
              "Governing spec: " + str((packet.get("spec") or {}).get("spec_id")) +
              "; approved content SHA256: " + semantic_digest(packet)]
    for ref in packet.get("context", []):
        if ref["id"] in task.get("context_ids", []):
            lines += render_reference(ref, config or {})
    lines += ["", "## Work and evidence", "", "Kind: " + str(task["kind"]),
              "Code repository: " + str(task.get("repository", "not applicable")),
              "Integration branch: " + str(task.get("base_branch", "not applicable")),
              "Required delivery contract: " + canonical_json(task.get("completion", {}))]
    return "\n".join(lines)


def render_packet(packet, config):
    """Render the project, spec, context and task Markdown for review."""
    spec = packet.get("spec") or {}
    project = packet.get("project") or {}
    lines = ["# " + str(project.get("name") or spec.get("title") or "Packet"), "",
             "Spec: `" + str(spec.get("spec_id")) + "`  ",
             "Content digest: `" + semantic_digest(packet) + "`", "",
             "## Project", "", "**Summary.** " + str(project.get("summary", "")), "",
             "**Closure.** " + str(project.get("closure", "")), "",
             "## Spec", "", "### " + str(spec.get("title", "")), "", str(spec.get("markdown", "")), "",
             "## Context", ""]
    for ref in packet.get("context") or []:
        lines += render_reference(ref, config) + [""]
    lines += ["## Tasks", ""]
    for task in packet.get("tasks") or []:
        lines += ["### " + str(task.get("title", "")) + " (`" + str(task.get("task_id", "")) + "`)", "",
                  _issue_description(task, packet, config), ""]
    return "\n".join(lines)


# --- publication -----------------------------------------------------------

def _task_map(packet):
    return {task["task_id"]: task for task in packet.get("tasks") or []}


def _project_logical_key(packet):
    return "project:%s" % (packet.get("spec") or {}).get("spec_id")


def _context_content(packet, config):
    project = packet["project"]
    lines = ["# Context index", "", "Approved scope: " + semantic_digest(packet), "",
             "## Approved project orientation", "", "Name: " + project["name"], "",
             project["summary"], "", "Closure: " + project["closure"], "",
             "This versioned index contains the approved project revision. The native container's original fields are preserved.", ""]
    for ref in packet["context"]:
        lines += render_reference(ref, config) + [""]
    return "\n".join(lines)


def _context_key(packet, config):
    return "context_document:%s:%s" % (packet["spec"]["spec_id"], sha256_hex(_context_content(packet, config)))


def build_publication_plan(packet, config):
    spec_id, digest = (packet.get("spec") or {}).get("spec_id"), semantic_digest(packet)
    plan = [
        {"action": "project", "logical_key": _project_logical_key(packet), "kind": "project"},
        {"action": "document", "logical_key": "spec_document:%s:%s" % (spec_id, digest),
         "kind": "document", "role": "spec_revision"},
        {"action": "document", "logical_key": _context_key(packet, config),
         "kind": "document", "role": "context_index"}]
    for task in packet.get("tasks") or []:
        plan.append({"action": "issue", "logical_key": "issue:%s" % task["task_id"],
                     "kind": "issue", "task_id": task["task_id"]})
        for dep in task.get("dependencies") or []:
            plan.append({"action": "relation", "logical_key": "relation:%s:%s" % (task["task_id"], dep),
                         "kind": "relation", "task_id": task["task_id"], "related_task_id": dep})
    return plan


def _check_public_destination(packet, config):
    # This adapter publishes private work packets only. Public GitHub text has a
    # separate privacy gate (check-public) and never receives the packet.
    raise CoreError("public_disabled", "The pilot has no public-tracker publication route")


def _surface_adoptions(packet):
    """Imported native identities surfaced in preview for explicit review."""
    adoptions = []
    container = cfg(packet, "spec", "metadata", "tracker_container")
    if container:
        adoptions.append({"logical_key": _project_logical_key(packet), "kind": "project",
                          "native_id": container, "note": "imported project; requires exact permission scope"})
    document = cfg(packet, "spec", "metadata", "tracker_document")
    if document:
        adoptions.append({"logical_key": "legacy_document:" + str(document), "kind": "document",
                          "native_id": document, "note": "imported document; membership verified against the project"})
    for task in packet.get("tasks") or []:
        if task.get("native_id"):
            adoptions.append({"logical_key": "issue:" + task["task_id"], "kind": "issue",
                              "native_id": task["native_id"], "note": "imported issue; membership verified against the project"})
    return adoptions


def _verify_adoptions(packet, store):
    """Bookkeeping cannot choose new native targets; store conflicts are blocked."""
    mappings = store.list_mappings()
    for task in packet["tasks"]:
        identity = task.get("native_id")
        if not identity:
            continue
        logical = "issue:" + task["task_id"]
        existing = store.get_mapping(logical)
        if existing and existing["native_id"] != identity:
            raise CoreError("sync_conflict", "Imported and durable issue mappings disagree")
        if any(m["kind"] == "issue" and m["native_id"] == identity and m["logical_key"] != logical for m in mappings):
            raise CoreError("sync_conflict", "An issue is already mapped to another logical task")


def _publish_project(store, adapter, packet, config, permission):
    logical_key = _project_logical_key(packet)
    mapping = store.get_mapping(logical_key)
    declared = (packet["spec"].get("metadata", {})).get("tracker_container") or \
        cfg(config, "integration", "private_destination", "project_id")
    if declared and mapping and mapping["native_id"] != declared:
        raise CoreError("sync_conflict", "Stored and canonical project mappings disagree")
    recorded, scoped = (mapping or {}).get("native_id") or declared, permission.get("project_id")
    if scoped and not recorded:
        raise CoreError("mapping_missing", "Record the authorized existing project mapping before publication")
    if scoped and recorded and scoped != recorded:
        raise CoreError("authorization_invalid", "Permission does not cover the mapped project")
    if recorded and (declared or mapping.get("status") == "active"):
        # An existing or imported project is reused; membership is verified and
        # it is never silently replaced.
        if not mapping and scoped != recorded:
            raise CoreError("authorization_invalid", "Adopting a project requires its exact ID in the permission scope")
        remote = remote_get(adapter, "project", recorded, logical_key)
        if remote is None:
            raise CoreError("project_missing", "Recorded project is absent or inaccessible; never replace it")
        if remote.get("archived"):
            raise CoreError("project_archived", "Recorded project is archived; inspect deliberately")
        if mapping and mapping.get("readback_hash") and owned_hash("project", remote) != mapping["readback_hash"]:
            raise CoreError("human_edit_conflict", "Project content changed; preserve the human edit")
        if not mapping:
            store.put_mapping(logical_key, "project", recorded, readback_hash=owned_hash("project", remote),
                              status="active", meta={"adopted": True})
        return {"action": "reuse", "kind": "project", "native_id": recorded,
                "approved_content_location": "context_index", "native_container_updated": False}
    if not permission.get("create_project"):
        raise CoreError("authorization_invalid", "Creating a project is not authorized")
    team = cfg(config, "integration", "team_id")
    if not team:
        raise CoreError("configuration_required", "Linear team_id is required")
    project = packet["project"]
    payload = {"name": project["name"], "description": project["summary"][:255],
               "content": "## Outcome\n\n" + project["summary"] + "\n\n## Closure\n\n" + project["closure"],
               "teamIds": [team]}
    action, _ = ensure_create(store, adapter, logical_key, "project", payload)
    action["approved_content_location"] = "context_index"
    return action


def _publish_document(store, adapter, logical_key, title, content, project_id, role):
    action, _ = ensure_create(store, adapter, logical_key, "document",
                              {"title": title, "content": content, "projectId": project_id})
    action["role"] = role
    return action


def _publish_issue(store, adapter, packet, config, task, project_id):
    logical_key = "issue:" + task["task_id"]
    payload = {"title": task["title"], "description": _issue_description(task, packet, config),
               "teamId": cfg(config, "integration", "team_id"), "projectId": project_id,
               "stateId": cfg(config, "integration", "status_ids", "todo"),
               "labelIds": cfg(config, "repositories", task.get("repository"), "label_ids", default=[])}
    mapping, existing_id, title_digest = store.get_mapping(logical_key), task.get("native_id"), semantic_digest(packet)
    content_digest = sha256_hex(payload["description"])
    if existing_id and mapping and existing_id != mapping["native_id"]:
        raise CoreError("sync_conflict", "Existing issue mappings disagree")
    if existing_id and not mapping:
        # Imported issue: verify membership before adopting, never replace.
        remote = remote_get(adapter, "issue", existing_id, logical_key)
        _block_remote(logical_key, "issue", remote)
        if remote.get("project_id") != project_id:
            raise CoreError("sync_conflict", "Imported issue is in a different project")
        store.put_mapping(logical_key, "issue", existing_id, readback_hash=owned_hash("issue", remote),
                          status="active", meta={"adopted": True})
        mapping = store.get_mapping(logical_key)
    if mapping and mapping.get("status") == "active":
        remote = remote_get(adapter, "issue", mapping["native_id"], logical_key)
        _block_remote(logical_key, "issue", remote)
        if remote.get("project_id") != project_id:
            raise CoreError("sync_conflict", "Mapped issue moved out of project")
        if mapping.get("readback_hash") != owned_hash("issue", remote):
            raise CoreError("human_edit_conflict", "Issue scope changed; preserving human edits")
        if store.get_meta("packet:" + task["task_id"]) == title_digest and \
                store.get_meta("packet_content:" + task["task_id"]) == content_digest:
            return {"action": "reuse", "kind": "issue", "task_id": task["task_id"], "native_id": mapping["native_id"]}
        # Never overwrite the native issue body. Each approved packet revision
        # gets an immutable managed revision comment.
        key = "packet_comment:%s:%s:%s:%s" % (packet["spec"]["spec_id"], task["task_id"], title_digest, content_digest)
        revision_comment, _ = ensure_create(store, adapter, key, "comment", {
            "issueId": mapping["native_id"], "body": "## Approved scope / context revision\n\n"
            + payload["description"].split("## Current state")[0]
            + "Current execution facts remain in the latest issue handoff.\n\n## Context index"
            + payload["description"].split("## Context index", 1)[1]})
        store.set_meta("packet:" + task["task_id"], title_digest)
        store.set_meta("packet_content:" + task["task_id"], content_digest)
        return {"action": "append_revision", "kind": "issue", "task_id": task["task_id"],
                "native_id": mapping["native_id"], "revision_comment": revision_comment}
    action, _ = ensure_create(store, adapter, logical_key, "issue", payload)
    action["task_id"] = task["task_id"]
    store.set_meta("packet:" + task["task_id"], title_digest)
    store.set_meta("packet_content:" + task["task_id"], content_digest)
    return action


def _publish_relation(store, adapter, task, related_task_id, issue_ids):
    # A task declares prerequisites: the prerequisite BLOCKS the dependent task.
    action, _ = ensure_create(store, adapter, "relation:%s:%s" % (task["task_id"], related_task_id), "relation", {
        "issueId": issue_ids[related_task_id], "relatedIssueId": issue_ids[task["task_id"]], "type": "blocks"})
    return action


def publish(packet, config, authority, *, apply=False, store=None, adapter=None,
            destination="private", path_probe=None, url_checker=None):
    """Preview (default, no mutation) or apply a private publication within authority."""
    errors = collect_validation_errors(packet, config, path_probe=path_probe, url_checker=url_checker)
    if errors:
        raise CoreError("validation_failed", "Packet failed validation", details=errors)
    if destination != "private" or cfg(config, "integration", "visibility", default="private") != "private":
        _check_public_destination(packet, config)
    digest, report, plan = semantic_digest(packet), authority_report(authority, packet), build_publication_plan(packet, config)

    if not apply:
        known = store.list_mappings() if store else []
        recorded_project = cfg(packet, "spec", "metadata", "tracker_container")
        if recorded_project and not any(m["logical_key"] == _project_logical_key(packet) for m in known):
            known = list(known) + [{"logical_key": _project_logical_key(packet), "kind": "project",
                                    "native_id": recorded_project, "status": "active"}]
        for item in plan:
            mapping = next((m for m in known if m["logical_key"] == item["logical_key"]), None)
            if mapping:
                item["native_id"], item["intent"] = mapping["native_id"], "reuse/verify"
            elif item.get("role") == "spec_revision":
                item["intent"] = "create immutable revision document"
            else:
                item["intent"] = "create if authorized"
            stored = store.get_meta("packet:" + item["task_id"]) if store and item["kind"] == "issue" else digest
            if item["kind"] == "issue" and item.get("native_id") and digest != stored:
                item["revision_action"] = "append approved packet revision comment"
        findings, checked = [], 0
        for mapping in known if adapter else []:
            if mapping["status"] != "active":
                findings.append({"code": "publication_pending", "logical_key": mapping["logical_key"]})
                continue
            try:
                remote = remote_get(adapter, mapping["kind"], mapping["native_id"], mapping["logical_key"])
                _block_remote(mapping["logical_key"], mapping["kind"], remote)
                checked += 1
                if remote.get("id") != mapping["native_id"] or (
                        mapping.get("readback_hash") and owned_hash(mapping["kind"], remote) != mapping["readback_hash"]):
                    findings.append({"code": "human_edit_conflict", "logical_key": mapping["logical_key"]})
            except CoreError as exc:
                findings.append({"code": exc.code, "logical_key": mapping["logical_key"]})
        can_apply = not findings and all(value == "coherent" for value in report.values())
        return {"ok": can_apply, "can_apply": can_apply, "operation": "publish", "applied": False,
                "semantic_digest": digest, "authority_source_verified_by_script": False,
                "plan": plan, "authorization": report, "adoptions": _surface_adoptions(packet),
                "findings": findings, "remote": "mapped resources checked" if checked else "unchecked",
                "preview": render_packet(packet, config),
                "blocked": [k for k, v in report.items() if v != "coherent"]}

    approval = verify_approval(authority, packet)
    permission = verify_permission(authority, packet, "publish")
    if not store or store.readonly or not adapter:
        raise CoreError("state_required", "Apply requires a writable durable operation store and adapter")
    if store.get_meta("spec_id") not in (None, packet["spec"]["spec_id"]):
        raise CoreError("scope_conflict", "Store is bound to a different project; use its original store")
    _verify_adoptions(packet, store)
    # Check prior managed mirrors before creating a new revision. Never treat an
    # inaccessible known document as a missing new publication.
    for mapping in store.list_mappings(kind="document"):
        if mapping["status"] != "active":
            continue
        remote = remote_get(adapter, "document", mapping["native_id"], mapping["logical_key"])
        _block_remote(mapping["logical_key"], "document", remote)
        if mapping.get("readback_hash") and owned_hash("document", remote) != mapping["readback_hash"]:
            raise CoreError("human_edit_conflict", "An earlier mirror has human edits; preserve and review before publishing")
    capability = adapter.capabilities() if hasattr(adapter, "capabilities") else None
    if capability and not all(capability.get("creates", {}).get(kind, {}).get("supported") for kind in ADAPTER_KINDS):
        raise CoreError("capability_missing", "Adapter schema does not support the required publication operations")
    store.set_meta("spec_id", packet["spec"]["spec_id"])
    actions = [_publish_project(store, adapter, packet, config, permission)]
    project_id = actions[0]["native_id"]
    if permission.get("project_id") and permission["project_id"] != project_id:
        raise CoreError("authorization_invalid", "Permission does not cover the resulting project")
    legacy_doc = cfg(packet, "spec", "metadata", "tracker_document")
    if legacy_doc and not any(m["native_id"] == legacy_doc for m in store.list_mappings(kind="document")):
        old = remote_get(adapter, "document", legacy_doc, "recorded tracker_document")
        _block_remote("recorded tracker_document", "document", old)
        if old.get("project_id") != project_id:
            raise CoreError("sync_conflict", "Recorded document belongs to another project")
        store.put_mapping("legacy_document:" + legacy_doc, "document", legacy_doc,
                          readback_hash=owned_hash("document", old), status="active", meta={"adopted": True})
    spec = packet["spec"]
    actions.append(_publish_document(store, adapter, "spec_document:%s:%s" % (spec["spec_id"], digest),
                                     spec["title"] + " (approved " + digest[:12] + ")", spec["markdown"],
                                     project_id, "spec_revision"))
    context_action = _publish_document(
        store, adapter, _context_key(packet, config),
        packet["project"]["name"] + " — context " + digest[:12] + "/" + sha256_hex(_context_content(packet, config))[:8],
        _context_content(packet, config), project_id, "context_index")
    actions.append(context_action)
    issue_ids = {}
    for task in packet["tasks"]:
        action = _publish_issue(store, adapter, packet, config, task, project_id)
        issue_ids[task["task_id"]] = action["native_id"]
        actions.append(action)
    for task in packet["tasks"]:
        for dep in task.get("dependencies", []):
            actions.append(_publish_relation(store, adapter, task, dep, issue_ids))
    mappings = {"tracker": "linear", "tracker_container": project_id, "tracker_document": actions[1]["native_id"],
                "context_document": context_action["native_id"], "approved_revision": digest, "tasks": issue_ids}
    store.set_meta("last_publish:" + spec["spec_id"],
                   {"digest": digest, "approved_by": approval.get("approved_by"), "mappings": mappings})
    return {"ok": True, "operation": "publish", "applied": True, "semantic_digest": digest,
            "authorization": report, "actions": actions, "mappings": mappings,
            "source_metadata_preserved": spec.get("metadata", {}), "sync_health": "verified"}


# --- record: append one concise, deduplicated issue note -------------------

def _request_errors(request):
    errors = []

    def fail(code, field, message):
        errors.append({"code": code, "path": field, "message": message})

    if not is_uuid4(request.get("request_id")):
        fail("bad_uuid4", "request_id", "Request id must be UUID4")
    if not is_uuid4(request.get("task_id")):
        fail("bad_uuid4", "task_id", "Task id must be UUID4")
    if request.get("kind") not in REQUEST_KINDS:
        fail("bad_value", "kind", "Unsupported request kind")
    if not isinstance(request.get("observed_at"), str) or not request["observed_at"].strip():
        fail("missing", "observed_at", "observed_at is required")
    else:
        try:
            parse_time(request["observed_at"])
        except (ValueError, TypeError):
            fail("bad_date", "observed_at", "observed_at must be ISO8601")
    if not isinstance(request.get("summary"), str) or not request["summary"].strip():
        fail("missing", "summary", "Summary required")
    if not isinstance(request.get("facts"), dict):
        fail("bad_type", "facts", "Facts must be an object")
    if not isinstance(request.get("next_action"), str) or not request["next_action"].strip():
        fail("missing", "next_action", "Next action required")
    return errors


def _observed(value):
    return parse_time(value) or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


def _request_note(request):
    lines = ["## " + request["kind"].capitalize(), "", request["summary"], "",
             "Observed: " + request["observed_at"], ""]
    for key, value in sorted(request["facts"].items()):
        label = key.replace("_", " ").capitalize()
        rendered = value if isinstance(value, str) else canonical_json(value)
        lines.append("- **" + label + ":** " + rendered)
    lines += ["", "**Next action:** " + request["next_action"], "",
              "<!-- workflow-request: " + request["request_id"] + " -->", ""]
    return "\n".join(lines)


def record(packet, config, request, *, apply=False, store=None, adapter=None, authority=None):
    """Append one well-labeled issue note, deduplicated by durable request UUID."""
    if not isinstance(request, dict):
        raise CoreError("bad_request", "A request object is required")
    errors = _request_errors(request)
    if errors:
        raise CoreError("bad_request", "Request failed validation", details=errors)
    if cfg(config, "integration", "visibility", default="private") != "private":
        _check_public_destination(packet, config)
    project_mapping = store.get_mapping(_project_logical_key(packet)) if store else None
    if not project_mapping or project_mapping.get("status") != "active":
        raise CoreError("mapping_missing", "Publish and verify the project before recording issue notes")
    project_id = project_mapping["native_id"]
    if apply:
        if not store or store.readonly or not adapter:
            raise CoreError("state_required", "Apply requires writable durable state and an adapter")
        verify_approval(authority, packet)
        permission = verify_permission(authority, packet, "record", project_id=project_id)
        if permission.get("project_id") != project_id:
            raise CoreError("authorization_invalid", "Record permission must name the published project")
    task_id = request["task_id"]
    task = _task_map(packet).get(task_id)
    if task is None:
        raise CoreError("bad_request", "Request references a task not in the packet")
    logical_key = "issue:" + task_id
    mapping = store.get_mapping(logical_key) if store else None
    if not mapping or not mapping.get("native_id"):
        raise CoreError("mapping_missing", "No published issue is mapped for this task")
    native_id, digest = mapping["native_id"], sha256_hex(canonical_json(request))
    project = remote_get(adapter, "project", project_id, _project_logical_key(packet))
    _block_remote(_project_logical_key(packet), "project", project)
    remote = remote_get(adapter, "issue", native_id, logical_key)
    _block_remote(logical_key, "issue", remote)
    if remote.get("id") != native_id or remote.get("project_id") != project_id:
        raise CoreError("sync_conflict", "Mapped issue identity or project membership changed")
    if task["kind"] == "research" and request["kind"] == "result":
        result_errors = verify_research_result(task, request["facts"], config)
        if result_errors:
            raise CoreError("validation_failed", "Research result evidence is incomplete", details=result_errors)
    recorded = store.get_meta("request:" + request["request_id"]) if store else None
    if isinstance(recorded, dict):
        if recorded.get("digest") != digest:
            raise CoreError("request_conflict", "Request id was reused with different content")
        comment = remote_get(adapter, "comment", recorded["native_id"], "recorded request")
        _block_remote("recorded request", "comment", comment)
        if comment.get("body") != _request_note(request) or comment.get("issue_id") != native_id:
            raise CoreError("human_edit_conflict", "Recorded note changed; preserve it")
        return {"ok": True, "operation": "record", "applied": apply, "reused": True,
                "request_id": request["request_id"], "issue_id": native_id, "comment_id": recorded["native_id"]}
    # A newer note cannot be overwritten by an older observation.
    latest = store.get_meta("request_latest:" + task_id) if store else None
    if isinstance(latest, dict) and _observed(request["observed_at"]) < _observed(latest.get("observed_at")):
        raise CoreError("stale_event", "A newer observation is already recorded for this task")
    body = _request_note(request)
    if not apply:
        return {"ok": True, "operation": "record", "applied": False, "request_id": request["request_id"],
                "issue_id": native_id, "note": "Preview only; no issue comment was written.", "body": body}
    action, _ = ensure_create(store, adapter, "request_comment:%s:%s" % (task_id, request["request_id"]),
                              "comment", {"issueId": native_id, "body": body})
    store.set_meta("request:" + request["request_id"], {
        "request_id": request["request_id"], "task_id": task_id, "observed_at": request["observed_at"],
        "digest": digest, "native_id": action["native_id"], "recorded_at": now_iso()})
    store.set_meta("request_latest:" + task_id,
                   {"observed_at": request["observed_at"], "request_id": request["request_id"]})
    return {"ok": True, "operation": "record", "applied": True, "reused": action["action"] == "reuse",
            "request_id": request["request_id"], "issue_id": native_id, "comment_id": action["native_id"]}


# --- delivery evidence checks (reused by the independent audit) ------------

def verify_code_completion(task, config, evidence, *, require_merge=True):
    findings = []

    def fail(code, **detail):
        findings.append({"code": code, "task_id": task.get("task_id"), **detail})

    prs = cfg(task, "completion", "required_prs", default=[])
    if not prs:
        fail("required_prs_missing")
        return findings
    registry = cfg(config, "repositories", task.get("repository"), default={})
    integration = registry.get("base_branch")
    if not integration or integration != task.get("base_branch"):
        fail("integration_branch_unconfigured")
        return findings
    for pr in prs:
        if not pr.get("number") or not re.fullmatch(r"[a-f0-9]{40}", str(pr.get("head_sha", ""))):
            fail("pr_association_missing")
            continue
        if pr.get("repo") != registry.get("repo"):
            fail("pr_repository_mismatch")
            continue
        if evidence is None:
            fail("evidence_unavailable")
            continue
        try:
            data = evidence.pull_request(pr["repo"], pr["number"])
        except Exception as exc:
            fail("pr_read_failed", detail=adapter_code(exc) or type(exc).__name__)
            continue
        if data.get("repo") != pr["repo"] or data.get("number") != pr["number"]:
            fail("pr_identity_mismatch")
            continue
        if data.get("base_branch") != integration:
            fail("wrong_base_branch")
        if data.get("draft") is not False:
            fail("pr_is_draft")
        if require_merge and (not data.get("merged") or not data.get("merge_commit_sha")):
            fail("pr_not_merged")
        if data.get("head_sha") != pr["head_sha"]:
            fail("head_sha_mismatch")
        # Multiple facts with one name must all satisfy a required check, rather
        # than letting a later arbitrary list entry hide a failure.
        for name in pr.get("required_checks", []):
            checks = [c for c in data.get("checks", []) if c.get("name") == name]
            if not checks or any(c.get("conclusion") != "success" or c.get("sha") != pr["head_sha"] for c in checks):
                fail("check_not_green_at_head", check=name)
        latest = {}
        for review in data.get("reviews", []):
            if str(review.get("state", "")).lower() in ("approved", "changes_requested", "dismissed"):
                latest[review.get("actor")] = review
        for actor in pr.get("required_reviewers", []):
            review = latest.get(actor, {})
            if str(review.get("state", "")).lower() != "approved" or review.get("commit_sha") != pr["head_sha"]:
                fail("reviewer_not_approved_at_head", reviewer=actor)
    return findings


def verify_research_result(task, request, config=None):
    findings = []

    def missing(field):
        findings.append({"code": "research_field_missing", "field": field})

    research = request.get("research") or {}
    for field in ("question", "config", "dataset", "seeds", "run", "artifacts", "analysis", "review"):
        if research.get(field) in (None, "", [], {}):
            missing(field)
    run = research.get("run") or {}
    if not isinstance(run, dict) or not run.get("experiment_run_id") or not run.get("code_revision"):
        missing("run.experiment_run_id/code_revision")
    artifacts = research.get("artifacts") or []
    if not isinstance(artifacts, list) or any(
            not isinstance(a, dict) or not a.get("uri") or not re.fullmatch(r"[a-f0-9]{64}", str(a.get("sha256", "")))
            for a in artifacts):
        missing("artifact location and SHA256")
    elif artifacts:
        for artifact in artifacts:
            if not artifact.get("path") or not artifact.get("documentation_root"):
                findings.append({"code": "artifact_evidence_unavailable",
                                 "detail": "Pilot requires a declared local artifact; remote observation remains pending"})
                continue
            findings.extend(_resolve_local_ref({**artifact, "content_hash": artifact["sha256"]}, config or {},
                                               "documentation_roots", "documentation_root", None))
    analysis = research.get("analysis") or {}
    if not isinstance(analysis, dict) or not analysis.get("conclusion") or not analysis.get("limitations"):
        missing("analysis.conclusion/limitations")
    review = research.get("review") or {}
    if not isinstance(review, dict) or review.get("decision") != "approved" or \
            review.get("reviewer") in (None, "", request.get("owner")) or not review.get("evidence"):
        missing("independent scientific review")
    if request.get("outcome") not in ("supported", "negative") or request.get("running_jobs"):
        findings.append({"code": "not_a_completed_research_result"})
    return findings


def capabilities(config=None):
    return {
        "schema_version": SCHEMA_VERSION, "interface_version": 1, "runtime": "workflow.core",
        "pilot": {"scope": "supervised single-project local pilot", "daemon": False,
                  "cross_host_exclusivity": False, "writer_scope": "one supervised writer"},
        "operations": ["capabilities", "validate", "render", "publish", "record", "audit",
                       "check-public", "demo"],
        "supported": ["packet_validation", "semantic_approval_digest", "external_authority_coherence",
                      "durable_uuid_allocation", "idempotent_get_before_create", "readback_receipts",
                      "human_edit_detection", "public_text_privacy_validation", "issue_note_recording"],
        "deferred": ["live_rollout_and_integration_evidence", "cross_host_exclusivity",
                     "conditional_document_update", "research_launch", "automatic_project_closure",
                     "unattended_repair", "cryptographic_authorization"],
        "trust_boundary": ("Authority is external JSON checked for coherence, never authenticity; it is "
                           "bookkeeping, not cryptographic enforcement. The model must verify the actual "
                           "approval and source and respect any narrower scope.")}
