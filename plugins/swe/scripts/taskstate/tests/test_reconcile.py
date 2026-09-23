#!/usr/bin/env python3
"""Offline taskstate Phase 4b reconciliation tests."""
from __future__ import annotations

import argparse
import datetime
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

import facts
import reconcile
import store
import taskstate

FAKE_SLURM = """#!/usr/bin/env python3
import json
import os
import sys
with open(os.environ["TASKSTATE_SLURM_LOG"], "a", encoding="utf-8") as handle:
    handle.write("\\t".join(sys.argv) + "\\n")
command = os.path.basename(sys.argv[0])
job_id = sys.argv[sys.argv.index("-j") + 1]
outputs = json.loads(os.environ.get("TASKSTATE_FAKE_" + command.upper(), "{}"))
value = outputs.get(job_id, "")
if value == "EXIT1":
    sys.stderr.write("slurm_load_jobs error: Invalid job id specified\\n")
    sys.exit(1)
sys.stdout.write(value)
"""


class ReconcileTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.repo = self.root / "repo"
        self.bin_dir = self.root / "bin"
        self.empty_bin = self.root / "empty-bin"
        self.home.mkdir()
        self.repo.mkdir()
        self.bin_dir.mkdir()
        self.empty_bin.mkdir()
        self.old_cwd = Path.cwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, self.old_cwd)
        self.old_env = {key: os.environ.get(key) for key in (
            "TASKSTATE_HOME", "TASKSTATE_ACTOR", "TASKSTATE_LEASE_SECONDS",
            "TASKSTATE_SLURM_LOG", "TASKSTATE_FAKE_SQUEUE", "TASKSTATE_FAKE_SACCT",
            "CLAUDECODE", "PATH"
        )}
        self.old_slurm_ssh = {
            key: value for key, value in os.environ.items()
            if key.startswith("TASKSTATE_SLURM_SSH_")
        }
        self.addCleanup(self._restore_env)
        os.environ["TASKSTATE_HOME"] = str(self.home)
        os.environ["TASKSTATE_ACTOR"] = "test:reconcile"
        os.environ["TASKSTATE_LEASE_SECONDS"] = "7200"
        os.environ.pop("CLAUDECODE", None)
        for key in self.old_slurm_ssh:
            os.environ.pop(key, None)
        self.log = self.root / "slurm.log"
        os.environ["TASKSTATE_SLURM_LOG"] = str(self.log)
        os.environ["TASKSTATE_FAKE_SQUEUE"] = "{}"
        os.environ["TASKSTATE_FAKE_SACCT"] = "{}"
        for name in ("squeue", "sacct"):
            path = self.bin_dir / name
            path.write_text(FAKE_SLURM, encoding="utf-8")
            path.chmod(0o755)
        os.environ["PATH"] = str(self.bin_dir) + os.pathsep + self.old_env["PATH"]
        self.git("init", "-q")
        self.git("config", "user.email", "reconcile@example.invalid")
        self.git("config", "user.name", "Reconcile Test")
        (self.repo / "tracked.txt").write_text("initial\n", encoding="utf-8")
        self.git("add", "tracked.txt")
        self.git("commit", "-qm", "initial")
        self.project_number = 0

    def _restore_env(self):
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for key in list(os.environ):
            if key.startswith("TASKSTATE_SLURM_SSH_") and key not in self.old_slurm_ssh:
                os.environ.pop(key, None)
        for key, value in self.old_slurm_ssh.items():
            os.environ[key] = value

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, timeout=30)

    def call(self, argv, human=None):
        code, payload = taskstate.run(argv, human=human)
        self.assertEqual(code, 0, msg=json.dumps(payload, ensure_ascii=False))
        self.assertTrue(payload.get("ok"), msg=json.dumps(payload, ensure_ascii=False))
        return payload["result"]

    def new_task(self, claimed=False):
        self.project_number += 1
        slug = "p%d" % self.project_number
        self.call(["project", "init", "--slug", slug], human=True)
        task = self.call(["task", "add", "--project", slug, "--title", "Reconcile task"])
        result = {"slug": slug, "ref": task["ref"]}
        if claimed:
            result["claim"] = self.call(["claim", "--project", slug, task["ref"]])
        return result

    def args(self, command, sub=None, **values):
        return argparse.Namespace(cmd=command, sub=sub, **values)

    def dispatch(self, args, actor="test:reconcile", observed_at=None, host="test-host"):
        observed_at = observed_at or self.timestamp()
        conn, _path = store.open_project_db(args.project, root=self.home)
        try:
            return reconcile.dispatch(
                conn, args.project, args, actor, observed_at, facts.collect(str(self.repo)),
                host, False)
        finally:
            conn.close()

    def timestamp(self, seconds=0):
        value = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=seconds)
        return value.isoformat(timespec="microseconds")

    def set_fake(self, command, outputs):
        os.environ["TASKSTATE_FAKE_" + command.upper()] = json.dumps(outputs, sort_keys=True)

    def slurm_calls(self):
        if not self.log.exists():
            return []
        calls = []
        for line in self.log.read_text(encoding="utf-8").splitlines():
            argv = line.split("\t")
            self.assertIn(os.path.basename(argv[0]), {"squeue", "sacct"})
            calls.append(argv)
        return calls

    def job_state(self, slug, job_id):
        conn, _path = store.open_project_db(slug, root=self.home)
        try:
            row = conn.execute("SELECT * FROM job WHERE job_id=?", (job_id,)).fetchone()
            return dict(row) if row is not None else None
        finally:
            conn.close()

    def add_job(self, task, job_id, attempt=None, epoch=None, request_id=None, cluster="test"):
        args = self.args(
            "job", "add", project=task["slug"], cluster=cluster, job_id=job_id,
            task=task["ref"], attempt=attempt, epoch=epoch,
            request_id=request_id or str(uuid.uuid4()), observed_at=self.timestamp(),
            actor=None, json=False)
        return self.dispatch(args)

    def reconcile(self, slug, no_slurm=False, observed_at=None):
        args = self.args(
            "reconcile", project=slug, no_slurm=no_slurm,
            observed_at=observed_at or self.timestamp(), actor=None, json=False)
        return self.dispatch(args)

    def test_job_add_owner_late_validation_and_replay(self):
        task = self.new_task(claimed=True)
        claim = task["claim"]
        request_id = str(uuid.uuid4())
        first = self.add_job(task, "100", claim["attempt_id"], claim["epoch"], request_id)
        self.assertEqual(first["late"], 0)
        self.assertEqual(first["attempt_id"], claim["attempt_id"])
        replay = self.add_job(task, "100", claim["attempt_id"], claim["epoch"], request_id)
        self.assertEqual(first, replay)
        row = self.job_state(task["slug"], "100")
        self.assertEqual(row["attempt_id"], claim["attempt_id"])
        self.assertEqual(row["last_state"], None)
        conn, _path = store.open_project_db(task["slug"], root=self.home)
        try:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM mutation WHERE command='job.add' AND request_id=?",
                (request_id,)).fetchone()["n"]
            self.assertEqual(count, 1)
        finally:
            conn.close()

        late = self.add_job(task, "101", claim["attempt_id"], claim["epoch"] - 1)
        self.assertEqual(late["late"], 1)
        self.assertEqual(self.job_state(task["slug"], "101")["attempt_id"], claim["attempt_id"])
        cached_owner = self.add_job(task, "104")
        self.assertEqual(cached_owner["late"], 0)
        self.assertEqual(cached_owner["attempt_id"], claim["attempt_id"])

        ownerless = self.new_task()
        task_level = self.add_job(ownerless, "200")
        self.assertEqual(task_level["late"], 0)
        self.assertIsNone(self.job_state(ownerless["slug"], "200")["attempt_id"])
        unlinked = self.new_task()

        with self.assertRaises(taskstate.TaskStateError) as raised:
            self.add_job(task, "bad")
        self.assertEqual(raised.exception.code, "validation_failed")
        with self.assertRaises(taskstate.TaskStateError) as raised:
            self.add_job(task, "102", cluster="bad cluster")
        self.assertEqual(raised.exception.code, "validation_failed")
        args = self.args(
            "job", "add", project=unlinked["slug"], cluster="test", job_id="103",
            task=None, attempt=None, epoch=None, request_id=str(uuid.uuid4()),
            observed_at=self.timestamp(), actor=None, json=False)
        with self.assertRaises(taskstate.TaskStateError) as raised:
            self.dispatch(args)
        self.assertEqual(raised.exception.code, "validation_failed")

    def test_squeue_invalid_job_id_falls_through_to_sacct(self):
        task = self.new_task()
        self.add_job(task, "301")
        self.set_fake("squeue", {"301": "EXIT1"})
        self.set_fake("sacct", {"301": "COMPLETED|0:0\n"})
        result = self.reconcile(task["slug"], observed_at=self.timestamp(1))
        self.assertEqual(result["job_changes"][0]["classification"], "finished")
        self.assertEqual(result["unobservable"], [])
        self.assertTrue(any(item["type"] == "job_finished" for item in self.attention(task["slug"])))

    def test_running_to_completed_finished_attention_and_ack(self):
        task = self.new_task()
        self.add_job(task, "300")
        self.set_fake("squeue", {"300": "RUNNING\n"})
        self.set_fake("sacct", {"300": "COMPLETED|0:0\n"})
        running = self.reconcile(task["slug"], observed_at=self.timestamp(1))
        self.assertEqual(running["jobs_checked"], 1)
        self.assertEqual(running["job_changes"][0]["classification"], "nonterminal")
        row = self.job_state(task["slug"], "300")
        self.assertEqual(row["last_state"], "RUNNING")
        self.assertIsNone(row["exit_code"])
        self.assertFalse(any(item["type"] == "job_finished"
                             for item in self.attention(task["slug"])))

        self.set_fake("squeue", {})
        completed = self.reconcile(task["slug"], observed_at=self.timestamp(2))
        self.assertEqual(completed["job_changes"][0]["previous_state"], "RUNNING")
        self.assertEqual(completed["job_changes"][0]["state"], "COMPLETED")
        self.assertEqual(completed["job_changes"][0]["classification"], "finished")
        row = self.job_state(task["slug"], "300")
        self.assertEqual(row["last_state"], "COMPLETED")
        self.assertEqual(row["exit_code"], "0:0")
        items = self.attention(task["slug"])
        finished = [item for item in items if item["type"] == "job_finished"]
        self.assertEqual(len(finished), 1)
        self.assertEqual(finished[0]["ref"], task["ref"])
        calls_before = self.slurm_calls()
        self.assertEqual([os.path.basename(call[0]) for call in calls_before],
                         ["squeue", "squeue", "sacct"])
        self.assertEqual(calls_before[0][1:], ["-h", "-j", "300", "-o", "%T"])
        self.assertEqual(calls_before[2][1:], ["-n", "-X", "-P", "-j", "300", "-o", "State,ExitCode"])
        skipped = self.reconcile(task["slug"], observed_at=self.timestamp(3))
        self.assertEqual(skipped["jobs_checked"], 0)
        self.assertEqual(self.slurm_calls(), calls_before)

        ack = self.args(
            "job", "ack", project=task["slug"], cluster="test", job_id="300",
            request_id=str(uuid.uuid4()), observed_at=self.timestamp(4),
            actor=None, json=False)
        acked = self.dispatch(ack, actor="human:any")
        self.assertEqual(acked["acknowledged"], 1)
        items = self.attention(task["slug"])
        self.assertFalse(any(item["type"] == "job_finished" for item in items))

    def test_failed_timeout_and_cancelled_states_include_exit_codes(self):
        task = self.new_task()
        for job_id in ("401", "402", "403"):
            self.add_job(task, job_id)
        self.set_fake("squeue", {})
        self.set_fake("sacct", {
            "401": "FAILED|1:2\n",
            "402": "TIMEOUT|0:9\n",
            "403": "CANCELLED by 123|0:0\n"
        })
        result = self.reconcile(task["slug"])
        self.assertEqual(result["jobs_checked"], 3)
        self.assertEqual({row["job_id"] for row in result["job_changes"]},
                         {"401", "402", "403"})
        self.assertEqual(self.job_state(task["slug"], "401")["exit_code"], "1:2")
        self.assertEqual(self.job_state(task["slug"], "402")["exit_code"], "0:9")
        self.assertEqual(self.job_state(task["slug"], "403")["exit_code"], "0:0")
        items = self.attention(task["slug"])
        failed = [item for item in items if item["type"] == "job_failed"]
        self.assertEqual(len(failed), 3)
        self.assertTrue(any("exit_code 1:2" in item["detail"] for item in failed))
        self.assertTrue(any("CANCELLED by 123" in item["detail"] for item in failed))
        self.slurm_calls()

    def test_cluster_ssh_alias_uses_read_only_ssh_prefix(self):
        os.environ["TASKSTATE_SLURM_SSH_LOGIN_TEST"] = "cluster-login"
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="RUNNING\n", stderr="")
        with patch.object(reconcile.subprocess, "run", return_value=completed) as run:
            output = reconcile._run_slurm(
                ["squeue", "-h", "-j", "800", "-o", "%T"], "login.test")
        self.assertEqual(output, "RUNNING\n")
        invocation = run.call_args.args[0]
        self.assertEqual(invocation, [
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
            "cluster-login", "squeue", "-h", "-j", "800", "-o", "%T"
        ])
        self.assertEqual(run.call_args.kwargs["timeout"], 10)
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        with self.assertRaises(AssertionError):
            reconcile._run_slurm(["sbatch", "job.txt"], "login.test")
        os.environ["TASKSTATE_SLURM_SSH_LOGIN_TEST"] = "-oProxyCommand=unexpected"
        with self.assertRaises(taskstate.TaskStateError):
            reconcile._run_slurm(["squeue", "-h", "-j", "800", "-o", "%T"], "login.test")

    def test_older_observation_does_not_overwrite_newer_job_state(self):
        task = self.new_task()
        self.add_job(task, "801")
        self.set_fake("squeue", {"801": "RUNNING\n"})
        conn = self._connection(task["slug"])
        newer = self.timestamp(3)

        def observe_after_newer_write(cluster, job_id):
            conn.execute(
                "UPDATE job SET last_state='COMPLETED', last_state_at=?, exit_code='0:0', "
                "observed_at=? WHERE cluster=? AND job_id=?",
                (newer, newer, cluster, job_id))
            return {"state": "RUNNING", "exit_code": None, "category": "nonterminal"}

        try:
            with patch.object(reconcile, "_observe_job", side_effect=observe_after_newer_write):
                result = self.reconcile(
                    task["slug"], observed_at=self.timestamp(2))
        finally:
            conn.close()
        self.assertEqual(result["jobs_checked"], 1)
        self.assertEqual(result["job_changes"], [])
        row = self.job_state(task["slug"], "801")
        self.assertEqual(row["last_state"], "COMPLETED")
        self.assertEqual(row["exit_code"], "0:0")
        self.assertEqual(row["observed_at"], newer)

    def test_absent_from_squeue_and_sacct_is_missing(self):
        task = self.new_task()
        self.add_job(task, "500")
        self.set_fake("squeue", {})
        self.set_fake("sacct", {})
        result = self.reconcile(task["slug"])
        self.assertEqual(result["unobservable"], [])
        self.assertEqual(self.job_state(task["slug"], "500")["last_state"], "missing")
        items = self.attention(task["slug"])
        self.assertEqual([item["type"] for item in items], ["job_missing"])
        self.assertEqual([os.path.basename(call[0]) for call in self.slurm_calls()],
                         ["squeue", "sacct"])

    def test_no_squeue_and_no_ssh_is_unobservable_not_missing(self):
        task = self.new_task()
        self.add_job(task, "600")
        os.environ["PATH"] = str(self.empty_bin)
        for key in list(os.environ):
            if key.startswith("TASKSTATE_SLURM_SSH_"):
                os.environ.pop(key, None)
        result = self.reconcile(task["slug"])
        self.assertEqual(result["jobs_checked"], 1)
        self.assertEqual(result["unobservable"][0]["job_id"], "600")
        row = self.job_state(task["slug"], "600")
        self.assertEqual(row["last_state"], "unobservable")
        self.assertNotEqual(row["last_state"], "missing")
        items = self.attention(task["slug"])
        self.assertEqual([item["type"] for item in items], ["job_unobservable"])
        self.assertFalse(self.log.exists())

    def test_stale_session_is_inferred_but_owner_stays_claimed_until_release(self):
        task = self.new_task(claimed=True)
        claim = task["claim"]
        now = datetime.datetime.now(datetime.timezone.utc)
        last_seen = (now - datetime.timedelta(seconds=30)).isoformat(timespec="microseconds")
        lease = (now - datetime.timedelta(seconds=20)).isoformat(timespec="microseconds")
        conn = self._connection(task["slug"])
        try:
            conn.execute(
                "INSERT INTO session(runtime, session_id, attempt_id, task_id, host, cwd, source, "
                "started_at, last_seen_at, head, diff_hash, end_reason, end_observed, end_inferred) "
                "VALUES('claude','dead-session',?,?,?,?,?,?,?,NULL,NULL,NULL,0,0)",
                (claim["attempt_id"], self._task_id(conn, task["ref"]), "test-host",
                 str(self.repo), "startup", last_seen, last_seen))
            conn.execute("UPDATE task SET lease_expires_at=? WHERE ref=?", (lease, task["ref"]))
        finally:
            conn.close()
        os.environ["TASKSTATE_LEASE_SECONDS"] = "10"
        result = self.reconcile(task["slug"], no_slurm=True, observed_at=now.isoformat())
        self.assertEqual(result["sessions_orphaned"], 1)
        self.assertEqual([item["ref"] for item in result["stalled_tasks"]], [task["ref"]])
        conn = self._connection(task["slug"])
        try:
            session = conn.execute(
                "SELECT end_observed, end_inferred FROM session WHERE session_id='dead-session'"
            ).fetchone()
            owner = conn.execute("SELECT owner_attempt, lifecycle FROM task WHERE ref=?",
                                 (task["ref"],)).fetchone()
            self.assertEqual(session["end_observed"], 0)
            self.assertEqual(session["end_inferred"], 1)
            self.assertEqual(owner["owner_attempt"], claim["attempt_id"])
            self.assertEqual(owner["lifecycle"], "active")
        finally:
            conn.close()
        items = self.attention(task["slug"])
        orphaned = [item for item in items if item["type"] == "orphaned_session"]
        self.assertEqual(len(orphaned), 1)
        self.assertEqual(orphaned[0]["ref"], task["ref"])

        self.call(["release", "--project", task["slug"], "--task", task["ref"],
                   "--attempt", claim["attempt_id"], "--epoch", str(claim["epoch"])])
        items = self.attention(task["slug"])
        self.assertFalse(any(item["type"] == "orphaned_session" for item in items))
        conn = self._connection(task["slug"])
        try:
            owner = conn.execute("SELECT owner_attempt FROM task WHERE ref=?", (task["ref"],)).fetchone()
            self.assertIsNone(owner["owner_attempt"])
        finally:
            conn.close()

    def test_migration_three_upgrades_schema_two_with_pre_migration_backup(self):
        slug = "schema-two"
        path = self.home / (slug + ".db")
        conn = sqlite3.connect(str(path))
        try:
            conn.executescript(store.MIGRATION_1)
            conn.executescript(store.MIGRATION_2)
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', '2')")
            conn.commit()
        finally:
            conn.close()
        conn, _path = store.open_project_db(slug, root=self.home)
        try:
            version = conn.execute(
                "SELECT value FROM meta WHERE key='schema_version'").fetchone()["value"]
            self.assertEqual(version, str(store.SCHEMA_VERSION))
            session_columns = {row[1] for row in conn.execute("PRAGMA table_info(session)")}
            self.assertIn("end_inferred", session_columns)
            job_columns = {row[1] for row in conn.execute("PRAGMA table_info(job)")}
            self.assertTrue({
                "cluster", "job_id", "task_id", "attempt_id", "submitted_by", "host",
                "last_state", "last_state_at", "exit_code", "acknowledged", "observed_at",
                "recorded_at", "request_id"
            } <= job_columns)
            self.assertIn("job", store.EXPORT_TABLES)
        finally:
            conn.close()
        backups = list((self.home / "backups").glob(slug + "-*.db"))
        self.assertEqual(len(backups), 1)
        backup = sqlite3.connect(str(backups[0]))
        try:
            version = backup.execute(
                "SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
            self.assertEqual(version, "2")
            self.assertIsNone(backup.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='job'").fetchone())
        finally:
            backup.close()

    def test_no_slurm_never_invokes_fake_commands(self):
        task = self.new_task()
        self.add_job(task, "700")
        result = self.reconcile(task["slug"], no_slurm=True)
        self.assertEqual(result["jobs_checked"], 0)
        self.assertEqual(result["unobservable"], [])
        self.assertIsNone(self.job_state(task["slug"], "700")["last_state"])
        self.assertFalse(self.log.exists())

    def attention(self, slug):
        conn = self._connection(slug)
        try:
            return reconcile.attention_items(conn, slug)
        finally:
            conn.close()

    def _connection(self, slug):
        conn, _path = store.open_project_db(slug, root=self.home)
        return conn

    def _task_id(self, conn, ref):
        return conn.execute("SELECT task_id FROM task WHERE ref=?", (ref,)).fetchone()["task_id"]


if __name__ == "__main__":
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
        unittest.main(verbosity=2)
