#!/usr/bin/env python3
"""Offline home/satellite taskstate synchronization tests."""
from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
TASKSTATE = PKG / "taskstate.py"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

FAKE_SSH = r'''#!/usr/bin/env python3
import json
import os
import subprocess
import sys

if len(sys.argv) < 5 or sys.argv[4] != "rpc":
    sys.exit(2)
alias = sys.argv[1]
python = sys.argv[2]
script = sys.argv[3]
raw = sys.stdin.read()
env = os.environ.copy()
if alias == "satellite1":
    env["TASKSTATE_HOME"] = os.environ["TASKSTATE_SATELLITE_HOME"]
    env["TASKSTATE_REGISTRY"] = os.environ["TASKSTATE_SATELLITE_REGISTRY"]
    env.pop("TASKSTATE_SSH", None)
    if os.environ.get("TASKSTATE_FAKE_SSH_MODE") == "unreachable":
        sys.exit(255)
    if os.environ.get("TASKSTATE_FAKE_SSH_MODE") == "lose_push":
        try:
            request = json.loads(raw)
        except Exception:
            request = {}
        if request.get("op") == "push":
            result = subprocess.run([python, script, "rpc"], input=raw, text=True,
                                    env=env, capture_output=True)
            sys.exit(255)
    result = subprocess.run([python, script, "rpc"], input=raw, text=True,
                            env=env, capture_output=True)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    sys.exit(result.returncode)
sys.exit(255)
'''


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.satellite = self.root / "satellite"
        self.home.mkdir()
        self.satellite.mkdir()
        self.home_repo = self.root / "home-repo"
        self.satellite_repo = self.root / "satellite-repo"
        self.home_repo.mkdir()
        self.satellite_repo.mkdir()
        self.old_cwd = Path.cwd()
        self.old_env = {key: os.environ.get(key) for key in (
            "TASKSTATE_HOME", "TASKSTATE_REGISTRY", "TASKSTATE_SSH", "TASKSTATE_ACTOR",
            "TASKSTATE_LEASE_SECONDS", "CLAUDECODE", "TASKSTATE_FAKE_SSH_MODE",
            "TASKSTATE_SATELLITE_HOME", "TASKSTATE_SATELLITE_REGISTRY",
        )}
        self.addCleanup(self._restore)
        os.environ.pop("CLAUDECODE", None)
        os.environ["TASKSTATE_ACTOR"] = "test:sync"
        os.environ["TASKSTATE_LEASE_SECONDS"] = "7200"
        self._git(self.home_repo)
        self._git(self.satellite_repo)
        self.project = "agent-toolbox"
        self.home_registry = self.root / "home-registry.json"
        self.satellite_registry = self.root / "satellite-registry.json"
        self.fake_ssh = self.root / "fake-ssh"
        self.fake_ssh.write_text(FAKE_SSH, encoding="utf-8")
        self.fake_ssh.chmod(0o755)
        remote = "github.com/kpeez/agent-toolbox"
        self.home_registry.write_text(json.dumps({
            "self": "homehost",
            "hosts": {"satellite1": {"ssh": "satellite1", "python": sys.executable,
                                  "taskstate": str(TASKSTATE)}},
            "projects": {self.project: {"home": "homehost", "satellites": ["satellite1"],
                                        "repos": [remote]}},
        }), encoding="utf-8")
        self.satellite_registry.write_text(json.dumps({
            "self": "satellite1",
            "projects": {self.project: {"home": "homehost", "repos": [remote]}},
        }), encoding="utf-8")
        self.home_env = self._machine_env(self.home, self.home_registry)
        self.satellite_env = self._machine_env(self.satellite, self.satellite_registry)
        self.addCleanup(self.assert_invariant)

    def assert_invariant(self):
        for home_path in (self.home / (self.project + ".db"),):
            if not home_path.exists():
                continue
            home_conn = sqlite3.connect(str(home_path))
            home_conn.row_factory = sqlite3.Row
            try:
                home_rows = {row["ref"]: dict(row) for row in home_conn.execute("SELECT * FROM task")}
            finally:
                home_conn.close()
            satellite_path = self.satellite / (self.project + ".db")
            satellite_rows = {}
            if satellite_path.exists():
                satellite_conn = sqlite3.connect(str(satellite_path))
                satellite_conn.row_factory = sqlite3.Row
                try:
                    satellite_rows = {row["ref"]: dict(row) for row in satellite_conn.execute("SELECT * FROM task")}
                finally:
                    satellite_conn.close()
            for ref in set(home_rows) | set(satellite_rows):
                home_auth = ((home_rows.get(ref) or {}).get("authority_host") in (None, "homehost"))
                satellite_auth = ((satellite_rows.get(ref) or {}).get("authority_host") == "satellite1")
                self.assertFalse(home_auth and satellite_auth, ref)

    def _restore(self):
        os.chdir(self.old_cwd)
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _git(self, repo):
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "sync@example.invalid"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Sync Test"], cwd=repo, check=True)
        (repo / "tracked.txt").write_text("initial\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=repo, check=True)
        subprocess.run(["git", "remote", "add", "origin", "git@github.com:kpeez/agent-toolbox.git"],
                       cwd=repo, check=True)

    def _machine_env(self, home, registry):
        env = os.environ.copy()
        env["TASKSTATE_HOME"] = str(home)
        env["TASKSTATE_REGISTRY"] = str(registry)
        env["TASKSTATE_SSH"] = str(self.fake_ssh) if hasattr(self, "fake_ssh") else ""
        env["TASKSTATE_SATELLITE_HOME"] = str(self.satellite)
        env["TASKSTATE_SATELLITE_REGISTRY"] = str(self.satellite_registry) \
            if hasattr(self, "satellite_registry") else ""
        env.pop("TASKSTATE_FAKE_SSH_MODE", None)
        return env

    def call(self, machine, argv, human=None, env=None, timeout=30):
        if machine == "home":
            repo = self.home_repo
            base_env = self.home_env
        else:
            repo = self.satellite_repo
            base_env = self.satellite_env
        if env is not None:
            base_env = env
        if human is not None:
            base_env = base_env.copy()
            code = ("import json,sys;sys.path.insert(0,sys.argv[1]);import taskstate;"
                    "code,payload=taskstate.run(sys.argv[2:],human=True);"
                    "sys.stdout.write(json.dumps(payload));sys.exit(code)")
            command = [sys.executable, "-c", code, str(PKG)] + list(argv)
        else:
            command = [sys.executable, str(TASKSTATE)] + list(argv)
        result = subprocess.run(command, cwd=repo,
                                env=base_env, input="", text=True, capture_output=True,
                                timeout=timeout)
        self.assertTrue(result.stdout, msg=result.stderr)
        payload = json.loads(result.stdout)
        return result, payload

    def ok(self, machine, argv, human=None, env=None, timeout=30):
        result, payload = self.call(machine, argv, human=human, env=env, timeout=timeout)
        if human is None:
            self.assertEqual(result.returncode, 0, msg=json.dumps(payload))
            self.assertTrue(payload.get("ok"), msg=json.dumps(payload))
            return payload["result"]
        return payload

    def err(self, machine, argv, human=None, env=None):
        result, payload = self.call(machine, argv, human=human, env=env)
        self.assertNotEqual(result.returncode, 0, msg=json.dumps(payload))
        self.assertFalse(payload.get("ok"))
        return payload["error"]

    def init_home(self):
        return self.ok("home", ["project", "init", "--slug", self.project], human=True)

    def add_task(self, machine="home", title="Task", criteria=None):
        argv = ["task", "add", "--project", self.project, "--title", title]
        for item in criteria or []:
            argv += ["--criterion", item]
        return self.ok(machine, argv)

    def sync(self, machine="home", env=None, host=None):
        argv = ["sync"]
        if host:
            argv += ["--host", host]
        return self.ok(machine, argv, env=env)

    def task_row(self, machine, ref, project=None):
        home = self.home if machine == "home" else self.satellite
        conn = sqlite3.connect(str(home / ((project or self.project) + ".db")))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT * FROM task WHERE ref=?", (ref,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def count(self, machine, table, where="", params=()):
        home = self.home if machine == "home" else self.satellite
        conn = sqlite3.connect(str(home / (self.project + ".db")))
        try:
            sql = "SELECT COUNT(*) FROM " + table
            if where:
                sql += " WHERE " + where
            return conn.execute(sql, params).fetchone()[0]
        finally:
            conn.close()

    def test_no_registry_keeps_local_behavior(self):
        env = self.home_env.copy()
        env.pop("TASKSTATE_REGISTRY", None)
        self.ok("home", ["project", "init", "--slug", "local"], human=True, env=env)
        task = self.ok("home", ["task", "add", "--project", "local", "--title", "Local"], env=env)
        self.assertEqual(task["ref"], "local-1")
        self.ok("home", ["claim", "--project", "local", task["ref"]], env=env)
        self.assertEqual(self.task_row("home", task["ref"], project="local")["authority_host"], None)

    def test_delegate_claim_authority_and_satellite_race(self):
        self.init_home()
        first = self.add_task(title="delegated")
        second = self.add_task(title="home only")
        self.sync()
        self.ok("home", ["delegate", "--project", self.project, first["ref"], "--host", "satellite1"])
        error = self.err("home", ["claim", "--project", self.project, first["ref"]])
        self.assertEqual(error["code"], "not_authoritative")
        self.assertEqual(error["details"][0]["authority_host"], "satellite1")
        self.sync()
        self.assertEqual(self.task_row("satellite", first["ref"])["authority_host"], "satellite1")
        self.ok("satellite", ["claim", "--project", self.project, first["ref"]])
        error = self.err("satellite", ["claim", "--project", self.project, first["ref"]])
        self.assertEqual(error["code"], "already_claimed")
        error = self.err("satellite", ["claim", "--project", self.project, second["ref"]])
        self.assertEqual(error["code"], "not_authoritative")
        self.sync()
        home = self.task_row("home", first["ref"])
        sat = self.task_row("satellite", first["ref"])
        self.assertEqual(home["authority_host"], "satellite1")
        self.assertEqual(sat["authority_host"], "satellite1")
        self.assertIsNotNone(sat["owner_attempt"])
        self.assertIsNotNone(home["owner_attempt"])
        self.assertEqual(home["owner_attempt"], sat["owner_attempt"])

    def test_observations_merge_idempotently_and_journal_is_monotonic(self):
        self.init_home()
        task = self.add_task(criteria=["AC-1=works"])
        self.sync()
        home_question = self.ok("home", ["note", "--project", self.project, "--task", task["ref"],
                                         "--kind", "question", "--body", "home question"])
        self.sync()
        self.ok("satellite", ["note", "--project", self.project, "--task", task["ref"],
                              "--kind", "note", "--body", "sat resolves", "--resolves",
                              home_question["entry_id"]])
        self.sync()
        self.ok("home", ["delegate", "--project", self.project, task["ref"], "--host", "satellite1"])
        self.sync()
        claim = self.ok("satellite", ["claim", "--project", self.project, task["ref"]])
        owner = ["--task", task["ref"], "--attempt", claim["attempt_id"],
                 "--epoch", str(claim["epoch"])]
        self.ok("satellite", ["note", "--project", self.project, "--kind", "question",
                              "--body", "sat question"] + owner)
        self.ok("satellite", ["evidence", "--project", self.project, "--kind", "test",
                              "--result", "pass", "--criteria", "AC-1"] + owner)
        self.ok("satellite", ["job", "add", "--project", self.project, "--cluster", "test",
                              "--id", "123"] + owner)
        hook = subprocess.run(
            [sys.executable, str(PKG / "hooks.py"), "session-start", "--runtime", "claude"],
            cwd=self.satellite_repo, env=self.satellite_env,
            input=json.dumps({"session_id": "merge-session", "cwd": str(self.satellite_repo)}),
            text=True, capture_output=True, timeout=20)
        self.assertEqual(hook.returncode, 0, msg=hook.stderr)
        self.sync()
        first_counts = (self.count("home", "journal"), self.count("home", "evidence"),
                        self.count("home", "job"), self.count("home", "session"))
        self.sync()
        self.assertEqual(first_counts, (self.count("home", "journal"),
                                        self.count("home", "evidence"),
                                        self.count("home", "job"),
                                        self.count("home", "session")))
        conn = sqlite3.connect(str(self.home / (self.project + ".db")))
        try:
            self.assertEqual(conn.execute("SELECT origin_host FROM session").fetchone()[0], "satellite1")
        finally:
            conn.close()
        home_rows = sqlite3.connect(str(self.home / (self.project + ".db")))
        try:
            question = home_rows.execute("SELECT entry_id FROM journal WHERE body='sat question'").fetchone()[0]
        finally:
            home_rows.close()
        self.ok("home", ["note", "--project", self.project, "--task", task["ref"],
                         "--kind", "note", "--body", "resolve", "--resolves", question])
        self.sync()
        conn = sqlite3.connect(str(self.home / (self.project + ".db")))
        try:
            status = conn.execute("SELECT status FROM journal WHERE entry_id=?", (question,)).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(status, "resolved")

    def test_verify_auto_return_and_accept(self):
        self.init_home()
        task = self.add_task(criteria=["AC-1=works"])
        self.sync()
        self.ok("home", ["delegate", "--project", self.project, task["ref"], "--host", "satellite1"])
        self.sync()
        claim = self.ok("satellite", ["claim", "--project", self.project, task["ref"]])
        owner = ["--task", task["ref"], "--attempt", claim["attempt_id"],
                 "--epoch", str(claim["epoch"])]
        self.ok("satellite", ["evidence", "--project", self.project, "--kind", "test",
                              "--result", "pass", "--criteria", "AC-1"] + owner)
        self.ok("satellite", ["verify", "--project", self.project] + owner)
        self.sync()
        home = self.task_row("home", task["ref"])
        self.assertIsNone(home["authority_host"])
        self.assertEqual(home["lifecycle"], "verified")
        self.sync()
        self.assertIsNone(self.task_row("satellite", task["ref"])["authority_host"])
        self.ok("home", ["accept", "--project", self.project, task["ref"],
                         "--expect-version", str(home["version"])], human=True)

    def test_revoke_unclaimed_claimed_and_force(self):
        self.init_home()
        task = self.add_task()
        self.sync()
        self.ok("home", ["delegate", "--project", self.project, task["ref"], "--host", "satellite1"])
        self.sync()
        self.ok("home", ["revoke", "--project", self.project, task["ref"]])
        self.sync()
        self.assertIsNone(self.task_row("home", task["ref"])["authority_host"])
        self.assertEqual(self.task_row("satellite", task["ref"])["authority_host"], None)
        task2 = self.add_task(title="claimed revoke")
        self.sync()
        self.ok("home", ["delegate", "--project", self.project, task2["ref"], "--host", "satellite1"])
        self.sync()
        claim = self.ok("satellite", ["claim", "--project", self.project, task2["ref"]])
        self.ok("home", ["revoke", "--project", self.project, task2["ref"]])
        self.sync()
        row = self.task_row("home", task2["ref"])
        self.assertEqual(row["authority_host"], "satellite1")
        self.assertEqual(row["revoke_pending"], 1)
        attention = self.ok("home", ["attention", "--project", self.project])["items"]
        self.assertTrue(any(item["type"] == "revoke_blocked" for item in attention))
        self.ok("home", ["revoke", "--project", self.project, task2["ref"], "--force"], human=True)
        self.sync()
        self.assertIsNone(self.task_row("home", task2["ref"])["authority_host"])
        conn = sqlite3.connect(str(self.satellite / (self.project + ".db")))
        try:
            attempt = conn.execute("SELECT end FROM attempt WHERE attempt_id=?", (claim["attempt_id"],)).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(attempt, "superseded")
        old_owner = self.err("satellite", [
            "heartbeat", "--project", self.project, "--task", task2["ref"],
            "--attempt", claim["attempt_id"], "--epoch", str(claim["epoch"])])
        self.assertIn(old_owner["code"], {"not_authoritative", "stale_claim"})

    def test_push_with_stale_home_copy_never_erases_satellite_claim(self):
        # A satellite claim that lands after the home's last pull must survive
        # a revoke push built from the home's older copy.
        self.init_home()
        task = self.add_task(title="late claim")
        self.sync()
        self.ok("home", ["delegate", "--project", self.project, task["ref"], "--host", "satellite1"])
        self.sync()
        self.ok("home", ["revoke", "--project", self.project, task["ref"]])
        claim = self.ok("satellite", ["claim", "--project", self.project, task["ref"]])
        build = ("import json,sys;sys.path.insert(0,sys.argv[1]);import registry,store,sync;"
                 "conn,_=store.open_project_db(sys.argv[2]);"
                 "role=registry.project_role(sys.argv[2]);"
                 "print(json.dumps(sync.push_payload(conn,sys.argv[2],role,[])))")
        payload = subprocess.run([sys.executable, "-c", build, str(PKG), self.project],
                                 env=self.home_env, cwd=self.home_repo, text=True,
                                 capture_output=True, check=True).stdout
        result = subprocess.run([sys.executable, str(TASKSTATE), "rpc"], input=payload,
                                env=self.satellite_env, cwd=self.satellite_repo, text=True,
                                capture_output=True, timeout=30)
        response = json.loads(result.stdout)
        self.assertTrue(response.get("ok"), msg=result.stdout + result.stderr)
        self.assertIn(task["task_id"], response["result"]["blocked"])
        row = self.task_row("satellite", task["ref"])
        self.assertEqual(row["authority_host"], "satellite1")
        self.assertEqual(row["owner_attempt"], claim["attempt_id"])
        self.assertEqual(row["revoke_pending"], 1)
        self.ok("satellite", ["heartbeat", "--project", self.project, "--task", task["ref"],
                              "--attempt", claim["attempt_id"], "--epoch", str(claim["epoch"])])
        self.sync()
        self.assert_invariant()

    def test_delegate_all_open_skips_undelegable_tasks(self):
        self.init_home()
        first = self.add_task(title="already delegated")
        claimed = self.add_task(title="claimed at home")
        free = self.add_task(title="free")
        self.ok("home", ["delegate", "--project", self.project, first["ref"], "--host", "satellite1"])
        self.ok("home", ["claim", "--project", self.project, claimed["ref"]])
        result = self.ok("home", ["delegate", "--project", self.project, "--all-open", "--host", "satellite1"])
        self.assertEqual([item["ref"] for item in result["delegated"]], [free["ref"]])

    def test_satellite_one_off_ref_and_origin(self):
        self.init_home()
        self.sync()
        task = self.ok("satellite", ["claim", "--project", self.project, "--new", "one off"])
        self.assertEqual(task["ref"], self.project + "-satellite1-1")
        self.assertEqual(self.task_row("satellite", task["ref"])["origin_host"], "satellite1")
        self.sync()
        self.assertIsNotNone(self.task_row("home", task["ref"]))

    def test_unreachable_stale_and_crash_safety(self):
        self.init_home()
        task = self.add_task()
        self.sync()
        self.ok("home", ["delegate", "--project", self.project, task["ref"], "--host", "satellite1"])
        self.sync()
        claim = self.ok("satellite", ["claim", "--project", self.project, task["ref"]])
        owner = ["--task", task["ref"], "--attempt", claim["attempt_id"],
                 "--epoch", str(claim["epoch"])]
        self.ok("satellite", ["evidence", "--project", self.project, "--kind", "test",
                              "--result", "pass"] + owner)
        self.ok("satellite", ["verify", "--project", self.project] + owner)
        bad = self.home_env.copy()
        bad["TASKSTATE_FAKE_SSH_MODE"] = "unreachable"
        before = self.task_row("home", task["ref"])
        result = self.ok("home", ["sync", "--host", "satellite1"], env=bad)
        self.assertEqual(result["projects"][0]["hosts"][0]["code"], "unreachable")
        self.assertEqual(self.task_row("home", task["ref"])["authority_host"], before["authority_host"])
        stale_env = self.home_env.copy()
        stale_env["TASKSTATE_SYNC_STALE_SECONDS"] = "0"
        attention = self.ok("home", ["attention", "--project", self.project], env=stale_env)["items"]
        self.assertTrue(any(item["type"] == "satellite_stale" for item in attention))
        lost_env = self.home_env.copy()
        lost_env["TASKSTATE_FAKE_SSH_MODE"] = "lose_push"
        self.ok("home", ["sync", "--host", "satellite1"], env=lost_env)
        self.ok("home", ["sync", "--host", "satellite1"])
        self.assertIsNone(self.task_row("home", task["ref"])["authority_host"])
        self.assertEqual(self.count("home", "attempt", "task_id=(SELECT task_id FROM task WHERE ref=?)",
                                    (task["ref"],)), 1)

    def test_registry_resolution_and_rpc_validation(self):
        self.init_home()
        task = self.add_task()
        result = subprocess.run([sys.executable, str(TASKSTATE), "task", "show", task["ref"]],
                                cwd=self.home_repo, env=self.home_env, text=True,
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])
        bad = self.root / "bad-registry.json"
        bad.write_text("{", encoding="utf-8")
        bad_env = self.home_env.copy()
        bad_env["TASKSTATE_REGISTRY"] = str(bad)
        error = self.err("home", ["task", "show", "--project", self.project, task["ref"]], env=bad_env)
        self.assertEqual(error["code"], "registry_invalid")
        request = {"v": 1, "op": "ping", "project": self.project, "from_home": "homehost"}
        ping = subprocess.run([sys.executable, str(TASKSTATE), "rpc"], input=json.dumps(request),
                              cwd=self.satellite_repo, env=self.satellite_env, text=True,
                              capture_output=True, timeout=20)
        self.assertEqual(ping.returncode, 0, msg=ping.stderr)
        self.assertTrue(json.loads(ping.stdout)["ok"])
        request["from_home"] = "wrong-home"
        denied = subprocess.run([sys.executable, str(TASKSTATE), "rpc"], input=json.dumps(request),
                                cwd=self.satellite_repo, env=self.satellite_env, text=True,
                                capture_output=True, timeout=20)
        self.assertEqual(denied.returncode, 2)
        self.assertEqual(json.loads(denied.stdout)["error"]["code"], "forbidden_home")
        request["from_home"] = "homehost"
        request["op"] = "delete"
        invalid = subprocess.run([sys.executable, str(TASKSTATE), "rpc"], input=json.dumps(request),
                                 cwd=self.satellite_repo, env=self.satellite_env, text=True,
                                 capture_output=True, timeout=20)
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(json.loads(invalid.stdout)["error"]["code"], "validation_failed")
        self.assertNotIn("Traceback", invalid.stderr + invalid.stdout)
        self.sync()
        home_only = self.call("satellite", [
            "task", "hold", "--project", self.project, task["ref"],
            "--reason", "no", "--expect-version", "1"], human=True)[1]
        self.assertEqual(home_only["error"]["code"], "home_only")

    def test_rpc_freshness_and_hook_pointer(self):
        self.init_home()
        task = self.add_task(criteria=["AC-1=works"])
        self.sync()
        self.ok("home", ["delegate", "--project", self.project, task["ref"], "--host", "satellite1"])
        self.sync()
        context = self.ok("satellite", ["context", "--project", self.project, task["ref"]])
        self.assertIn("home copy as of", context["sync"]["label"])
        self.assertIn("last_sync_at", context["sync"])
        self.ok("satellite", ["claim", "--project", self.project, task["ref"]])
        hook_env = self.satellite_env.copy()
        hook = subprocess.run([sys.executable, str(PKG / "hooks.py"), "session-start", "--runtime", "claude"],
                              cwd=self.satellite_repo, env=hook_env,
                              input=json.dumps({"session_id": "sync-hook", "cwd": str(self.satellite_repo)}),
                              text=True, capture_output=True, timeout=20)
        self.assertEqual(hook.returncode, 0, msg=hook.stderr)
        payload = json.loads(hook.stdout)
        text = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("home copy as of", text)
        self.assertIn(str(TASKSTATE), text)
        self.assertIn("python3", text)


if __name__ == "__main__":
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
        unittest.main(verbosity=2)
