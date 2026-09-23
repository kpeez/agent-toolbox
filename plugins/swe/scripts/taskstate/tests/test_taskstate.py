#!/usr/bin/env python3
"""Offline taskstate Phase 1 tests. Run directly; temp dirs only, no network."""
import json
import multiprocessing
import os
import random
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
if PKG not in sys.path:
    sys.path.insert(0, PKG)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import taskstate
import store as store_mod


def _claim_worker(payload):
    home, slug, ref = payload
    import os as _os
    import sys as _sys
    _os.environ["TASKSTATE_HOME"] = home
    pkg = os.path.dirname(os.path.abspath(__file__))
    # When spawned, __file__ is this test file; package dir is its parent.
    parent = os.path.dirname(pkg) if os.path.basename(pkg) == "tests" else pkg
    for p in (parent, pkg):
        if p not in _sys.path:
            _sys.path.insert(0, p)
    import taskstate as _ts
    code, out = _ts.run(["claim", "--project", slug, ref], human=None)
    err = (out.get("error") or {}).get("code") if isinstance(out, dict) else None
    return (code, bool(out.get("ok")) if isinstance(out, dict) else False, err)


class TaskStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = os.path.join(self.tmp.name, "home")
        os.makedirs(self.home, exist_ok=True)
        os.environ["TASKSTATE_HOME"] = self.home
        os.environ["TASKSTATE_ACTOR"] = "test:session"
        os.environ.pop("CLAUDECODE", None)
        self._old_lease = os.environ.get("TASKSTATE_LEASE_SECONDS")
        os.environ["TASKSTATE_LEASE_SECONDS"] = "7200"
        self.repo = os.path.join(self.tmp.name, "repo")
        os.makedirs(self.repo, exist_ok=True)
        self._git("init", "-q")
        self._git("config", "user.email", "t@t.t")
        self._git("config", "user.name", "t")
        Path(self.repo, "f.txt").write_text("one\n")
        self._git("add", "f.txt")
        self._git("commit", "-qm", "init")
        self._old_cwd = os.getcwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, self._old_cwd)
        self.addCleanup(self._restore_env)
        self.slug_n = 0

    def _restore_env(self):
        if self._old_lease is None:
            os.environ.pop("TASKSTATE_LEASE_SECONDS", None)
        else:
            os.environ["TASKSTATE_LEASE_SECONDS"] = self._old_lease

    def _git(self, *args):
        subprocess.run(["git"] + list(args), cwd=self.repo, check=True,
                       capture_output=True, timeout=30)

    def tcall(self, argv, human=None):
        return taskstate.run(argv, human=human)

    def ok(self, argv, human=None):
        code, out = self.tcall(argv, human=human)
        self.assertEqual(code, 0, msg=json.dumps(out)[:2000])
        self.assertTrue(out.get("ok"), msg=json.dumps(out)[:2000])
        self.assertIn("db_seq", out)
        return out["result"]

    def err(self, argv, human=None):
        code, out = self.tcall(argv, human=human)
        self.assertEqual(code, 2, msg=json.dumps(out)[:2000])
        self.assertFalse(out.get("ok"))
        return out["error"]

    def new_project(self, slug=None, disclosure="internal"):
        if slug is None:
            self.slug_n += 1
            slug = "p%d" % self.slug_n
        res = self.ok(["project", "init", "--slug", slug, "--disclosure", disclosure], human=True)
        self.assertEqual(res["project"]["slug"], slug)
        return slug

    def add_task(self, slug, title="T", criteria=None, depends=None, kind="code", spec_id=None):
        argv = ["task", "add", "--project", slug, "--title", title, "--kind", kind]
        for c in (criteria or []):
            argv += ["--criterion", c]
        for d in (depends or []):
            argv += ["--depends-on", d]
        if spec_id:
            argv += ["--spec-id", spec_id]
        return self.ok(argv)

    # 1. concurrent claim
    def test_1_concurrent_claim(self):
        slug = self.new_project()
        t = self.add_task(slug, "Race")
        ref = t["ref"]
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(8) as pool:
            results = pool.map(_claim_worker, [(self.home, slug, ref)] * 8)
        oks = [r for r in results if r[1]]
        errs = [r for r in results if not r[1]]
        self.assertEqual(len(oks), 1, msg=str(results))
        self.assertEqual(len(errs), 7, msg=str(results))
        for code, okv, err in errs:
            self.assertEqual(code, 2)
            self.assertEqual(err, "already_claimed")
        code, out = self.tcall(["task", "show", "--project", slug, ref])
        self.assertTrue(out["ok"])
        self.assertEqual(out["result"]["task"]["claim_epoch"], 1)

    # 2. takeover then old-epoch writes
    def test_2_takeover_old_epoch(self):
        os.environ["TASKSTATE_LEASE_SECONDS"] = "7200"
        slug = self.new_project()
        ref = self.add_task(slug, "Take")["ref"]
        c1 = self.ok(["claim", "--project", slug, ref])
        a1, e1 = c1["attempt_id"], c1["epoch"]
        q = self.ok(["note", "--project", slug, "--task", ref, "--attempt", a1, "--epoch", str(e1),
                     "--kind", "question", "--body", "Q1"])
        to = self.ok(["takeover", "--project", slug, ref, "--reason", "stale owner", "--force"], human=True)
        self.assertEqual(to["epoch"], e1 + 1)
        a2 = to["attempt_id"]
        e = self.err(["release", "--project", slug, "--task", ref, "--attempt", a1,
                      "--epoch", str(e1)])
        self.assertEqual(e["code"], "stale_claim")
        e = self.err(["verify", "--project", slug, "--task", ref, "--attempt", a1,
                      "--epoch", str(e1)])
        self.assertEqual(e["code"], "stale_claim")
        rid = str(uuid.uuid4())
        res = self.ok(["note", "--project", slug, "--task", ref, "--attempt", a1, "--epoch", str(e1),
                       "--kind", "note", "--body", "late write", "--resolves", q["entry_id"],
                       "--request-id", rid])
        self.assertEqual(res["late"], 1)
        # question still open
        conn, _ = store_mod.open_project_db(slug, root=Path(self.home))
        try:
            row = conn.execute("SELECT status FROM journal WHERE entry_id=?",
                               (q["entry_id"],)).fetchone()
            self.assertEqual(row["status"], "open")
        finally:
            conn.close()
        # new owner still works
        hb = self.ok(["heartbeat", "--project", slug, "--task", ref, "--attempt", a2,
                      "--epoch", str(to["epoch"])])
        self.assertIn("lease_expires_at", hb)

    # 3. idempotency + replay
    def test_3_idempotency_replay(self):
        slug = self.new_project()
        ref = self.add_task(slug, "Idem")["ref"]
        rid = str(uuid.uuid4())
        obs = "2026-01-01T00:00:00+00:00"
        base = ["note", "--project", slug, "--task", ref, "--kind", "note", "--body", "same",
                "--observed-at", obs, "--request-id", rid]
        r1 = self.ok(base)
        r2 = self.ok(base)
        self.assertEqual(r1, r2)
        e = self.err(["note", "--project", slug, "--task", ref, "--kind", "note",
                      "--body", "different", "--observed-at", obs, "--request-id", rid])
        self.assertEqual(e["code"], "request_conflict")
        # shuffled/duplicated replay with fixed seeds
        ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, "n%d" % i)) for i in range(6)]
        cmds = [["note", "--project", slug, "--task", ref, "--kind", "note",
                 "--body", "body-%d" % i, "--observed-at", obs, "--request-id", ids[i]]
                for i in range(6)]
        stream = cmds + list(cmds)
        rnd = random.Random(0)
        rnd.shuffle(stream)
        for c in stream:
            self.ok(c)
        conn, _ = store_mod.open_project_db(slug, root=Path(self.home))
        try:
            n = conn.execute("SELECT COUNT(*) AS n FROM journal WHERE task_id IN "
                             "(SELECT task_id FROM task WHERE ref=?)", (ref,)).fetchone()["n"]
        finally:
            conn.close()
        self.assertEqual(n, 1 + 6)  # first note + six replayed

    # 4. evidence staleness
    def test_4_evidence_staleness(self):
        slug = self.new_project()
        ref = self.add_task(slug, "Stale", criteria=["AC-1=works"])["ref"]
        c = self.ok(["claim", "--project", slug, ref])
        a, e = c["attempt_id"], c["epoch"]
        self.ok(["evidence", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(e),
                 "--kind", "test", "--result", "pass", "--criteria", "AC-1", "--command", "run.sh"])
        Path(self.repo, "f.txt").write_text("two\n")
        self._git("add", "f.txt")
        self._git("commit", "-qm", "change")
        err = self.err(["verify", "--project", slug, "--task", ref, "--attempt", a,
                        "--epoch", str(e)])
        self.assertEqual(err["code"], "verification_incomplete")
        self.assertTrue(any(g.get("gap") == "stale" for g in err.get("details", [])))
        # heartbeat picks up new facts; still stale until new evidence
        self.ok(["heartbeat", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(e)])
        self.ok(["evidence", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(e),
                 "--kind", "test", "--result", "pass", "--criteria", "AC-1", "--command", "run.sh"])
        v = self.ok(["verify", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(e)])
        self.assertEqual(v["lifecycle"], "verified")

    # 5. verify gating
    def test_5_verify_gating(self):
        slug = self.new_project()
        ref = self.add_task(slug, "Gate", criteria=["AC-1=a", "AC-2=b"])["ref"]
        c = self.ok(["claim", "--project", slug, ref])
        a, e = c["attempt_id"], c["epoch"]
        self.ok(["evidence", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(e),
                 "--kind", "test", "--result", "unavailable", "--criteria", "AC-1"])
        self.ok(["evidence", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(e),
                 "--kind", "test", "--result", "pass", "--criteria", "AC-2"])
        err = self.err(["verify", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(e)])
        self.assertEqual(err["code"], "verification_incomplete")
        gaps = {g["ac_id"]: g["gap"] for g in err.get("details", [])}
        self.assertEqual(gaps.get("AC-1"), "unavailable")
        self.ok(["evidence", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(e),
                 "--kind", "test", "--result", "inconclusive", "--criteria", "AC-1"])
        err = self.err(["verify", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(e)])
        gaps = {g["ac_id"]: g["gap"] for g in err.get("details", [])}
        self.assertEqual(gaps.get("AC-1"), "inconclusive")
        self.ok(["evidence", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(e),
                 "--kind", "test", "--result", "pass", "--criteria", "AC-1"])
        v = self.ok(["verify", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(e)])
        self.assertEqual(v["lifecycle"], "verified")

    # 6. human-only + stale version
    def test_6_human_only_and_versions(self):
        slug = self.new_project()
        e = self.err(["project", "init", "--slug", "nope"])
        self.assertEqual(e["code"], "human_only")
        ref = self.add_task(slug, "H")["ref"]
        code, out = self.tcall(["task", "show", "--project", slug, ref])
        ver = out["result"]["task"]["version"]
        e = self.err(["task", "hold", "--project", slug, ref, "--reason", "x",
                      "--expect-version", str(ver)])
        self.assertEqual(e["code"], "human_only")
        e = self.err(["grant", "add", "--project", slug, "--kind", "execute",
                      "--scope-project", "--source", "s"])
        self.assertEqual(e["code"], "human_only")
        # accept path: claim -> evidence -> verify -> accept stale
        c = self.ok(["claim", "--project", slug, ref])
        a, ep = c["attempt_id"], c["epoch"]
        self.ok(["evidence", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(ep),
                 "--kind", "test", "--result", "pass"])
        self.ok(["verify", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(ep)])
        code, out = self.tcall(["task", "show", "--project", slug, ref])
        ver2 = out["result"]["task"]["version"]
        e = self.err(["accept", "--project", slug, ref, "--expect-version", str(ver2 - 1)], human=True)
        self.assertEqual(e["code"], "stale_version")
        acc = self.ok(["accept", "--project", slug, ref, "--expect-version", str(ver2)], human=True)
        self.assertEqual(acc["lifecycle"], "accepted")

    # 7. deps/readiness/cycles/hold/grants
    def test_7_deps_hold_grants(self):
        slug = self.new_project()
        a = self.add_task(slug, "A")["ref"]
        b = self.add_task(slug, "B", depends=[a])["ref"]
        e = self.err(["claim", "--project", slug, b])
        self.assertEqual(e["code"], "blocked")
        e = self.err(["task", "add", "--project", slug, "--title", "X", "--depends-on", "nope-99"])
        self.assertEqual(e["code"], "unknown_dependency")
        # cycle logic at store level: A <- B exists, so A depending on B is a cycle
        conn, _ = store_mod.open_project_db(slug, root=Path(self.home))
        try:
            aid = conn.execute("SELECT task_id FROM task WHERE ref=?", (a,)).fetchone()["task_id"]
            bid = conn.execute("SELECT task_id FROM task WHERE ref=?", (b,)).fetchone()["task_id"]
            with self.assertRaises(taskstate.TaskStateError) as cm:
                taskstate.check_cycle(conn, aid, [bid])
            self.assertEqual(cm.exception.code, "dependency_cycle")
            with self.assertRaises(taskstate.TaskStateError) as cm2:
                taskstate.check_cycle(conn, aid, [aid])
            self.assertEqual(cm2.exception.code, "dependency_cycle")
        finally:
            conn.close()
        # hold blocks claim
        code, out = self.tcall(["task", "show", "--project", slug, a])
        ver = out["result"]["task"]["version"]
        self.ok(["task", "hold", "--project", slug, a, "--reason", "wait",
                 "--expect-version", str(ver)], human=True)
        e = self.err(["claim", "--project", slug, a])
        self.assertEqual(e["code"], "on_hold")
        code, out = self.tcall(["task", "show", "--project", slug, a])
        self.ok(["task", "unhold", "--project", slug, a,
                 "--expect-version", str(out["result"]["task"]["version"])], human=True)
        # spec-linked needs grant
        spec = str(uuid.uuid4())
        s = self.add_task(slug, "S", spec_id=spec)["ref"]
        e = self.err(["claim", "--project", slug, s])
        self.assertEqual(e["code"], "not_authorized")
        self.ok(["grant", "add", "--project", slug, "--kind", "execute",
                 "--task", s, "--source", "user-ok"], human=True)
        c = self.ok(["claim", "--project", slug, s])
        self.assertIn("attempt_id", c)

    # 8. context + attention
    def test_8_context_attention(self):
        slug = self.new_project()
        long_body = "L" * 5000 + "\nline2\nline3"
        uni = "héllo wörld 🌟\nline-α\nline-β"
        ref = self.add_task(slug, "Ctx", criteria=["AC-1=x"])["ref"]
        c = self.ok(["claim", "--project", slug, ref])
        a, e = c["attempt_id"], c["epoch"]
        self.ok(["note", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(e),
                 "--kind", "decision", "--body", long_body])
        self.ok(["note", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(e),
                 "--kind", "finding", "--body", "plain finding"])
        self.ok(["note", "--project", slug, "--task", ref, "--attempt", a, "--epoch", str(e),
                 "--kind", "question", "--body", "open?\n" + uni])
        code, out = self.tcall(["context", "--project", slug, ref])
        self.assertEqual(code, 0)
        ctx = out["result"]
        self.assertEqual(ctx["contract_version"], 1)
        blob = json.dumps(ctx, ensure_ascii=False)
        self.assertIn("…[truncated", blob)
        self.assertIn("🌟", blob)
        # attention: stalled via zero lease
        os.environ["TASKSTATE_LEASE_SECONDS"] = "0"
        s2 = self.new_project(slug="stallp")
        r2 = self.add_task(s2, "S")["ref"]
        self.ok(["claim", "--project", s2, r2])
        code, out = self.tcall(["attention", "--project", s2])
        types = [i["type"] for i in out["result"]["items"]]
        self.assertIn("stalled", types)
        code, out = self.tcall(["attention", "--project", slug])
        types = [i["type"] for i in out["result"]["items"]]
        self.assertIn("open_question", types)
        os.environ["TASKSTATE_LEASE_SECONDS"] = "7200"
        # verified awaiting acceptance + stale evidence
        s3 = self.new_project(slug="verp")
        r3 = self.add_task(s3, "V", criteria=["AC-1=y"])["ref"]
        cc = self.ok(["claim", "--project", s3, r3])
        self.ok(["evidence", "--project", s3, "--task", r3, "--attempt", cc["attempt_id"],
                 "--epoch", str(cc["epoch"]), "--kind", "test", "--result", "pass",
                 "--criteria", "AC-1"])
        self.ok(["verify", "--project", s3, "--task", r3, "--attempt", cc["attempt_id"],
                 "--epoch", str(cc["epoch"])])
        code, out = self.tcall(["attention", "--project", s3])
        types = [i["type"] for i in out["result"]["items"]]
        self.assertIn("verified_awaiting_acceptance", types)
        Path(self.repo, "f.txt").write_text("changed\n")
        self._git("add", "f.txt")
        self._git("commit", "-qm", "move head")
        # touch: new claim cycle to refresh facts? attention stale check uses last attempt inputs
        code, out = self.tcall(["attention", "--project", s3])
        types = [i["type"] for i in out["result"]["items"]]
        self.assertIn("stale_evidence", types)
        self.assertIn("verified_awaiting_acceptance", types)

    def test_heartbeat_does_not_invalidate_expect_version(self):
        slug = self.new_project()
        ref = self.add_task(slug, "HB")["ref"]
        c = self.ok(["claim", "--project", slug, ref])
        code, out = self.tcall(["task", "show", "--project", slug, ref])
        ver = out["result"]["task"]["version"]
        self.ok(["heartbeat", "--project", slug, "--task", ref, "--attempt", c["attempt_id"],
                 "--epoch", str(c["epoch"])])
        self.ok(["task", "hold", "--project", slug, ref, "--reason", "pause",
                 "--expect-version", str(ver)], human=True)

    # 9. backup/export/migration
    def test_9_backup_export_migration(self):
        slug = self.new_project()
        self.add_task(slug, "B")
        res = self.ok(["backup", "--project", slug])
        self.assertTrue(res["backups"])
        for p in res["backups"]:
            self.assertTrue(os.path.isfile(p))
            conn = sqlite3.connect(p)
            try:
                rows = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchall()
                self.assertTrue(rows)
            finally:
                conn.close()
        outdir = os.path.join(self.tmp.name, "exp")
        res = self.ok(["export", "--project", slug, "--out", outdir])
        for table, path in res["files"].items():
            self.assertTrue(os.path.isfile(path), msg=table)
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        json.loads(line)
        conn, _ = store_mod.open_project_db(slug, root=Path(self.home))
        try:
            row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            self.assertEqual(row["value"], str(store_mod.SCHEMA_VERSION))
        finally:
            conn.close()

    # F1. subdir facts use worktree top
    def test_F1_subdir_facts(self):
        import facts as facts_mod
        sub = os.path.join(self.repo, "sub")
        os.makedirs(sub, exist_ok=True)
        Path(self.repo, "sub", "keep.txt").write_text("k\n")
        a = facts_mod.collect(cwd=sub)
        b = facts_mod.collect(cwd=self.repo)
        self.assertEqual(a["worktree"], b["worktree"])
        self.assertEqual(a["diff_hash"], b["diff_hash"])
        self.assertEqual(a["head"], b["head"])
        Path(self.repo, "outside.txt").write_text("outside\n")
        c = facts_mod.collect(cwd=sub)
        self.assertNotEqual(c["diff_hash"], b["diff_hash"])
        # evidence from subdir verifies from root
        slug = self.new_project()
        ref = self.add_task(slug, "F1")["ref"]
        cc = self.ok(["claim", "--project", slug, ref])
        a_id, ep = cc["attempt_id"], cc["epoch"]
        os.chdir(sub)
        try:
            self.ok(["evidence", "--project", slug, "--task", ref, "--attempt", a_id,
                     "--epoch", str(ep), "--kind", "test", "--result", "pass"])
        finally:
            os.chdir(self.repo)
        # remove untracked file created above so verify baseline is clean
        try:
            os.unlink(os.path.join(self.repo, "outside.txt"))
        except OSError:
            pass
        # need fresh evidence after cleanup (diff changed); record again from root
        self.ok(["evidence", "--project", slug, "--task", ref, "--attempt", a_id,
                 "--epoch", str(ep), "--kind", "test", "--result", "pass"])
        v = self.ok(["verify", "--project", slug, "--task", ref, "--attempt", a_id,
                     "--epoch", str(ep)])
        self.assertEqual(v["lifecycle"], "verified")

    # F2. unknown freshness + owned stale without heartbeat
    def test_F2_unknown_and_owned_stale(self):
        # non-git verify
        outside = os.path.join(self.tmp.name, "plain")
        os.makedirs(outside, exist_ok=True)
        os.chdir(outside)
        try:
            slug = self.new_project(slug="nongitp")
            ref = self.add_task(slug, "NG")["ref"]
            cc = self.ok(["claim", "--project", slug, ref])
            a_id, ep = cc["attempt_id"], cc["epoch"]
            self.ok(["evidence", "--project", slug, "--task", ref, "--attempt", a_id,
                     "--epoch", str(ep), "--kind", "test", "--result", "pass"])
            v = self.ok(["verify", "--project", slug, "--task", ref, "--attempt", a_id,
                         "--epoch", str(ep)])
            self.assertEqual(v["lifecycle"], "verified")
            self.assertIn("freshness_unknown", v)
            self.assertEqual(v["freshness_unknown"], ["task"])
        finally:
            os.chdir(self.repo)
        # owned task show reflects new commit as stale without heartbeat
        slug2 = self.new_project(slug="ownstale")
        ref2 = self.add_task(slug2, "OS", criteria=["AC-1=x"])["ref"]
        cc2 = self.ok(["claim", "--project", slug2, ref2])
        a2, e2 = cc2["attempt_id"], cc2["epoch"]
        self.ok(["evidence", "--project", slug2, "--task", ref2, "--attempt", a2,
                 "--epoch", str(e2), "--kind", "test", "--result", "pass",
                 "--criteria", "AC-1"])
        Path(self.repo, "f.txt").write_text("moved\n")
        self._git("add", "f.txt")
        self._git("commit", "-qm", "move")
        code, out = self.tcall(["task", "show", "--project", slug2, ref2])
        self.assertTrue(out["ok"])
        ev = out["result"]["derived"]["evidence"]
        self.assertEqual(ev[0]["freshness"], "stale")

    # F3. time comparison uses parsed datetimes + microseconds
    def test_F3_time_parse(self):
        import taskstate as ts_mod
        slug = self.new_project(slug="timep")
        ref = self.add_task(slug, "TM")["ref"]
        cc = self.ok(["claim", "--project", slug, ref])
        a_id = cc["attempt_id"]
        conn, _ = store_mod.open_project_db(slug, root=Path(self.home))
        try:
            conn.execute("UPDATE attempt SET last_head='h1', facts_observed_at='2026-01-01T00:30:00Z' "
                         "WHERE attempt_id=?", (a_id,))
            conn.commit()
            ts_mod.update_attempt_facts(conn, a_id, {"head": "h2", "diff_hash": "d2",
                                        "branch": "b", "worktree": "w"},
                                        "2026-01-01T01:00:00+01:00")
            conn.commit()
            row = conn.execute("SELECT last_head, facts_observed_at FROM attempt WHERE attempt_id=?",
                               (a_id,)).fetchone()
            self.assertEqual(row["last_head"], "h1")
            ts_mod.update_attempt_facts(conn, a_id, {"head": "h3", "diff_hash": "d3",
                                        "branch": "b", "worktree": "w"},
                                        "2026-01-01T02:00:00Z")
            conn.commit()
            row = conn.execute("SELECT last_head, facts_observed_at FROM attempt WHERE attempt_id=?",
                               (a_id,)).fetchone()
            self.assertEqual(row["last_head"], "h3")
            self.assertIn(".", row["facts_observed_at"])
            # now_iso has microseconds
            self.assertIn(".", ts_mod.now_iso())
            import domain as dmod
            self.assertIn(".", dmod.now_iso())
        finally:
            conn.close()

    # F4. attempt-less writes are late=0 and count
    def test_F4_attemptless(self):
        slug = self.new_project(slug="latep")
        ref = self.add_task(slug, "L")["ref"]
        cc = self.ok(["claim", "--project", slug, ref])
        a_id, ep = cc["attempt_id"], cc["epoch"]
        q = self.ok(["note", "--project", slug, "--task", ref, "--attempt", a_id,
                     "--epoch", str(ep), "--kind", "question", "--body", "Q?"])
        # human note without attempt resolves
        r = self.ok(["note", "--project", slug, "--task", ref, "--kind", "note",
                     "--body", "human resolves", "--resolves", q["entry_id"]])
        self.assertEqual(r["late"], 0)
        conn, _ = store_mod.open_project_db(slug, root=Path(self.home))
        try:
            row = conn.execute("SELECT status FROM journal WHERE entry_id=?",
                               (q["entry_id"],)).fetchone()
            self.assertEqual(row["status"], "resolved")
        finally:
            conn.close()
        # manual evidence without attempt counts toward verify
        e = self.ok(["evidence", "--project", slug, "--task", ref, "--kind", "manual",
                     "--result", "pass"])
        self.assertEqual(e["late"], 0)
        v = self.ok(["verify", "--project", slug, "--task", ref, "--attempt", a_id,
                     "--epoch", str(ep)])
        self.assertEqual(v["lifecycle"], "verified")

    # F5. cache only when project+ref match
    def test_F5_cache_scope(self):
        slug = self.new_project(slug="cachep")
        r1 = self.add_task(slug, "C1")["ref"]
        r2 = self.add_task(slug, "C2")["ref"]
        self.ok(["claim", "--project", slug, r1])
        # explicit --task for r2 must ignore cache for r1 -> attempt-less late=0
        res = self.ok(["note", "--project", slug, "--task", r2, "--kind", "note",
                       "--body", "other task"])
        self.assertEqual(res["late"], 0)
        conn, _ = store_mod.open_project_db(slug, root=Path(self.home))
        try:
            row = conn.execute("SELECT attempt_id FROM journal WHERE entry_id=?",
                               (res["entry_id"],)).fetchone()
            self.assertIsNone(row["attempt_id"])
        finally:
            conn.close()

    # F6. cache only after commit, never on replay/refused
    def test_F6_cache_lifecycle(self):
        import taskstate as ts_mod
        slug = self.new_project(slug="cachelife")
        cache_path = os.path.join(self.repo, ".git", "taskstate.json")
        try:
            os.unlink(cache_path)
        except OSError:
            pass
        # refused claim (on hold) leaves no cache
        ref_h = self.add_task(slug, "H")["ref"]
        code, out = self.tcall(["task", "show", "--project", slug, ref_h])
        ver = out["result"]["task"]["version"]
        self.ok(["task", "hold", "--project", slug, ref_h, "--reason", "wait",
                 "--expect-version", str(ver)], human=True)
        err = self.err(["claim", "--project", slug, ref_h])
        self.assertEqual(err["code"], "on_hold")
        self.assertFalse(os.path.exists(cache_path))
        self.ok(["task", "unhold", "--project", slug, ref_h,
                 "--expect-version", str(ver + 1)], human=True)
        cc = self.ok(["claim", "--project", slug, ref_h])
        self.assertTrue(os.path.isfile(cache_path))
        # idempotent replay does not touch cache: delete then replay same request
        rid = str(uuid.uuid4())
        ref2 = self.add_task(slug, "R")["ref"]
        # clear cache from previous claim first
        try:
            os.unlink(cache_path)
        except OSError:
            pass
        # use explicit request id twice
        argv = ["claim", "--project", slug, ref2, "--request-id", rid]
        r1 = self.ok(argv)
        self.assertTrue(os.path.isfile(cache_path))
        mtime1 = os.path.getmtime(cache_path)
        import time as _t
        _t.sleep(0.02)
        # remove cache, replay should NOT recreate it
        os.unlink(cache_path)
        r2 = self.ok(argv)
        self.assertEqual(r1, r2)
        self.assertFalse(os.path.exists(cache_path))
        # release clears cache
        cc3 = self.ok(["claim", "--project", slug, self.add_task(slug, "Z")["ref"]])
        self.assertTrue(os.path.isfile(cache_path))
        self.ok(["release", "--project", slug, "--task", cc3["ref"],
                 "--attempt", cc3["attempt_id"], "--epoch", str(cc3["epoch"])])
        self.assertFalse(os.path.exists(cache_path))

    # F7. journal request_id equals returned request_id
    def test_F7_request_id(self):
        slug = self.new_project(slug="reqp")
        ref = self.add_task(slug, "RQ")["ref"]
        res = self.ok(["note", "--project", slug, "--task", ref, "--kind", "note",
                       "--body", "hello"])
        self.assertIn("request_id", res)
        rid = res["request_id"]
        self.assertTrue(rid)
        conn, _ = store_mod.open_project_db(slug, root=Path(self.home))
        try:
            row = conn.execute("SELECT request_id FROM journal WHERE entry_id=?",
                               (res["entry_id"],)).fetchone()
            self.assertEqual(row["request_id"], rid)
        finally:
            conn.close()

    # F8. cancel ends owner attempt
    def test_F8_cancel(self):
        slug = self.new_project(slug="cancelp")
        ref = self.add_task(slug, "CX")["ref"]
        cc = self.ok(["claim", "--project", slug, ref])
        code, out = self.tcall(["task", "show", "--project", slug, ref])
        ver = out["result"]["task"]["version"]
        res = self.ok(["task", "cancel", "--project", slug, ref,
                       "--expect-version", str(ver)], human=True)
        self.assertIn("version", res)
        err = self.err(["heartbeat", "--project", slug, "--task", ref,
                        "--attempt", cc["attempt_id"], "--epoch", str(cc["epoch"])])
        self.assertEqual(err["code"], "stale_claim")

    # F9. takeover guards
    def test_F9_takeover_guards(self):
        slug = self.new_project(slug="top")
        ref = self.add_task(slug, "TG")["ref"]
        self.ok(["claim", "--project", slug, ref])
        code, out = self.tcall(["task", "show", "--project", slug, ref])
        ver = out["result"]["task"]["version"]
        self.ok(["task", "hold", "--project", slug, ref, "--reason", "wait",
                 "--expect-version", str(ver)], human=True)
        os.environ["TASKSTATE_LEASE_SECONDS"] = "0"
        try:
            err = self.err(["takeover", "--project", slug, ref, "--reason", "try"])
            self.assertEqual(err["code"], "on_hold")
        finally:
            os.environ["TASKSTATE_LEASE_SECONDS"] = "7200"
        code, out = self.tcall(["task", "show", "--project", slug, ref])
        self.ok(["task", "unhold", "--project", slug, ref,
                 "--expect-version", str(out["result"]["task"]["version"])], human=True)
        # spec-linked without grant
        spec = str(uuid.uuid4())
        ref2 = self.add_task(slug, "SG", spec_id=spec)["ref"]
        # claim it first with a grant, then drop grants to test takeover guard
        self.ok(["grant", "add", "--project", slug, "--kind", "execute",
                 "--task", ref2, "--source", "s"], human=True)
        cc2 = self.ok(["claim", "--project", slug, ref2])
        conn, _ = store_mod.open_project_db(slug, root=Path(self.home))
        try:
            conn.execute("DELETE FROM grant_")
            conn.commit()
        finally:
            conn.close()
        os.environ["TASKSTATE_LEASE_SECONDS"] = "0"
        try:
            err = self.err(["takeover", "--project", slug, ref2, "--reason", "try2"])
            self.assertEqual(err["code"], "not_authorized")
        finally:
            os.environ["TASKSTATE_LEASE_SECONDS"] = "7200"

    # F10. release reason journal
    def test_F10_release_reason(self):
        slug = self.new_project(slug="relp")
        ref = self.add_task(slug, "RL")["ref"]
        cc = self.ok(["claim", "--project", slug, ref])
        self.ok(["release", "--project", slug, "--task", ref, "--attempt", cc["attempt_id"],
                 "--epoch", str(cc["epoch"]), "--reason", "done now"])
        conn, _ = store_mod.open_project_db(slug, root=Path(self.home))
        try:
            row = conn.execute("SELECT body FROM journal WHERE task_id IN "
                               "(SELECT task_id FROM task WHERE ref=?) ORDER BY recorded_at DESC LIMIT 1",
                               (ref,)).fetchone()
            self.assertIn("release: done now", row["body"])
        finally:
            conn.close()

    # F11. handoff diffstat/dirty + claim --spec-id removed
    def test_F11_handoff_cleanup(self):
        slug = self.new_project(slug="hop")
        ref = self.add_task(slug, "HO")["ref"]
        res = self.ok(["handoff", "--project", slug, "--task", ref,
                       "--next-action", "next"])
        conn, _ = store_mod.open_project_db(slug, root=Path(self.home))
        try:
            row = conn.execute("SELECT data_json FROM journal WHERE entry_id=?",
                               (res["entry_id"],)).fetchone()
            data = json.loads(row["data_json"])
            self.assertIn("diffstat", data["facts"])
            self.assertIn("dirty", data["facts"])
        finally:
            conn.close()
        # outside git: dirty None, diffstat None
        outside = os.path.join(self.tmp.name, "plain2")
        os.makedirs(outside, exist_ok=True)
        os.chdir(outside)
        try:
            ref2 = self.add_task(slug, "HO2")["ref"]
            res2 = self.ok(["handoff", "--project", slug, "--task", ref2,
                            "--next-action", "next2"])
        finally:
            os.chdir(self.repo)
        conn, _ = store_mod.open_project_db(slug, root=Path(self.home))
        try:
            row = conn.execute("SELECT data_json FROM journal WHERE entry_id=?",
                               (res2["entry_id"],)).fetchone()
            data = json.loads(row["data_json"])
            self.assertIsNone(data["facts"]["diffstat"])
            self.assertIsNone(data["facts"]["dirty"])
        finally:
            conn.close()
        # claim --spec-id is gone
        code, out = self.tcall(["claim", "--project", slug, ref, "--spec-id", "x"])
        self.assertEqual(code, 2)

    # F12. migration from meta-without-version + backup
    def test_F12_migration_backup(self):
        slug = "migp"
        path = Path(self.home) / (slug + ".db")
        if path.exists():
            path.unlink()
        conn = sqlite3.connect(str(path))
        try:
            conn.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("INSERT INTO meta(key, value) VALUES('other', 'x')")
            conn.commit()
        finally:
            conn.close()
        conn2, _ = store_mod.open_project_db(slug, root=Path(self.home))
        try:
            row = conn2.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["value"], str(store_mod.SCHEMA_VERSION))
            row2 = conn2.execute("SELECT value FROM meta WHERE key='next_ref_n'").fetchone()
            self.assertEqual(row2["value"], "1")
        finally:
            conn2.close()
        backs = list((Path(self.home) / "backups").glob(slug + "-*.db"))
        self.assertTrue(backs)

    # F13. attention --all store_error
    def test_F13_store_error(self):
        bad = Path(self.home) / "badstore.db"
        bad.write_bytes(os.urandom(128))
        code, out = self.tcall(["attention", "--all"])
        self.assertEqual(code, 0)
        items = out["result"]["items"]
        errs = [i for i in items if i.get("type") == "store_error" and i.get("project") == "badstore"]
        self.assertTrue(errs)
        self.assertIsNone(errs[0]["since"])
        self.assertTrue(errs[0]["detail"])


if __name__ == "__main__":
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
        unittest.main(verbosity=2)
