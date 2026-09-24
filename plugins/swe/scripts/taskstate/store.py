"""SQLite connection, schema, migrations, backup/export. Stdlib only."""
from __future__ import annotations

import datetime
import json
import os
import re
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 4

SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class StoreError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def state_root():
    raw = os.environ.get("TASKSTATE_HOME", "~/.local/state/taskstate")
    root = Path(os.path.expanduser(raw)).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def db_path_for_slug(slug, root=None):
    if not slug or not SLUG_RE.match(slug):
        raise StoreError("validation_failed", "Invalid project slug: %r" % (slug,))
    root = Path(root) if root is not None else state_root()
    root = root.resolve()
    path = (root / (slug + ".db")).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise StoreError("validation_failed", "Database path outside state root")
    if path.parent != root:
        raise StoreError("validation_failed", "Database path outside state root")
    return path


def _owner_only(path):
    """Create path owner-only (0600), or tighten it if it is broader.

    Stores hold private notes; SQLite gives -wal/-shm files the main file's
    mode, so fixing the main file covers them when they are created."""
    path = str(path)
    if not os.path.exists(path):
        os.close(os.open(path, os.O_CREAT | os.O_WRONLY, 0o600))
    for candidate in (path, path + "-wal", path + "-shm"):
        try:
            if os.stat(candidate).st_mode & 0o077:
                os.chmod(candidate, 0o600)
        except OSError:
            pass


