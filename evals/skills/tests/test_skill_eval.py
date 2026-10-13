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
"""
from __future__ import annotations

import json
from pathlib import Path
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

    def prepare(self, name, case=None):
        run = self.root / name
        self.cli("materialize", "--case", (case or self.case)["id"], "--runtime", HERE / "runtime.offline.json", "--output", run)
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

    def claude_trace(self, run, steps, relevant):
        """Write a minimal transcript in the audited Claude Code shape (EVIDENCE.md) and score it."""
        lines, sid = [], "claude-session"

        def add(row):
            row = {"uuid": f"line-{len(lines)}", "parentUuid": lines[-1]["uuid"] if lines else None,
                   "sessionId": sid, "isSidechain": False, **row}
            lines.append(row)

        add({"type": "user", "message": {"role": "user", "content": "rename it"}})
        for kind, message_id, tool_use_id, payload in steps:
            if kind == "call":
                add({"type": "assistant", "message": {"id": message_id, "content": [
                    {"type": "tool_use", "id": tool_use_id, "name": payload["name"], "input": payload["input"]}]}})
            elif kind == "result":
                add({"type": "user", "toolUseResult": payload, "message": {"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": tool_use_id, "content": "ok"}]}})
            else:
                add({"type": "user", "isMeta": True, "sourceToolUseID": tool_use_id, "message": {
                    "role": "user", "content": [{"type": "text", "text": payload}]}})
        source = self.root / (run.name + ".jsonl")
        source.write_text("".join(json.dumps(row) + "\n" for row in lines)
                          + json.dumps({"type": "cost-state", "sessionId": sid}) + "\n")
        stream = self.root / (run.name + ".stream.jsonl")
        stream.write_text(json.dumps({"type": "result", "subtype": "success", "is_error": False, "session_id": sid}) + "\n")
        self.cli("capture", "--run", run, "--source", source, "--state", "completed", "--format", "claude-transcript",
                 "--plugin-dir", run / "inputs" / "plugins" / "swe", "--stream", stream, "--relevant-action", relevant)
        return self.cli("score", "--run", run)

    def test_claude_transcript_load_proof_and_action_order(self):
        # Shapes come from the audited probe traces; see EVIDENCE.md "Claude transcript audit".
        # Values: evidence coverage, then activation and timing of swe:implement.
        unresolved = ("complete", "unavailable", "unavailable")
        expected = {"skill-body": ("complete", "loaded", "before"), "skill-without-body": unresolved,
                    "skill-in-action-message": ("complete", "loaded", "late"), "full-read": ("complete", "loaded", "before"),
                    "sliced-read": unresolved, "bare-name-without-body": unresolved,
                    "name-differs-from-body": ("partial", "unavailable", "unavailable")}
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
                read_call = [("call", "message-read", "use-read", {"name": "Read", "input": {"file_path": skill["path"]}})]
                shown = len(lines) if name == "full-read" else 3
                read_result = [("result", None, "use-read", {"type": "text", "file": {
                    "filePath": skill["path"], "content": text if name == "full-read" else "\n".join(lines[:3]),
                    "startLine": 1, "numLines": shown, "totalLines": len(lines)}})]
                steps = {"skill-body": skill_call + [("body", None, "use-skill", body)],
                         "skill-without-body": skill_call, "bare-name-without-body": skill_call,
                         "name-differs-from-body": skill_call + [("body", None, "use-skill", body)],
                         "skill-in-action-message": skill_call + [("body", None, "use-skill", body)],
                         "full-read": read_call + read_result, "sliced-read": read_call + read_result}[name]
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


if __name__ == "__main__":
    unittest.main()
