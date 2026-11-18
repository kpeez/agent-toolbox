"""Plugin-eval adapter contract checks. A stub `claude` replaces the CLI; no model is invoked.

Admission: protects the spend and evidence promises of `run_eval.py` at its CLI. The credible
regressions are a rerun that launches finished runs again, a launch past the total budget, a run
over the per-run cost that does not stop the batch, a session that breaks the frozen runtime but is
scored, a hook-off arm that still carries hooks, final files taken from the fixture instead of the
agent's working folder, and a stream whose added final newline goes unrecorded.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SCRIPT = HERE / "run_eval.py"
sys.path.insert(0, str(HERE))
import skill_eval as se

STUB = r'''#!/usr/bin/env python3
"""Stub of `claude --version` and `claude plugin eval` that writes a kept sandbox like the real CLI."""
import json, os, secrets, subprocess, sys
from pathlib import Path

argv = sys.argv[1:]
if argv == ["--version"]:
    print("2.1.327 (Claude Code)")
    sys.exit(0)
with open(os.environ["STUB_LOG"], "a") as log:
    log.write(json.dumps({"argv": argv, "effort": os.environ.get("CLAUDE_CODE_EFFORT_LEVEL")}) + "\n")
suite = Path(argv[2])
case = argv[argv.index("--case") + 1]
cost = float(os.environ.get("STUB_COST", "0.1"))
tools = json.loads(os.environ.get("STUB_TOOLS", '["Edit","Glob","Grep","Read","Skill","Write"]'))
kept = Path(os.environ["STUB_TMP"]) / ("e-" + secrets.token_hex(4))
cwd = kept / "sealed" / "home" / "cwd"
cwd.mkdir(parents=True)
subprocess.run(["bash", str(suite / "evals" / case / "fixture.sh")], cwd=cwd, check=True)
(cwd / "agent-wrote.txt").write_text("changed by the agent\n")
sid = "stub-session"
plugins = ["swe", "lab", "uni"]
hooks = [p for p in plugins if (suite / p / "hooks" / "session-start.md").is_file()]
rows = []
def add(row):
    rows.append({"uuid": f"u{len(rows)}", "parentUuid": rows[-1]["uuid"] if rows else None, "sessionId": sid,
                 "isSidechain": False, **row})
for p in hooks:
    text = (suite / p / "hooks" / "session-start.md").read_text()
    add({"type": "attachment", "attachment": {"type": "hook_success", "hookName": "SessionStart:startup",
         "hookEvent": "SessionStart", "toolUseID": "hook-" + p, "content": text.rstrip("\n"), "stdout": text,
         "stderr": "", "exitCode": 0}})
add({"type": "user", "message": {"role": "user", "content": "do it"}})
skill = suite / "swe" / "skills" / "implement" / "SKILL.md"
body = skill.read_text().split("\n---\n", 1)[1].lstrip("\n")
add({"type": "assistant", "message": {"id": "m1", "content": [
    {"type": "tool_use", "id": "use-skill", "name": "Skill", "input": {"skill": "swe:implement"}}]}})
add({"type": "user", "toolUseResult": {"success": True, "commandName": "swe:implement"}, "message": {
    "role": "user", "content": [{"type": "tool_result", "tool_use_id": "use-skill", "content": "ok"}]}})
add({"type": "user", "isMeta": True, "sourceToolUseID": "use-skill", "message": {"role": "user", "content": [
    {"type": "text", "text": "Base directory for this skill: " + str(skill.parent) + "\n\n" + body}]}})
add({"type": "assistant", "message": {"id": "m2", "content": [
    {"type": "tool_use", "id": "use-edit", "name": "Edit", "input": {"file_path": "importer.py"}}]}})
add({"type": "user", "toolUseResult": {"filePath": "importer.py"}, "message": {
    "role": "user", "content": [{"type": "tool_result", "tool_use_id": "use-edit", "content": "ok"}]}})
add({"type": "assistant", "message": {"id": "m3", "content": [{"type": "text", "text": "Done."}]}})
project = kept / "config" / "projects" / "-stub"
project.mkdir(parents=True)
meta = [{"type": "api-request-shape", "sessionId": sid, "effort": os.environ.get("STUB_EFFORT", "high")}]
(project / (sid + ".jsonl")).write_text("".join(json.dumps(r) + "\n" for r in rows + meta))
events = [{"type": "system", "subtype": "init", "model": argv[argv.index("--model") + 1], "tools": tools,
           "claude_code_version": os.environ.get("STUB_CLI", "2.1.327"),
           "plugins": [{"name": p} for p in plugins + ["cc-plugin-privacy"]], "mcp_servers": [], "session_id": sid}]
for p in hooks:
    events += [{"type": "system", "subtype": "hook_started", "hook_id": p, "hook_name": "SessionStart:startup"},
               {"type": "system", "subtype": "hook_response", "hook_id": p, "hook_name": "SessionStart:startup",
                "outcome": "success", "output": (suite / p / "hooks" / "session-start.md").read_text()}]
events.append({"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": cost, "session_id": sid})
(kept / "out").mkdir()
(kept / "out" / "trace.jsonl").write_text("\n".join(json.dumps(e) for e in events))
Path(argv[argv.index("--json") + 1]).write_text(json.dumps({"costUsd": cost, "cases": [{"name": case, "arms": {
    "with": [{"costUsd": cost, "error": None, "turns": 3, "tracePath": str(kept / "out" / "trace.jsonl")}]}}]}))
print(f"kept {kept}: home/ and tmp/ in it were written by the plugin under test")
'''


class PluginEvalAdapter(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="adapter-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        stub = self.root / "claude"
        stub.write_text(STUB)
        stub.chmod(0o755)
        (self.root / "tmp").mkdir()
        self.log = self.root / "stub.jsonl"
        self.env = os.environ | {
            "SKILL_EVAL_CLAUDE": str(stub),
            "STUB_LOG": str(self.log),
            "STUB_TMP": str(self.root / "tmp"),
        }
        self.out = self.root / "out"

    def cli(self, *args, code=0, **env):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            text=True,
            capture_output=True,
            env=self.env | env,
            cwd=se.REPO,
        )
        self.assertEqual(result.returncode, code, result.stderr + result.stdout)
        return result

    def run_eval(self, *extra, code=0, cases=("IM-01",), **env):
        case_args = [arg for case in cases for arg in ("--case", case)]
        return self.cli("run", *case_args, "--out", self.out, *extra, code=code, **env)

    def launches(self):
        return (
            [json.loads(line) for line in self.log.read_text().splitlines()]
            if self.log.exists()
            else []
        )

    def test_run_keeps_the_session_and_score_reads_it(self):
        self.run_eval("--max-total-usd", "5")
        calls = self.launches()
        self.assertEqual(len(calls), 2)
        for call in calls:
            argv = call["argv"]
            self.assertEqual(call["effort"], "high")
            self.assertEqual(
                argv[argv.index("--disallow-tools") + 1 : argv.index("--max-cost-usd")],
                ["Task", "TaskStop", "NotebookEdit", "ToolSearch"],
            )
            self.assertEqual(
                argv[argv.index("--allow-tools") + 1 : argv.index("--disallow-tools")],
                ["Write", "Edit"],
            )
            self.assertIn("--keep-temp", argv)
        for arm in ("hook-on", "hook-off"):
            run = self.out / "runs" / "IM-01" / arm / "r1"
            record = json.loads((run / "run.json").read_text())
            self.assertEqual(record["violations"], [])
            self.assertTrue(record["stream_appended_final_newline"])
            self.assertTrue(
                (run / "kept" / "stream.jsonl").read_bytes().endswith(b"\n")
            )
            self.assertEqual(
                (run / "workspace" / "agent-wrote.txt").read_text(),
                "changed by the agent\n",
            )
            self.assertEqual(
                (run / "suite" / "swe" / "hooks").exists(), arm == "hook-on"
            )
            self.assertEqual(list((self.root / "tmp").iterdir()), [])
            case_yaml = (run / "suite" / "evals" / "IM-01" / "case.yaml").read_text()
            prompt = (run / "inputs" / "prompt.txt").read_text().rstrip("\n")
            self.assertIn(
                "  prompt: " + json.dumps(prompt, ensure_ascii=False) + "\n", case_yaml
            )
        labels = self.root / "labels.jsonl"
        labels.write_text(
            "".join(
                json.dumps(
                    {
                        "case": "IM-01",
                        "arm": arm,
                        "repeat": 1,
                        "tool_use_id": "use-edit",
                    }
                )
                + "\n"
                for arm in ("hook-on", "hook-off")
            )
        )
        report = json.loads(
            self.cli("score", "--out", self.out, "--labels", labels).stdout
        )
        self.assertEqual((report["runs_scored"], report["runs_labeled"]), (2, 2))
        for arm in ("hook-on", "hook-off"):
            run = self.out / "runs" / "IM-01" / arm / "r1"
            capture = json.loads((run / "capture.json").read_text())
            self.assertTrue(capture["stream"]["appended_final_newline"])
            self.assertIn("agent-wrote.txt", capture["final_files"])
            score = json.loads((run / "score.json").read_text())
            self.assertEqual(
                (
                    score["evidence_coverage"],
                    score["activation"]["swe:implement"],
                    score["timing"]["swe:implement"],
                ),
                ("complete", "loaded", "before"),
                arm,
            )
        groups = json.loads((self.out / "report.json").read_text())["aggregate"][
            "groups"
        ]
        self.assertEqual(sorted(g["recall_interval"]["n"] for g in groups), [1, 1])
        self.cli("score", "--out", self.out, "--labels", labels)

    def test_rerun_skips_finished_runs_and_relaunches_an_interrupted_one(self):
        self.run_eval("--max-total-usd", "5", "--arms", "hook-off")
        self.run_eval("--max-total-usd", "5", "--arms", "hook-off")
        self.assertEqual(len(self.launches()), 1)
        record = self.out / "runs" / "IM-01" / "hook-off" / "r1" / "run.json"
        record.write_text(json.dumps({"started_at": "x", "cost_usd": None}))
        self.run_eval("--max-total-usd", "5", "--arms", "hook-off")
        self.assertEqual(len(self.launches()), 2)
        aside = list((self.out / "interrupted").glob("*/run.json"))
        self.assertEqual(len(aside), 1)
        spend = json.loads(
            self.run_eval("--max-total-usd", "5", "--arms", "hook-off").stdout
        )["spend"]
        self.assertEqual(spend["unknown_cost_runs"], 1)
        self.assertAlmostEqual(spend["worst_case_usd"], 0.1 + 1.0)

    def test_budget_refuses_a_launch_whose_worst_case_passes_the_total(self):
        result = json.loads(self.run_eval("--max-total-usd", "0.5", code=3).stdout)
        self.assertEqual(self.launches(), [])
        self.assertIn("budget", result["stopped"]["reason"])

    def test_a_run_over_the_per_run_cost_stops_the_batch(self):
        result = json.loads(
            self.run_eval("--max-total-usd", "10", code=3, STUB_COST="1.5").stdout
        )
        self.assertEqual(len(self.launches()), 1)
        self.assertIn("over $1.0", result["stopped"]["reason"])
        self.run_eval("--max-total-usd", "10", code=3)
        self.assertEqual(len(self.launches()), 1)

    def test_a_session_that_breaks_the_frozen_runtime_stops_the_batch_and_is_not_scored(
        self,
    ):
        for env, message in (
            (
                {"STUB_TOOLS": '["Bash","Edit","Glob","Grep","Read","Skill","Write"]'},
                "tools are",
            ),
            ({"STUB_EFFORT": "medium"}, "effort"),
            ({"STUB_CLI": "2.1.999"}, "claude_code_version"),
        ):
            with self.subTest(message=message):
                self.out = self.root / ("out-" + message.split()[0])
                result = json.loads(
                    self.run_eval("--max-total-usd", "10", code=3, **env).stdout
                )
                self.assertIn(message, result["stopped"]["reason"])
                report = json.loads(self.cli("score", "--out", self.out).stdout)
                self.assertEqual(report["runs_scored"], 0)
                self.assertEqual(report["skipped"][0]["reason"], "violations")

    def test_parallel_runs_are_counted_once_while_in_flight(self):
        # 8 runs at $0.10 with 4 at once: the worst case before any launch is at most 0.7 + 4 * 1.0 = 4.7.
        cases = ("IM-01", "IM-02", "IM-03", "IM-04")
        result = json.loads(self.run_eval("--max-total-usd", "5", "--jobs", "4", cases=cases).stdout)
        self.assertIsNone(result["stopped"])
        self.assertEqual((len(self.launches()), result["finished"]), (8, 8))

    def test_a_runner_timeout_scores_as_a_timeout(self):
        sys.path.insert(0, str(HERE))
        import run_eval
        stream = self.root / "stream.jsonl"
        stream.write_text("")
        self.assertEqual(run_eval.session_state({"error": "plugin eval did not exit in time"}, stream), "timeout")
        self.assertEqual(run_eval.session_state({"error": "timed out after 900s"}, stream), "timeout")

    def test_a_different_configuration_needs_a_new_output_folder(self):
        self.run_eval("--max-total-usd", "5", "--arms", "hook-off")
        result = self.run_eval(
            "--max-total-usd", "5", "--arms", "hook-off", cases=("IM-02",), code=2
        )
        self.assertIn("froze a different configuration", result.stderr)


if __name__ == "__main__":
    unittest.main()