def connect(path, timeout=5.0, busy_timeout_ms=5000):
    _owner_only(path)
    conn = sqlite3.connect(str(path), timeout=timeout, isolation_level=None,
                           detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except sqlite3.Error:
        pass
    try:
        conn.execute("PRAGMA busy_timeout=%d;" % max(1, int(busy_timeout_ms)))
    except sqlite3.Error:
        pass
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
    except sqlite3.Error:
        pass
    return conn


MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS project(
  project_id TEXT PRIMARY KEY, slug TEXT UNIQUE NOT NULL,
  disclosure TEXT NOT NULL DEFAULT 'internal', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS task(
  task_id TEXT PRIMARY KEY, ref TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'code', spec_id TEXT,
  lifecycle TEXT NOT NULL DEFAULT 'open', hold INTEGER NOT NULL DEFAULT 0,
  hold_reason TEXT, version INTEGER NOT NULL DEFAULT 1,
  claim_epoch INTEGER NOT NULL DEFAULT 0, owner_attempt TEXT,
  lease_expires_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS criterion(
  task_id TEXT NOT NULL REFERENCES task(task_id), ac_id TEXT NOT NULL,
  text TEXT NOT NULL, PRIMARY KEY(task_id, ac_id));
CREATE TABLE IF NOT EXISTS task_dep(
  task_id TEXT NOT NULL REFERENCES task(task_id) ON DELETE CASCADE,
  depends_on TEXT NOT NULL REFERENCES task(task_id) ON DELETE CASCADE,
  PRIMARY KEY(task_id, depends_on));
CREATE TABLE IF NOT EXISTS grant_(
  grant_id TEXT PRIMARY KEY, kind TEXT NOT NULL,
  scope_json TEXT NOT NULL, granted_by TEXT NOT NULL, source TEXT NOT NULL,
  recorded_via TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attempt(
  attempt_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES task(task_id),
  claim_epoch INTEGER NOT NULL, actor TEXT NOT NULL, host TEXT NOT NULL,
  worktree TEXT, branch TEXT, start_head TEXT, last_head TEXT,
  last_diff_hash TEXT, facts_observed_at TEXT,
  started_at TEXT NOT NULL, ended_at TEXT, end TEXT);
CREATE TABLE IF NOT EXISTS journal(
  entry_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES task(task_id),
  attempt_id TEXT REFERENCES attempt(attempt_id), kind TEXT NOT NULL,
  body TEXT NOT NULL, data_json TEXT, status TEXT NOT NULL,
  superseded_by TEXT, late INTEGER NOT NULL DEFAULT 0,
  actor TEXT NOT NULL, host TEXT NOT NULL,
  observed_at TEXT NOT NULL, recorded_at TEXT NOT NULL, request_id TEXT);
CREATE TABLE IF NOT EXISTS evidence(
  evidence_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES task(task_id),
  attempt_id TEXT REFERENCES attempt(attempt_id), criteria_json TEXT NOT NULL,
  kind TEXT NOT NULL, result TEXT NOT NULL, command TEXT, summary TEXT,
  inputs_json TEXT NOT NULL, artifact_refs_json TEXT NOT NULL,
  late INTEGER NOT NULL DEFAULT 0, actor TEXT NOT NULL, host TEXT NOT NULL,
  observed_at TEXT NOT NULL, recorded_at TEXT NOT NULL, request_id TEXT);
CREATE TABLE IF NOT EXISTS mutation(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT UNIQUE NOT NULL,
  command TEXT NOT NULL, actor TEXT NOT NULL, task_id TEXT,
  payload_digest TEXT NOT NULL, result_json TEXT NOT NULL,
  recorded_at TEXT NOT NULL);
"""

MIGRATION_2 = """
ALTER TABLE attempt ADD COLUMN checkpoint_head TEXT;
ALTER TABLE attempt ADD COLUMN checkpoint_diff_hash TEXT;
ALTER TABLE attempt ADD COLUMN checkpoint_at TEXT;
ALTER TABLE attempt ADD COLUMN start_diff_hash TEXT;
CREATE TABLE IF NOT EXISTS session(
  runtime TEXT NOT NULL,
  session_id TEXT NOT NULL,
  attempt_id TEXT REFERENCES attempt(attempt_id),
  task_id TEXT REFERENCES task(task_id),
  host TEXT,
  cwd TEXT,
  source TEXT,
  started_at TEXT,
  last_seen_at TEXT,
  head TEXT,
  diff_hash TEXT,
  end_reason TEXT,
  end_observed INTEGER NOT NULL DEFAULT 0,
  reminded_head TEXT,
  reminded_diff_hash TEXT,
  PRIMARY KEY(runtime, session_id)
);
"""

MIGRATION_3 = """
ALTER TABLE session ADD COLUMN end_inferred INTEGER NOT NULL DEFAULT 0;
CREATE TABLE IF NOT EXISTS job(
  cluster TEXT NOT NULL,
  job_id TEXT NOT NULL,
  task_id TEXT NOT NULL REFERENCES task(task_id),
  attempt_id TEXT REFERENCES attempt(attempt_id),
  submitted_by TEXT NOT NULL,
  host TEXT NOT NULL,
  last_state TEXT,
  last_state_at TEXT,
  exit_code TEXT,
  acknowledged INTEGER NOT NULL DEFAULT 0,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  request_id TEXT,
  PRIMARY KEY(cluster, job_id)
);
"""

MIGRATION_4 = """
ALTER TABLE task ADD COLUMN authority_host TEXT;
ALTER TABLE task ADD COLUMN delegation_epoch INTEGER NOT NULL DEFAULT 0;
ALTER TABLE task ADD COLUMN origin_host TEXT;
ALTER TABLE task ADD COLUMN revoke_pending INTEGER NOT NULL DEFAULT 0;
ALTER TABLE task ADD COLUMN revoke_force INTEGER NOT NULL DEFAULT 0;
ALTER TABLE task ADD COLUMN synced_at TEXT;
ALTER TABLE attempt ADD COLUMN origin_host TEXT;
ALTER TABLE journal ADD COLUMN origin_host TEXT;
ALTER TABLE evidence ADD COLUMN origin_host TEXT;
ALTER TABLE session ADD COLUMN origin_host TEXT;
ALTER TABLE job ADD COLUMN origin_host TEXT;
"""

MIGRATIONS = [(1, MIGRATION_1), (2, MIGRATION_2), (3, MIGRATION_3), (4, MIGRATION_4)]


def _get_meta(conn, key, default=None):
    try:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    except sqlite3.Error:
        return default
    return row[0] if row else default


def _set_meta(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (key, value))


def get_meta(conn, key, default=None):
    return _get_meta(conn, key, default)


def set_meta(conn, key, value):
    _set_meta(conn, key, str(value))


def _has_tables(conn):
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table' AND name='meta'").fetchone()
    return bool(row and row[0])


def _prepare_migration_sql(conn, version, sql):
    if version not in (2, 3, 4):
        return sql
    kept = []
    for line in sql.splitlines():
        stripped = line.strip()
        match = re.match(r"^ALTER TABLE ([A-Za-z_][A-Za-z0-9_]*) ADD COLUMN ([A-Za-z_][A-Za-z0-9_]*)\b",
                         stripped)
        if match:
            table, column = match.groups()
            try:
                existing = {row[1] for row in conn.execute("PRAGMA table_info(%s)" % table)}
            except sqlite3.Error:
                existing = set()
            if column in existing:
                continue
        kept.append(line)
    return "\n".join(kept)


def _next_ref_n(conn):
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='next_ref_n'").fetchone()
        if row is not None:
            return int(row[0])
    except (sqlite3.Error, TypeError, ValueError):
        pass
    highest = 0
    try:
        rows = conn.execute("SELECT ref FROM task").fetchall()
    except sqlite3.Error:
        rows = []
    for row in rows:
        text = str(row[0])
        suffix = text.rsplit("-", 1)[-1]
        try:
            highest = max(highest, int(suffix))
        except ValueError:
            continue
    return highest + 1


def ensure_schema(conn, slug=None, root=None):
    """Apply numbered migrations in a transaction; backup existing db first."""
    existed = _has_tables(conn)
    if existed:
        cur = _get_meta(conn, "schema_version", None)
        try:
            cur_v = int(cur) if cur is not None else 0
        except ValueError:
            cur_v = 0
    else:
        cur_v = 0
    if cur_v > SCHEMA_VERSION:
        raise StoreError("schema_too_new",
                         "Database schema %d is newer than supported schema %d" %
                         (cur_v, SCHEMA_VERSION))
    if cur_v >= SCHEMA_VERSION:
        return cur_v
    if existed:
        if slug is None:
            raise StoreError("backup_identity_required",
                             "A project slug is required before migrating an existing database")
        try:
            backup_db(conn, slug, root=root)
        except Exception as exc:
            raise StoreError("backup_failed", "Pre-migration backup failed: %s" % exc)
    for version, sql in MIGRATIONS:
        if version > cur_v:
            next_ref_n = _next_ref_n(conn)
            script = ("BEGIN IMMEDIATE;\n" + _prepare_migration_sql(conn, version, sql)
                      + "\nINSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', '%d');\n"
                      % version
                      + "INSERT OR IGNORE INTO meta(key, value) VALUES('next_ref_n', '%d');\n"
                      % next_ref_n
                      + "COMMIT;")
            try:
                conn.executescript(script)
            except sqlite3.Error as exc:
                if conn.in_transaction:
                    conn.execute("ROLLBACK;")
                if version == 2 and "duplicate column" in str(exc).lower():
                    try:
                        latest = int(_get_meta(conn, "schema_version", "0"))
                    except (TypeError, ValueError):
                        latest = 0
                    if latest >= version:
                        continue
                raise
    return SCHEMA_VERSION


def db_seq(conn):
    try:
        row = conn.execute("SELECT MAX(seq) AS m FROM mutation").fetchone()
    except sqlite3.Error:
        return 0
    return int(row[0]) if row and row[0] is not None else 0


def backup_db(conn, slug, root=None):
    """Online backup into <root>/backups/<slug>-<UTC timestamp>.db, keep 14."""
    root = Path(root) if root is not None else state_root()
    dest_dir = root / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dest = dest_dir / ("%s-%s.db" % (slug, stamp))
    _owner_only(dest)
    target = sqlite3.connect(str(dest), timeout=5.0)
    try:
        conn.backup(target)
    finally:
        target.close()
    # Keep newest 14 for this slug.
    items = sorted(dest_dir.glob(slug + "-*.db"), key=lambda p: p.name)
    for old in items[:-14]:
        try:
            old.unlink()
        except OSError:
            pass
    return str(dest)


def maybe_daily_backup(conn, slug, root=None):
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    last = _get_meta(conn, "last_backup_date", None)
    if last == today:
        return None
    path = backup_db(conn, slug, root=root)
    try:
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('last_backup_date', ?)",
                     (today,))
        conn.commit()
    except sqlite3.Error:
        pass
    return path


EXPORT_TABLES = ("project", "task", "criterion", "task_dep", "grant_",
                 "attempt", "session", "job", "journal", "evidence", "mutation", "meta")


def export_db(conn, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = {}
    for table in EXPORT_TABLES:
        dest = out / (table + ".jsonl")
        try:
            rows = conn.execute('SELECT * FROM "%s"' % table).fetchall()
            cols = [d[0] for d in conn.execute('SELECT * FROM "%s" LIMIT 0' % table).description] \
                if True else []
        except sqlite3.Error:
            rows, cols = [], []
        with open(os.open(str(dest), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600),
                  "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps({c: r[c] for c in cols},
                                    ensure_ascii=False, sort_keys=True) + "\n")
        written[table] = str(dest)
    return written


def open_project_db(slug, root=None, create=True):
    root = Path(root) if root is not None else state_root()
    path = db_path_for_slug(slug, root=root)
    if not create and not path.exists():
        raise StoreError("project_not_found", "Unknown project: %s" % slug)
    conn = connect(path)
    ensure_schema(conn, slug=slug, root=root)
    return conn, path
