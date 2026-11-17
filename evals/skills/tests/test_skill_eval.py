"""Public offline CLI contract checks; no model invocation.

Admission: protects independent body-delivery proof, missing-evidence
denominators, and evaluator-key isolation at the caller's actual CLI boundary.
Credible regressions are accepting partial reads as loads, treating interrupted
runs as misses, or materializing answer keys. No existing suite owns these
contracts. Standard-library synthetic protocol and throwaway repo snapshots
keep cost deterministic/offline. Seen-red evidence is retained in
artifacts/skill-evals/2026-09-30-offline-verification/verification.json.

The Claude transcript test protects the native load proof and action order.
Credible regressions are digesting the whole SKILL.md against a delivered body
that has no frontmatter, counting a Skill result with no linked body, counting a
sliced Read, ordering an action by its own line when its API message started
before the skill body arrived, keeping an unproved bare-name Skill load under its
bare name (a silent miss), and keeping a Skill load whose name differs from its
delivered body without an issue (also a silent miss). Each was seen red: the
first four under one mutation each of skill_eval.py, the last two on the code
before their fix. EVIDENCE.md points to the output.

The successor test protects scoring after the swe consolidation merged two
target skills. The credible regression is a silent miss on every case of a
merged family; it was seen red with the successor lookup removed from the
activation loop.

The resource-read and child-record tests protect frozen playbook/reference
verification, Claude and synthetic resource proofs, subagent record routing,
Bash unproved-read recording, and isolation of existing activation metrics.
Credible regressions are dropping non-SKILL.md reads, failing to verify frozen
resources in declared_snapshot, accepting a content-mismatched or sliced
playbook read or a failed or incomplete synthetic resource_read as success,
recording a non-frozen file Read in any evidence list, matching a suffixed path
in Bash or counting Bash cat as a load or success, leaking child or unrelated
non-root reads into root activation, colliding root and child requests that
share one request_id, or changing existing score fields when resource reads
appear.

The hook-on-arm tests protect selective SessionStart retention, arm separation
in frozen configurations and aggregate groups, synthetic hook.delivered checks,
and Claude hook_success delivery proofs and hook-off isolation. Credible
regressions are leaving non-SessionStart hooks in a
hook-on snapshot, pooling hook-on and hook-off runs in aggregate, accepting a
tampered, undeclared, duplicate, or post-user hook delivery without an issue,
recording a post-user hook row as a delivery, missing a declared plugin with no
delivery row, accepting a non-null parentUuid on the first hook row for start
coverage, skipping hook verification in declared_snapshot, or allowing
hook_success or hook_additional_context in hook-off.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
SCRIPT = HERE / "skill_eval.py"
REPO = HERE.parents[1]


class OfflineCLIContract(unittest.TestCase):
    def setUp(self):
        root = REPO / "artifacts" / "skill-evals"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="contract-", dir=root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = next(c for c in json.loads((HERE / "cases.json").read_text())["cases"]
                         if c["target"] == "swe:implement" and c["category"] == "natural")

    def cli(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                                text=True, capture_output=True, cwd=REPO)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def prepare(self, name, case=None, hook_arm=None):
        run = self.root / name
        extra = ["--hook-arm", hook_arm] if hook_arm else []
        self.cli("materialize", "--case", (case or self.case)["id"], "--runtime", HERE / "runtime.offline.json",
                 "--output", run, *extra)
        manifest = json.loads((run / "manifest.json").read_text())
        skill = manifest["skills"]["swe:implement"]
        body = Path(skill["path"]).read_text()
        return run, skill, body

    def trace(self, run, events, state="completed", native=False):
        source = self.root / (run.name + ".jsonl")
        with source.open("w") as handle:
            for index, event in enumerate(events, 1):
                event = {"event_id": f"event-{index}", "session_id": "root", **event}
                handle.write(json.dumps(event) + "\n")
        flags = [] if native else ["--format", "synthetic-contract-v1", "--evidence-kind", "synthetic"]
        self.cli("capture", "--run", run, "--source", source, "--state", state, *flags)
        self.assertEqual((run / "raw.jsonl").read_bytes(), source.read_bytes())
        return self.cli("score", "--run", run)

    def test_delivery_identity_order_and_denominators(self):
        # Each row has an independently specified result from the evidence contract.
        rows = [
            ("full", 0, True, "exact", "root", "before", "completed", "loaded", "before"),
            ("partial-flag", 0, False, "exact", "root", "before", "completed", "unavailable", "unavailable"),
            ("truncated-body", 0, True, "truncated", "root", "before", "completed", "unavailable", "unavailable"),
            ("failed", 1, True, "exact", "root", "before", "completed", "miss", "unavailable"),
            ("missing-status", None, True, "exact", "root", "before", "completed", "unavailable", "unavailable"),
            ("boolean-status", False, True, "exact", "root", "before", "completed", "unavailable", "unavailable"),
            ("late", 0, True, "exact", "root", "after", "completed", "loaded", "late"),
            ("child", 0, True, "exact", "child", "before", "completed", "miss", "unavailable"),
            ("timeout", 0, True, "exact", "root", "before", "timeout", "loaded", "before"),
        ]
        scores = []
        for name, code, complete, body_kind, session, order, state, expected, timing in rows:
            with self.subTest(name=name):
                run, skill, body = self.prepare(name)
                request = {"type": "skill_read.request", "request_id": "read-1", "skill": "swe:implement",
                           "path": skill["path"], "session_id": session}
                result = {"type": "skill_read.result", "request_id": "read-1", "exit_code": code,
                          "body": body if body_kind == "exact" else body[:50], "body_complete": complete,
                          "session_id": session}
                action = {"type": "action.started", "kind": self.case["relevant_action"]}
                events = [{"type": "session.started"}, {"type": "skill.mention", "text": "I will use swe:implement"}]
                events += [request, result, action] if order == "before" else [action, request, result]
                events.append({"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}})
                if name == "full":
                    events.append({"type": "action.started", "kind": "child follow-up", "session_id": "child"})
                score = self.trace(run, events, state)
                if name == "full":
                    self.assertEqual(score["evidence_coverage"], "complete")
                self.assertEqual(score["activation"]["swe:implement"], expected)
                self.assertEqual(score["timing"]["swe:implement"], timing)
                self.assertFalse(score["measured_efficacy"])
                scores.append(run / "score.json")
        report = self.cli("aggregate", *scores)
        group = report["groups"][0]
        # full+late are loads, failed+child are misses; partial+truncated+timeout excluded.
        self.assertEqual(group["recall_denominator"], 4)
        self.assertEqual(group["recall"], 0.5)
        self.assertEqual(group["counts"]["session_timeout"], 1)

    def test_negative_auxiliaries_and_partial_confusion(self):
        case = next(c for c in json.loads((HERE / "cases.json").read_text())["cases"]
                    if c["target"] == "swe:implement" and c["category"] == "negative" and c["expected_skills"])
        scores = []
        for state, partial in (("completed", False), ("incomplete", False), ("completed", True)):
            run, _, _ = self.prepare("negative-" + state + str(partial), case)
            manifest = json.loads((run / "manifest.json").read_text())
            events = [{"type": "session.started"}]
            for skill_id in [case["expected_skills"][0], "swe:implement"]:
                skill = manifest["skills"][skill_id]
                events += [{"type": "skill_read.request", "request_id": skill_id, "skill": skill_id, "path": skill["path"]},
                           {"type": "skill_read.result", "request_id": skill_id, "exit_code": 0,
                            "body": Path(skill["path"]).read_text(), "body_complete": not (partial and skill_id == "swe:implement")}]
            events += [{"type": "action.started", "kind": case["relevant_action"]},
                       {"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}}]
            score = self.trace(run, events, state)
            if partial:
                self.assertIsNone(score["false_activation"])
                self.assertEqual(score["unexpected_skills"], [])
            else:
                self.assertTrue(score["false_activation"])
                self.assertEqual(score["unexpected_skills"], ["swe:implement"])
            scores.append(run / "score.json")
        # A correct positive activation is not an opportunity for negative-case confusion.
        positive, skill, body = self.prepare("positive-confusion-control")
        self.trace(positive, [{"type": "session.started"},
                             {"type": "skill_read.request", "request_id": "positive", "skill": "swe:implement", "path": skill["path"]},
                             {"type": "skill_read.result", "request_id": "positive", "exit_code": 0, "body": body, "body_complete": True},
                             {"type": "action.started", "kind": self.case["relevant_action"]},
                             {"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}}])
        scores.append(positive / "score.json")
        report = self.cli("aggregate", *scores)
        self.assertEqual(report["groups"][0]["false_activation_rate"], 1)
        self.assertEqual(report["groups"][0]["false_activation_denominator"], 1)
        self.assertEqual(report["confusion"][0]["count"], 1)
        self.assertEqual(report["confusion"][0]["denominator"], 1)
        self.assertEqual(report["confusion"][0]["interrupted_or_partial_observations"], 1)

    def test_merged_skill_scores_as_its_successor(self):
        # A silent miss on every case of a merged family would read as an activation loss.
        excluded = self.cli("validate")["excluded_on_this_catalog"]
        self.assertEqual(sorted(excluded), ["AR-10", "TA-07", "TA-10", "TC-07"])
        for case_id in ("TA-07", "TA-10"):
            self.cli("materialize", "--case", case_id, "--runtime", HERE / "runtime.offline.json",
                     "--output", self.root / ("excluded-" + case_id), ok=False)
        cases = {c["id"]: c for c in json.loads((HERE / "cases.json").read_text())["cases"]}
        scores = {}
        for case_id in ("TA-01", "TA-09"):
            case = cases[case_id]
            run, _, _ = self.prepare("successor-" + case_id, case)
            skill = json.loads((run / "manifest.json").read_text())["skills"]["swe:testing-code"]
            scores[case_id] = self.trace(run, [
                {"type": "session.started"},
                {"type": "skill_read.request", "request_id": "merged", "skill": "swe:testing-code", "path": skill["path"]},
                {"type": "skill_read.result", "request_id": "merged", "exit_code": 0,
                 "body": Path(skill["path"]).read_text(), "body_complete": True},
                {"type": "action.started", "kind": case["relevant_action"]},
                {"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}}])
        self.assertEqual(scores["TA-01"]["activation"], {"swe:test-audit": "loaded"})
        self.assertEqual(scores["TA-01"]["unexpected_skills"], [])
        self.assertTrue(scores["TA-09"]["false_activation"])

    def claude_trace(self, run, steps, relevant, sidechains=None, hook_rows=None, plugin_dirs=None, hook_parent=None):
        """Write a minimal transcript in the audited Claude Code shape (EVIDENCE.md) and score it."""
        sid = "claude-session"

        def build_lines(seq_steps, is_sidechain=False, agent_id=None):
            rows = []

            def add(row, parent=None):
                extra = {"agentId": agent_id} if agent_id is not None else {}
                row = {"uuid": f"{agent_id or 'root'}-{len(rows)}",
                       "parentUuid": parent or (rows[-1]["uuid"] if rows else None),
                       "sessionId": sid, "isSidechain": is_sidechain, **extra, **row}
                rows.append(row)

            if not is_sidechain and hook_rows:
                for idx, att in enumerate(hook_rows):
                    add({"type": "attachment", "attachment": att}, hook_parent if idx == 0 else None)
            add({"type": "user", "message": {"role": "user", "content": "rename it"}})
            for kind, message_id, tool_use_id, payload in seq_steps:
                if kind == "call":
                    add({"type": "assistant", "message": {"id": message_id, "content": [
                        {"type": "tool_use", "id": tool_use_id, "name": payload["name"], "input": payload["input"]}]}})
                elif kind in {"result", "sibling-result"}:
                    # A sibling result answers an earlier call of one API message, so it branches from that call.
                    parent = next(r["uuid"] for r in rows if tool_use_id in json.dumps(r["message"])) \
                        if kind == "sibling-result" else None
                    add({"type": "user", "toolUseResult": payload, "message": {"role": "user", "content": [
                        {"type": "tool_result", "tool_use_id": tool_use_id, "content": "ok"}]}}, parent)
                elif kind == "attachment":
                    add({"type": "attachment", "attachment": payload})
                else:
                    add({"type": "user", "isMeta": True, "sourceToolUseID": tool_use_id, "message": {
                        "role": "user", "content": [{"type": "text", "text": payload}]}})
            return rows

        lines = build_lines(steps)
        source = self.root / (run.name + ".jsonl")
        source.write_text("".join(json.dumps(row) + "\n" for row in lines)
                          + json.dumps({"type": "cost-state", "sessionId": sid}) + "\n")
        if sidechains:
            subdir = source.with_suffix("") / "subagents"
            subdir.mkdir(parents=True, exist_ok=True)
            for agent_id, sub_steps in sidechains.items():
                sub_lines = build_lines(sub_steps, is_sidechain=True, agent_id=agent_id)
                (subdir / f"agent-{agent_id}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in sub_lines))
        stream = self.root / (run.name + ".stream.jsonl")
        stream.write_text(json.dumps({"type": "result", "subtype": "success", "is_error": False, "session_id": sid}) + "\n")
        dirs = plugin_dirs if plugin_dirs is not None else [run / "inputs" / "plugins" / "swe"]
        dir_args = [arg for d in dirs for arg in ("--plugin-dir", d)]
        self.cli("capture", "--run", run, "--source", source, "--state", "completed", "--format", "claude-transcript",
                 *dir_args, "--stream", stream, "--relevant-action", relevant)
        return self.cli("score", "--run", run)

    def test_claude_transcript_load_proof_and_action_order(self):
        # Shapes come from the audited probe traces; see EVIDENCE.md "Claude transcript audit".
        # Values: evidence coverage, then activation and timing of swe:implement.
        unresolved = ("complete", "unavailable", "unavailable")
        expected = {"skill-body": ("complete", "loaded", "before"), "skill-without-body": unresolved,
                    "skill-in-action-message": ("complete", "loaded", "late"), "full-read": ("complete", "loaded", "before"),
                    "sliced-read": unresolved, "bare-name-without-body": unresolved,
                    "name-differs-from-body": ("partial", "unavailable", "unavailable"),
                    "skill-with-arguments": ("complete", "loaded", "before"),
                    "parallel-calls": ("complete", "loaded", "before"),
                    "parallel-calls-split-message": ("partial", "loaded", "unavailable")}
        for name, outcome in expected.items():
            with self.subTest(name=name):
                run, skill, text = self.prepare("claude-" + name)
                lines = text.split("\n")
                body = ("Base directory for this skill: " + str(Path(skill["path"]).parent) + "\n\n"
                        + text.split("\n---\n", 1)[1].lstrip("\n"))
                requested = {"bare-name-without-body": "implement", "name-differs-from-body": "swe:diagnose"}
                skill_call = [("call", "message-skill", "use-skill",
                               {"name": "Skill", "input": {"skill": requested.get(name, "swe:implement")}}),
                              ("result", None, "use-skill", {"success": True, "commandName": "swe:implement"})]
                arguments = "rename it"
                with_arguments = [("call", "message-skill", "use-skill",
                                   {"name": "Skill", "input": {"skill": "swe:implement", "args": arguments}}),
                                  skill_call[1], ("body", None, "use-skill", body + "\n\nARGUMENTS: " + arguments)]
                parallel = [skill_call[0], ("call", "message-skill", "use-glob", {"name": "Glob", "input": {"pattern": "*"}}),
                            ("result", None, "use-glob", {"filenames": []}),
                            ("sibling-result",) + skill_call[1][1:], ("body", None, "use-skill", body)]
                # A different message id on the second call makes the same shape a real branch.
                split = [parallel[0], ("call", "message-other", "use-glob", parallel[1][3])] + parallel[2:]
                read_call = [("call", "message-read", "use-read", {"name": "Read", "input": {"file_path": skill["path"]}})]
                shown = len(lines) if name == "full-read" else 3
                read_result = [("result", None, "use-read", {"type": "text", "file": {
                    "filePath": skill["path"], "content": text if name == "full-read" else "\n".join(lines[:3]),
                    "startLine": 1, "numLines": shown, "totalLines": len(lines)}})]
                steps = {"skill-body": skill_call + [("body", None, "use-skill", body)],
                         "skill-without-body": skill_call, "bare-name-without-body": skill_call,
                         "name-differs-from-body": skill_call + [("body", None, "use-skill", body)],
                         "skill-in-action-message": skill_call + [("body", None, "use-skill", body)],
                         "full-read": read_call + read_result, "sliced-read": read_call + read_result,
                         "skill-with-arguments": with_arguments, "parallel-calls": parallel,
                         "parallel-calls-split-message": split}[name]
                # The Edit shares the Skill call's API message only in skill-in-action-message.
                edit_message = "message-skill" if name == "skill-in-action-message" else "message-edit"
                steps += [("call", edit_message, "use-edit", {"name": "Edit", "input": {"file_path": "calc.py"}}),
                          ("result", None, "use-edit", {"filePath": "calc.py"})]
                score = self.claude_trace(run, steps, "use-edit")
                self.assertEqual((score["evidence_coverage"], score["activation"]["swe:implement"],
                                  score["timing"]["swe:implement"]), outcome)

    def test_isolation_native_unknown_and_frozen_input_integrity(self):
        run, skill, body = self.prepare("identity")
        messages = json.loads((run / "inputs" / "messages.json").read_text())
        self.assertEqual(messages, self.case["messages"])
        self.assertFalse((run / "workspace" / "cases.json").exists())
        for root in (run / "workspace", run / "inputs"):
            self.assertFalse(any(p.name == "cases.json" for p in root.rglob("*")))
        self.assertTrue((run / "workspace" / ".git").is_dir())
        self.assertFalse((run / "workspace" / ".git" / "hooks").exists())
        self.assertFalse((run / "workspace" / ".git" / "commondir").exists())
        manifest = json.loads((run / "manifest.json").read_text())
        self.assertIn("lab:research", manifest["skills"])
        self.assertIn("swe:ship-pr", manifest["skills"])
        self.cli("materialize", "--case", self.case["id"], "--runtime", HERE / "runtime.offline.json", "--output", run, ok=False)
        events = [{"type": "session.started"},
                  {"type": "skill_read.request", "request_id": "read-1", "skill": "swe:implement", "path": "/unrelated/SKILL.md"},
                  {"type": "skill_read.result", "request_id": "read-1", "exit_code": 0, "body": body, "body_complete": True},
                  {"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}}]
        score = self.trace(run, events)
        self.assertEqual(score["activation"]["swe:implement"], "unavailable")
        # Body identity does not repair incorrect file identity.
        run2, _, _ = self.prepare("native")
        score2 = self.trace(run2, events, native=True)
        self.assertEqual(score2["evidence_coverage"], "unavailable")
        self.assertEqual(score2["activation"]["swe:implement"], "unavailable")
        Path(skill["path"]).write_text(body + "tampered\n")
        self.cli("score", "--run", run, ok=False)
        run3, _, _ = self.prepare("outside-link")
        outside = self.root / "outside.txt"
        outside.write_text("must not enter captured results")
        (run3 / "workspace" / "external.txt").symlink_to(outside)
        source = self.root / "empty.jsonl"
        source.write_text("")
        self.cli("capture", "--run", run3, "--source", source, "--state", "incomplete", ok=False)
        self.assertFalse((run3 / "raw.jsonl").exists())

    def test_claude_resource_reads_sidechain_and_bash(self):
        res_id = "swe:skills/swe-mode/playbooks/fix-bug.md"
        unchanged_keys = ("activation", "timing", "observed_skills", "expected_skills", "allowed_skills",
                          "unresolved_skills", "false_activation", "unexpected_skills",
                          "load_status_counts", "evidence_coverage", "session_state")

        def skill_and_edit(skill, text):
            body = ("Base directory for this skill: " + str(Path(skill["path"]).parent) + "\n\n"
                    + text.split("\n---\n", 1)[1].lstrip("\n"))
            return [
                ("call", "message-skill", "use-skill", {"name": "Skill", "input": {"skill": "swe:implement"}}),
                ("result", None, "use-skill", {"success": True, "commandName": "swe:implement"}),
                ("body", None, "use-skill", body),
            ], [
                ("call", "message-edit", "use-edit", {"name": "Edit", "input": {"file_path": "calc.py"}}),
                ("result", None, "use-edit", {"filePath": "calc.py"}),
            ]

        base_run, base_skill, base_text = self.prepare("res-baseline")
        skill_steps, edit_steps = skill_and_edit(base_skill, base_text)
        baseline_score = self.claude_trace(base_run, skill_steps + edit_steps, "use-edit")

        full_run, full_skill, full_text = self.prepare("res-full")
        manifest = json.loads((full_run / "manifest.json").read_text())
        self.assertIn("lab:skills/lab-mode/references/claim-checklist.md", manifest["resources"])
        playbook = manifest["resources"][res_id]
        pb_text = Path(playbook["path"]).read_text()
        pb_lines = pb_text.split("\n")
        s_steps, e_steps = skill_and_edit(full_skill, full_text)
        non_frozen = str(full_run / "workspace" / "calc.py")
        pb_read = [
            ("call", "message-pb", "use-pb", {"name": "Read", "input": {"file_path": playbook["path"]}}),
            ("result", None, "use-pb", {"type": "text", "file": {
                "filePath": playbook["path"], "content": pb_text,
                "startLine": 1, "numLines": len(pb_lines), "totalLines": len(pb_lines)}}),
            ("call", "message-other", "use-other", {"name": "Read", "input": {"file_path": non_frozen}}),
            ("result", None, "use-other", {"type": "text", "file": {
                "filePath": non_frozen, "content": "x = 1\n",
                "startLine": 1, "numLines": 1, "totalLines": 1}}),
        ]
        full_score = self.claude_trace(full_run, s_steps + pb_read + e_steps, "use-edit")
        full_ev = json.loads((full_run / "evidence.json").read_text())
        self.assertEqual(full_score["observed_resources"], [res_id])
        self.assertEqual(len(full_ev["resource_reads"]), 1)
        self.assertEqual(full_ev["resource_reads"][0]["status"], "success")
        self.assertEqual(full_ev["resource_reads"][0]["resource"], res_id)
        self.assertEqual(full_ev["resource_reads"][0]["body_sha256"], playbook["sha256"])
        self.assertEqual(len(full_ev["loads"]), 1)
        self.assertEqual(full_ev["child_loads"], [])
        self.assertEqual(full_ev["child_resource_reads"], [])
        self.assertEqual(full_ev["unproved_reads"], [])
        for key in unchanged_keys:
            self.assertEqual(full_score[key], baseline_score[key])

        mismatch_run, _, _ = self.prepare("res-mismatch")
        pb = json.loads((mismatch_run / "manifest.json").read_text())["resources"][res_id]
        pb_text = Path(pb["path"]).read_text()
        pb_l = pb_text.split("\n")
        mismatch_steps = [
            ("call", "message-pb", "use-pb", {"name": "Read", "input": {"file_path": pb["path"]}}),
            ("result", None, "use-pb", {"type": "text", "file": {
                "filePath": pb["path"], "content": pb_text + "mismatch\n",
                "startLine": 1, "numLines": len(pb_l), "totalLines": len(pb_l)}}),
            ("call", "message-edit", "use-edit", {"name": "Edit", "input": {"file_path": "calc.py"}}),
            ("result", None, "use-edit", {"filePath": "calc.py"}),
        ]
        mismatch_score = self.claude_trace(mismatch_run, mismatch_steps, "use-edit")
        mismatch_ev = json.loads((mismatch_run / "evidence.json").read_text())
        self.assertEqual(mismatch_ev["resource_reads"][0]["status"], "partial")
        self.assertEqual(mismatch_ev["resource_reads"][0]["detail"], "content digest mismatch")
        self.assertEqual(mismatch_score["observed_resources"], [])

        sliced_run, _, _ = self.prepare("res-sliced")
        pb = json.loads((sliced_run / "manifest.json").read_text())["resources"][res_id]
        pb_l = Path(pb["path"]).read_text().split("\n")
        sliced_steps = [
            ("call", "message-pb", "use-pb", {"name": "Read", "input": {"file_path": pb["path"]}}),
            ("result", None, "use-pb", {"type": "text", "file": {
                "filePath": pb["path"], "content": "\n".join(pb_l[:2]),
                "startLine": 1, "numLines": 2, "totalLines": len(pb_l)}}),
            ("call", "message-edit", "use-edit", {"name": "Edit", "input": {"file_path": "calc.py"}}),
            ("result", None, "use-edit", {"filePath": "calc.py"}),
        ]
        sliced_score = self.claude_trace(sliced_run, sliced_steps, "use-edit")
        sliced_ev = json.loads((sliced_run / "evidence.json").read_text())
        self.assertEqual(sliced_ev["resource_reads"][0]["status"], "partial")
        self.assertEqual(sliced_ev["resource_reads"][0]["detail"], "sliced read")
        self.assertEqual(sliced_score["observed_resources"], [])

        child_run, _, _ = self.prepare("res-sidechain")
        pb = json.loads((child_run / "manifest.json").read_text())["resources"][res_id]
        pb_text = Path(pb["path"]).read_text()
        pb_l = pb_text.split("\n")
        root_steps = [
            ("call", "message-agent", "use-agent", {"name": "Agent", "input": {"prompt": "check"}}),
            ("result", None, "use-agent", {"agentId": "sub1"}),
            ("call", "message-edit", "use-edit", {"name": "Edit", "input": {"file_path": "calc.py"}}),
            ("result", None, "use-edit", {"filePath": "calc.py"}),
        ]
        sub_steps = [
            ("call", "sub-msg", "sub-read", {"name": "Read", "input": {"file_path": pb["path"]}}),
            ("result", None, "sub-read", {"type": "text", "file": {
                "filePath": pb["path"], "content": pb_text,
                "startLine": 1, "numLines": len(pb_l), "totalLines": len(pb_l)}}),
        ]
        child_score = self.claude_trace(child_run, root_steps, "use-edit", sidechains={"sub1": sub_steps})
        child_ev = json.loads((child_run / "evidence.json").read_text())
        self.assertEqual(child_ev["resource_reads"], [])
        self.assertEqual(child_score["observed_resources"], [])
        self.assertEqual(child_score["child_observed_resources"], [res_id])
        self.assertEqual(len(child_ev["child_resource_reads"]), 1)
        self.assertEqual(child_ev["child_resource_reads"][0]["status"], "success")
        self.assertEqual(child_ev["child_resource_reads"][0]["agent_id"], "sub1")

        bash_run, _, _ = self.prepare("res-bash")
        pb = json.loads((bash_run / "manifest.json").read_text())["resources"][res_id]
        bash_steps = [
            ("call", "message-bash", "use-bash", {"name": "Bash", "input": {"command": f"cat {pb['path']}"}}),
            ("result", None, "use-bash", {"stdout": ""}),
            ("call", "message-edit", "use-edit", {"name": "Edit", "input": {"file_path": "calc.py"}}),
            ("result", None, "use-edit", {"filePath": "calc.py"}),
        ]
        bash_score = self.claude_trace(bash_run, bash_steps, "use-edit")
        bash_ev = json.loads((bash_run / "evidence.json").read_text())
        self.assertEqual(bash_ev["loads"], [])
        self.assertEqual(bash_ev["resource_reads"], [])
        self.assertEqual(bash_ev["child_loads"], [])
        self.assertEqual(bash_ev["child_resource_reads"], [])
        self.assertEqual(bash_score["observed_skills"], [])
        self.assertEqual(bash_score["observed_resources"], [])
        self.assertEqual(bash_score["unproved_read_count"], 1)
        self.assertEqual(bash_ev["unproved_reads"][0]["resource"], res_id)
        self.assertEqual(bash_ev["unproved_reads"][0]["proof"], "bash_command_mentions_path")
        self.assertEqual(bash_ev["unproved_reads"][0]["status"], "unproved")

        bak_run, _, _ = self.prepare("res-bash-bak")
        pb = json.loads((bak_run / "manifest.json").read_text())["resources"][res_id]
        bak_steps = [
            ("call", "message-bash", "use-bash", {"name": "Bash", "input": {"command": f"cat {pb['path']}.bak"}}),
            ("result", None, "use-bash", {"stdout": ""}),
            ("call", "message-edit", "use-edit", {"name": "Edit", "input": {"file_path": "calc.py"}}),
            ("result", None, "use-edit", {"filePath": "calc.py"}),
        ]
        bak_score = self.claude_trace(bak_run, bak_steps, "use-edit")
        bak_ev = json.loads((bak_run / "evidence.json").read_text())
        self.assertEqual(bak_ev["unproved_reads"], [])
        self.assertEqual(bak_score["unproved_read_count"], 0)

        tamper_run, _, _ = self.prepare("res-tamper")
        tampered_dir = self.root / "tampered-swe"
        shutil.copytree(tamper_run / "inputs" / "plugins" / "swe", tampered_dir)
        (tampered_dir / "skills" / "swe-mode" / "playbooks" / "fix-bug.md").write_text("tampered\n")
        tamper_source = self.root / "tamper.jsonl"
        tamper_source.write_text("")
        tamper_err = self.cli("capture", "--run", tamper_run, "--source", tamper_source, "--state", "incomplete",
                              "--format", "claude-transcript", "--plugin-dir", tampered_dir, ok=False)
        self.assertIn("resource does not match the frozen catalog", tamper_err.stderr)
        self.assertIn("fix-bug.md", tamper_err.stderr)

    def test_synthetic_resource_read_and_child_skill(self):
        ref_id = "lab:skills/lab-mode/references/claim-checklist.md"
        base_run, base_skill, base_body = self.prepare("syn-baseline")
        base_events = [
            {"type": "session.started"},
            {"type": "skill_read.request", "request_id": "s-1", "skill": "swe:implement", "path": base_skill["path"]},
            {"type": "skill_read.result", "request_id": "s-1", "exit_code": 0, "body": base_body, "body_complete": True},
            {"type": "action.started", "kind": self.case["relevant_action"]},
            {"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}},
        ]
        baseline_score = self.trace(base_run, base_events)

        res_run, res_skill, res_body = self.prepare("syn-resource")
        ref = json.loads((res_run / "manifest.json").read_text())["resources"][ref_id]
        ref_body = Path(ref["path"]).read_text()
        res_events = [
            {"type": "session.started"},
            {"type": "skill_read.request", "request_id": "s-1", "skill": "swe:implement", "path": res_skill["path"]},
            {"type": "skill_read.result", "request_id": "s-1", "exit_code": 0, "body": res_body, "body_complete": True},
            {"type": "resource_read.request", "request_id": "r-1", "resource": ref_id, "path": ref["path"]},
            {"type": "resource_read.result", "request_id": "r-1", "exit_code": 0, "body": ref_body, "body_complete": True},
            {"type": "action.started", "kind": self.case["relevant_action"]},
            {"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}},
        ]
        res_score = self.trace(res_run, res_events)
        res_ev = json.loads((res_run / "evidence.json").read_text())
        self.assertEqual(res_score["observed_resources"], [ref_id])
        self.assertEqual(res_ev["resource_reads"][0]["status"], "success")
        for key in ("activation", "timing", "observed_skills", "expected_skills", "allowed_skills",
                    "unresolved_skills", "false_activation", "unexpected_skills",
                    "load_status_counts", "evidence_coverage", "session_state"):
            self.assertEqual(res_score[key], baseline_score[key])

        child_run, child_skill, child_body = self.prepare("syn-child")
        child_events = [
            {"type": "session.started"},
            {"type": "session.started", "session_id": "child-1", "parent_session_id": "root"},
            {"type": "skill_read.request", "session_id": "child-1", "request_id": "c-1",
             "skill": "swe:implement", "path": child_skill["path"]},
            {"type": "skill_read.result", "session_id": "child-1", "request_id": "c-1",
             "exit_code": 0, "body": child_body, "body_complete": True},
            {"type": "action.started", "kind": self.case["relevant_action"]},
            {"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}},
        ]
        child_score = self.trace(child_run, child_events)
        child_ev = json.loads((child_run / "evidence.json").read_text())
        self.assertEqual(child_ev["loads"], [])
        self.assertEqual(len(child_ev["child_loads"]), 1)
        self.assertEqual(child_ev["child_loads"][0]["status"], "success")
        self.assertEqual(child_ev["child_loads"][0]["session_id"], "child-1")
        self.assertEqual(child_score["activation"]["swe:implement"], "miss")
        self.assertEqual(child_score["timing"]["swe:implement"], "unavailable")
        self.assertEqual(child_score["observed_skills"], [])
        self.assertEqual(child_score["child_observed_skills"], ["swe:implement"])

        for name, complete, code, expected_status in (
            ("syn-res-partial", False, 0, "partial"),
            ("syn-res-failed", True, 1, "failed"),
        ):
            with self.subTest(name=name):
                run, _, _ = self.prepare(name)
                ref = json.loads((run / "manifest.json").read_text())["resources"][ref_id]
                ref_body = Path(ref["path"]).read_text()
                score = self.trace(run, [
                    {"type": "session.started"},
                    {"type": "resource_read.request", "request_id": "r-1", "resource": ref_id, "path": ref["path"]},
                    {"type": "resource_read.result", "request_id": "r-1", "exit_code": code,
                     "body": ref_body, "body_complete": complete},
                    {"type": "action.started", "kind": self.case["relevant_action"]},
                    {"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}},
                ])
                ev = json.loads((run / "evidence.json").read_text())
                self.assertEqual(ev["resource_reads"][0]["status"], expected_status)
                self.assertEqual(score["observed_resources"], [])

        other_run, other_skill, other_body = self.prepare("syn-other-parent")
        other_ref = json.loads((other_run / "manifest.json").read_text())["resources"][ref_id]
        other_ref_body = Path(other_ref["path"]).read_text()
        other_score = self.trace(other_run, [
            {"type": "session.started"},
            {"type": "session.started", "session_id": "other-child", "parent_session_id": "other-root"},
            {"type": "skill_read.request", "session_id": "other-child", "request_id": "o-1",
             "skill": "swe:implement", "path": other_skill["path"]},
            {"type": "skill_read.result", "session_id": "other-child", "request_id": "o-1",
             "exit_code": 0, "body": other_body, "body_complete": True},
            {"type": "resource_read.request", "session_id": "other-child", "request_id": "o-2",
             "resource": ref_id, "path": other_ref["path"]},
            {"type": "resource_read.result", "session_id": "other-child", "request_id": "o-2",
             "exit_code": 0, "body": other_ref_body, "body_complete": True},
            {"type": "action.started", "kind": self.case["relevant_action"]},
            {"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}},
        ])
        other_ev = json.loads((other_run / "evidence.json").read_text())
        for field in ("loads", "child_loads", "resource_reads", "child_resource_reads", "unproved_reads"):
            self.assertEqual(other_ev[field], [])
        self.assertEqual(other_score["observed_skills"], [])
        self.assertEqual(other_score["child_observed_skills"], [])
        self.assertEqual(other_score["observed_resources"], [])
        self.assertEqual(other_score["child_observed_resources"], [])

        shared_run, shared_skill, shared_body = self.prepare("syn-shared-reqid")
        shared_score = self.trace(shared_run, [
            {"type": "session.started"},
            {"type": "session.started", "session_id": "child-1", "parent_session_id": "root"},
            {"type": "skill_read.request", "request_id": "shared-1",
             "skill": "swe:implement", "path": shared_skill["path"]},
            {"type": "skill_read.request", "session_id": "child-1", "request_id": "shared-1",
             "skill": "swe:implement", "path": shared_skill["path"]},
            {"type": "skill_read.result", "request_id": "shared-1",
             "exit_code": 0, "body": shared_body, "body_complete": True},
            {"type": "skill_read.result", "session_id": "child-1", "request_id": "shared-1",
             "exit_code": 0, "body": shared_body, "body_complete": True},
            {"type": "action.started", "kind": self.case["relevant_action"]},
            {"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}},
        ])
        shared_ev = json.loads((shared_run / "evidence.json").read_text())
        self.assertEqual(len(shared_ev["loads"]), 1)
        self.assertEqual(shared_ev["loads"][0]["status"], "success")
        self.assertEqual(shared_ev["loads"][0]["session_id"], "root")
        self.assertEqual(len(shared_ev["child_loads"]), 1)
        self.assertEqual(shared_ev["child_loads"][0]["status"], "success")
        self.assertEqual(shared_ev["child_loads"][0]["session_id"], "child-1")
        self.assertEqual(shared_score["observed_skills"], ["swe:implement"])
        self.assertEqual(shared_score["child_observed_skills"], ["swe:implement"])

    def test_hook_arm_materialize_score_and_aggregate(self):
        off_run, off_skill, off_body = self.prepare("arm-off")
        off_manifest = json.loads((off_run / "manifest.json").read_text())
        self.assertEqual(off_manifest["hook_arm"], "hook-off")
        self.assertNotIn("hooks", off_manifest)
        self.assertTrue(any("rules/AGENTS.md" in d for d in off_manifest["known_deltas"]))
        for plugin in ("swe", "lab", "uni"):
            self.assertFalse((off_run / "inputs" / "plugins" / plugin / "hooks").exists())
            self.assertTrue((off_run / "inputs" / "plugins" / plugin / "rules" / "AGENTS.md").is_file())
        self.assertEqual(off_manifest["removed_bindings"], [
            "plugins/lab/hooks",
            "plugins/swe/hooks",
            "plugins/uni/hooks",
        ])

        on_run, on_skill, on_body = self.prepare("arm-on", hook_arm="hook-on")
        on_manifest = json.loads((on_run / "manifest.json").read_text())
        self.assertEqual(on_manifest["hook_arm"], "hook-on")
        self.assertEqual(set(on_manifest["hooks"]), {"lab", "swe", "uni"})
        self.assertTrue(any("rules/AGENTS.md" in d for d in on_manifest["known_deltas"]))
        for plugin in ("swe", "lab", "uni"):
            hooks_dir = on_run / "inputs" / "plugins" / plugin / "hooks"
            self.assertEqual(sorted(p.name for p in hooks_dir.iterdir()), ["hooks.json", "session-start.md"])
            hooks_cfg = json.loads((hooks_dir / "hooks.json").read_text())["hooks"]
            self.assertEqual(list(hooks_cfg), ["SessionStart"])
        self.assertEqual(on_manifest["removed_bindings"], [
            "plugins/swe/hooks/hooks.json:PostCompact",
            "plugins/swe/hooks/hooks.json:PreToolUse",
        ])

        swe_hook_text = Path(on_manifest["hooks"]["swe"]["path"]).read_text()
        on_score = self.trace(on_run, [
            {"type": "session.started"},
            {"type": "hook.delivered", "plugin": "swe", "body": swe_hook_text},
            {"type": "skill_read.request", "request_id": "s-1", "skill": "swe:implement", "path": on_skill["path"]},
            {"type": "skill_read.result", "request_id": "s-1", "exit_code": 0, "body": on_body, "body_complete": True},
            {"type": "action.started", "kind": self.case["relevant_action"]},
            {"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}},
        ])
        on_ev = json.loads((on_run / "evidence.json").read_text())
        self.assertEqual(on_score["hook_arm"], "hook-on")
        self.assertEqual(on_score["evidence_coverage"], "complete")
        self.assertEqual(on_score["activation"]["swe:implement"], "loaded")
        self.assertEqual(len(on_ev["hook_deliveries"]), 1)
        self.assertEqual(on_ev["hook_deliveries"][0]["status"], "success")
        self.assertEqual(on_ev["hook_deliveries"][0]["sha256"], on_manifest["hooks"]["swe"]["sha256"])

        off_score = self.trace(off_run, [
            {"type": "session.started"},
            {"type": "skill_read.request", "request_id": "s-1", "skill": "swe:implement", "path": off_skill["path"]},
            {"type": "skill_read.result", "request_id": "s-1", "exit_code": 0, "body": off_body, "body_complete": True},
            {"type": "action.started", "kind": self.case["relevant_action"]},
            {"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}},
        ])
        self.assertEqual(off_score["hook_arm"], "hook-off")
        self.assertNotEqual(off_score["configuration_sha256"], on_score["configuration_sha256"])

        report = self.cli("aggregate", off_run / "score.json", on_run / "score.json")
        self.assertEqual(len(report["groups"]), 2)
        self.assertEqual({g["hook_arm"] for g in report["groups"]}, {"hook-off", "hook-on"})

        neg_case = next(c for c in json.loads((HERE / "cases.json").read_text())["cases"]
                        if c["target"] == "swe:implement" and c["category"] == "negative" and c["expected_skills"])
        neg_scores = []
        for arm in ("hook-off", "hook-on"):
            neg_run, neg_skill, neg_body = self.prepare("arm-neg-" + arm, neg_case, hook_arm=arm)
            neg_scores.append(self.trace(neg_run, [
                {"type": "session.started"},
                {"type": "skill_read.request", "request_id": "n-1", "skill": "swe:implement", "path": neg_skill["path"]},
                {"type": "skill_read.result", "request_id": "n-1", "exit_code": 0, "body": neg_body, "body_complete": True},
                {"type": "action.started", "kind": neg_case["relevant_action"]},
                {"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}},
            ]))
            self.assertEqual(neg_scores[-1]["hook_arm"], arm)
        conf_report = self.cli("aggregate",
                               self.root / "arm-neg-hook-off" / "score.json",
                               self.root / "arm-neg-hook-on" / "score.json")
        self.assertEqual(len(conf_report["confusion"]), 2)
        self.assertEqual({c["hook_arm"] for c in conf_report["confusion"]}, {"hook-off", "hook-on"})

        bad_on, _, _ = self.prepare("syn-hook-mismatch", hook_arm="hook-on")
        bad_on_score = self.trace(bad_on, [
            {"type": "session.started"},
            {"type": "hook.delivered", "plugin": "swe", "body": "tampered\n"},
            {"type": "action.started", "kind": self.case["relevant_action"]},
            {"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}},
        ])
        bad_on_ev = json.loads((bad_on / "evidence.json").read_text())
        self.assertEqual(bad_on_ev["hook_deliveries"][0]["status"], "mismatch")
        self.assertTrue(bad_on_ev["issues"])
        self.assertEqual(bad_on_score["evidence_coverage"], "partial")

        bad_off, _, _ = self.prepare("syn-hook-in-off")
        bad_off_score = self.trace(bad_off, [
            {"type": "session.started"},
            {"type": "hook.delivered", "plugin": "swe", "body": swe_hook_text},
            {"type": "action.started", "kind": self.case["relevant_action"]},
            {"type": "session.completed", "coverage": {"skill_delivery": True, "relevant_actions": True}},
        ])
        bad_off_ev = json.loads((bad_off / "evidence.json").read_text())
        self.assertTrue(bad_off_ev["issues"])
        self.assertEqual(bad_off_score["evidence_coverage"], "partial")

    def test_claude_hook_delivery_proof_and_isolation(self):
        def make_skill_and_edit(skill, text):
            body = ("Base directory for this skill: " + str(Path(skill["path"]).parent) + "\n\n"
                    + text.split("\n---\n", 1)[1].lstrip("\n"))
            return [
                ("call", "message-skill", "use-skill", {"name": "Skill", "input": {"skill": "swe:implement"}}),
                ("result", None, "use-skill", {"success": True, "commandName": "swe:implement"}),
                ("body", None, "use-skill", body),
                ("call", "message-edit", "use-edit", {"name": "Edit", "input": {"file_path": "calc.py"}}),
                ("result", None, "use-edit", {"filePath": "calc.py"}),
            ]

        def hook_att(stdout, hook_type="hook_success"):
            return {
                "type": hook_type,
                "hookName": "SessionStart:startup",
                "hookEvent": "SessionStart",
                "toolUseID": "hook-1",
                "content": stdout.rstrip("\n") if hook_type == "hook_success" else [stdout],
                "stdout": stdout,
                "stderr": "",
                "exitCode": 0,
                "command": "cat \"$CLAUDE_PLUGIN_ROOT\"/hooks/session-start.md",
                "durationMs": 12,
            }

        ok_run, ok_skill, ok_text = self.prepare("claude-hook-ok", hook_arm="hook-on")
        ok_manifest = json.loads((ok_run / "manifest.json").read_text())
        swe_stdout = Path(ok_manifest["hooks"]["swe"]["path"]).read_text()
        lab_stdout = Path(ok_manifest["hooks"]["lab"]["path"]).read_text()
        ok_score = self.claude_trace(
            ok_run,
            make_skill_and_edit(ok_skill, ok_text),
            "use-edit",
            hook_rows=[hook_att(swe_stdout), hook_att(lab_stdout)],
            plugin_dirs=[ok_run / "inputs" / "plugins" / "swe", ok_run / "inputs" / "plugins" / "lab"],
        )
        ok_ev = json.loads((ok_run / "evidence.json").read_text())
        self.assertEqual(ok_score["hook_arm"], "hook-on")
        self.assertEqual(ok_score["evidence_coverage"], "complete")
        self.assertEqual(ok_score["activation"]["swe:implement"], "loaded")
        self.assertTrue(ok_ev["coverage"]["start"])
        self.assertEqual(ok_ev["issues"], [])
        self.assertEqual([(d["plugin"], d["status"]) for d in ok_ev["hook_deliveries"]],
                         [("swe", "success"), ("lab", "success")])
        self.assertEqual(ok_ev["hook_deliveries"][0]["sha256"], ok_manifest["hooks"]["swe"]["sha256"])

        off_run, off_skill, off_text = self.prepare("claude-hook-in-off")
        off_score = self.claude_trace(
            off_run,
            make_skill_and_edit(off_skill, off_text),
            "use-edit",
            hook_rows=[hook_att(swe_stdout)],
        )
        off_ev = json.loads((off_run / "evidence.json").read_text())
        self.assertEqual(off_score["evidence_coverage"], "partial")
        self.assertFalse(off_ev["coverage"]["start"])
        self.assertTrue(any("hook-off" in issue for issue in off_ev["issues"]))

        mismatch_run, mismatch_skill, mismatch_text = self.prepare("claude-hook-mismatch", hook_arm="hook-on")
        mismatch_score = self.claude_trace(
            mismatch_run,
            make_skill_and_edit(mismatch_skill, mismatch_text),
            "use-edit",
            hook_rows=[hook_att("swe: altered hook body\n")],
        )
        mismatch_ev = json.loads((mismatch_run / "evidence.json").read_text())
        self.assertEqual(mismatch_score["evidence_coverage"], "partial")
        self.assertIsNone(mismatch_ev["hook_deliveries"][0]["plugin"])
        self.assertEqual(mismatch_ev["hook_deliveries"][0]["status"], "mismatch")
        self.assertTrue(any("no hook_success delivery row" in issue for issue in mismatch_ev["issues"]))

        dup_run, dup_skill, dup_text = self.prepare("claude-hook-dup", hook_arm="hook-on")
        dup_score = self.claude_trace(
            dup_run,
            make_skill_and_edit(dup_skill, dup_text),
            "use-edit",
            hook_rows=[hook_att(swe_stdout), hook_att(swe_stdout)],
        )
        dup_ev = json.loads((dup_run / "evidence.json").read_text())
        self.assertEqual(dup_score["evidence_coverage"], "partial")
        self.assertEqual([(d["plugin"], d["status"]) for d in dup_ev["hook_deliveries"]],
                         [("swe", "success"), ("swe", "success")])
        self.assertTrue(any("duplicate hook delivery for swe" in issue for issue in dup_ev["issues"]))

        late_run, late_skill, late_text = self.prepare("claude-hook-after-user", hook_arm="hook-on")
        late_score = self.claude_trace(
            late_run,
            [("attachment", None, None, hook_att(swe_stdout))] + make_skill_and_edit(late_skill, late_text),
            "use-edit",
            hook_rows=[hook_att(swe_stdout)],
        )
        late_ev = json.loads((late_run / "evidence.json").read_text())
        self.assertEqual(late_score["evidence_coverage"], "partial")
        self.assertEqual(len(late_ev["hook_deliveries"]), 1)
        self.assertTrue(any("outside leading start run" in issue for issue in late_ev["issues"]))

        nonnull_run, nonnull_skill, nonnull_text = self.prepare("claude-hook-nonnull-parent", hook_arm="hook-on")
        nonnull_score = self.claude_trace(
            nonnull_run,
            make_skill_and_edit(nonnull_skill, nonnull_text),
            "use-edit",
            hook_rows=[hook_att(swe_stdout)],
            hook_parent="stray-parent",
        )
        nonnull_ev = json.loads((nonnull_run / "evidence.json").read_text())
        self.assertEqual(nonnull_score["evidence_coverage"], "partial")
        self.assertFalse(nonnull_ev["coverage"]["start"])

        uni_stdout = Path(ok_manifest["hooks"]["uni"]["path"]).read_text()
        undecl_run, undecl_skill, undecl_text = self.prepare("claude-hook-undeclared", hook_arm="hook-on")
        undecl_score = self.claude_trace(
            undecl_run,
            make_skill_and_edit(undecl_skill, undecl_text),
            "use-edit",
            hook_rows=[hook_att(swe_stdout), hook_att(uni_stdout)],
        )
        undecl_ev = json.loads((undecl_run / "evidence.json").read_text())
        self.assertEqual(undecl_score["evidence_coverage"], "partial")
        self.assertEqual([(d["plugin"], d["status"]) for d in undecl_ev["hook_deliveries"]],
                         [("swe", "success"), (None, "mismatch")])
        self.assertTrue(any("does not match any declared plugin" in issue for issue in undecl_ev["issues"]))

        tamper_run, _, _ = self.prepare("claude-hook-tamper", hook_arm="hook-on")
        tampered_dir = self.root / "tampered-hook-swe"
        shutil.copytree(tamper_run / "inputs" / "plugins" / "swe", tampered_dir)
        (tampered_dir / "hooks" / "session-start.md").write_text("tampered\n")
        tamper_source = self.root / "tamper-hook.jsonl"
        tamper_source.write_text("")
        tamper_err = self.cli("capture", "--run", tamper_run, "--source", tamper_source, "--state", "incomplete",
                              "--format", "claude-transcript", "--plugin-dir", tampered_dir, ok=False)
        self.assertIn("hook does not match the frozen catalog", tamper_err.stderr)
        self.assertIn("hooks/session-start.md", tamper_err.stderr)

        missing_run, missing_skill, missing_text = self.prepare("claude-hook-missing", hook_arm="hook-on")
        missing_score = self.claude_trace(
            missing_run,
            make_skill_and_edit(missing_skill, missing_text),
            "use-edit",
        )
        missing_ev = json.loads((missing_run / "evidence.json").read_text())
        self.assertEqual(missing_score["evidence_coverage"], "partial")
        self.assertEqual(missing_ev["hook_deliveries"], [])
        self.assertTrue(any("no hook_success delivery row" in issue for issue in missing_ev["issues"]))

        for arm in ("hook-off", "hook-on"):
            ctx_run, ctx_skill, ctx_text = self.prepare("claude-hook-ctx-" + arm, hook_arm=arm)
            ctx_score = self.claude_trace(
                ctx_run,
                make_skill_and_edit(ctx_skill, ctx_text),
                "use-edit",
                hook_rows=[hook_att("extra context", hook_type="hook_additional_context")],
            )
            ctx_ev = json.loads((ctx_run / "evidence.json").read_text())
            self.assertEqual(ctx_score["evidence_coverage"], "partial")
            self.assertTrue(any("hook_additional_context" in issue for issue in ctx_ev["issues"]))


if __name__ == "__main__":
    unittest.main()
