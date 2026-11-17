"""Native runner contract checks. A stub `claude` on PATH replaces the model; no provider is invoked.

Admission: protects the spend and isolation promises of `run_eval.py` at its CLI. The credible
regressions are a dry run that launches the model, a rerun that launches finished runs again, a cost
cap checked after the launch or one that counts unknown cost as zero, a configuration the CLI cannot
confine that runs anyway, and a session whose effective tools break a declared limit. Owner: no other
test reaches the runner. Each was seen red under one mutation of run_eval.py (see the PR body).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
SCRIPT = HERE / "run_eval.py"

STUB = textwrap.dedent('''\
    import json, os, sys
    from pathlib import Path

    argv = sys.argv[1:]
    HERE = Path(__file__).parent
    config = json.loads((HERE / "config.json").read_text()) if (HERE / "config.json").exists() else {}
    with open(HERE / "calls.jsonl", "a") as log:
        log.write(json.dumps({"argv": argv, "cwd": os.getcwd()}) + "\\n")
    HELP = """Options:
      -p, --print                           Print response and exit
      --output-format <format>              Output format
      --verbose                             Override the verbose setting
      --session-id <uuid>                   Use a specific session ID
      --model <model>                       Model for the current session.
      --effort <level>                      Effort level for the current session
                                            (low, medium, high, xhigh, max)
      --setting-sources <sources>           Comma-separated list of setting sources
      --strict-mcp-config                   Only use MCP servers from --mcp-config
      --mcp-config <configs...>             Load MCP servers from JSON files
      --tools <tools...>                    Built-in tools to make available
      --allowedTools, --allowed-tools <tools...>
          Comma or space-separated list of tool names to allow
      --permission-mode <mode>              Permission mode to use for the session
                                            (choices: "acceptEdits", "dontAsk", "plan")
      --permission-prompts <target>         Who answers permission prompts
                                            (choices: "host", "none", default: "host")
      --max-budget-usd <amount>             Maximum dollar amount to spend
      --restricted                          Restricted mode
      --add-dir <directories...>            More directories Claude can access
      --plugin-dir <path>                   Load a plugin from a directory
    """
    home = os.environ.get("CLAUDE_CONFIG_DIR", "")
    if argv == ["--version"]:
        print("2.1.326 (Claude Code)")
    elif argv == ["--help"]:
        print(HELP)
    elif argv[:2] == ["plugin", "list"]:
        print("[]")
    elif argv[:2] == ["auth", "status"]:
        print(json.dumps({"loggedIn": "ANTHROPIC_API_KEY" in os.environ, "configDirectory": home,
                          "authMethod": "api_key", "apiKeySource": "ANTHROPIC_API_KEY"}))
    elif "-p" in argv:
        sid = argv[argv.index("--session-id") + 1]
        plugin = next(Path(a) for i, a in enumerate(argv) if argv[i - 1] == "--plugin-dir" and a.endswith("/swe"))
        skill = plugin / "skills" / "implement" / "SKILL.md"
        body = ("Base directory for this skill: " + str(skill.parent) + "\\n\\n"
                + skill.read_text().split("\\n---\\n", 1)[1].lstrip("\\n"))
        rows, parent = [], None
        def add(row):
            global parent
            row = {"uuid": "u%d" % len(rows), "parentUuid": parent, "sessionId": sid, "isSidechain": False, **row}
            parent = row["uuid"]
            rows.append(row)
        add({"type": "user", "message": {"role": "user", "content": "go"}})
        add({"type": "assistant", "message": {"id": "m1", "content": [
            {"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": "swe:implement"}}]}})
        add({"type": "user", "toolUseResult": {"success": True, "commandName": "swe:implement"},
              "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}})
        add({"type": "user", "isMeta": True, "sourceToolUseID": "t1",
              "message": {"role": "user", "content": [{"type": "text", "text": body}]}})
        add({"type": "assistant", "message": {"id": "m2", "content": [{"type": "text", "text": "done"}]}})
        target = Path(home) / "projects" / "p" / (sid + ".jsonl")
        target.parent.mkdir(parents=True)
        target.write_text("".join(json.dumps(r) + "\\n" for r in rows))
        tools = config.get("tools", ["Read", "Write", "Edit", "Glob", "Grep", "Skill"])
        print(json.dumps({"type": "system", "subtype": "init", "session_id": sid, "tools": tools, "mcp_servers": [],
                          "skills": ["swe:implement"], "model": "stub-model", "permissionMode": "dontAsk",
                          "claude_code_version": "2.1.326", "plugins": [], "memory_paths": {"auto": home + "/memory"}}))
        result = {"type": "result", "subtype": "success", "is_error": False, "session_id": sid, "num_turns": 2}
        if config.get("cost", 0.06) is not None:
            result["total_cost_usd"] = config.get("cost", 0.06)
        print(json.dumps(result))
    else:
        sys.exit("stub: unexpected argv %r" % argv)
    ''')


class NativeRunner(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="run-eval-")
        self.addCleanup(self.temp.cleanup)
        tmp = Path(self.temp.name)
        stub = tmp / "bin" / "claude"
        stub.parent.mkdir()
        script = stub.with_name("stub.py")
        script.write_text(STUB)
        stub.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
        stub.chmod(0o755)
        self.stub_dir = stub.parent
        self.log = stub.parent / "calls.jsonl"
        self.env = {
            "HOME": os.environ["HOME"],
            "PATH": f"{stub.parent}:/usr/bin:/bin",
            "ANTHROPIC_API_KEY": "stub",
        }
        self.runtime = json.loads((HERE / "runtime.native.json").read_text()) | {
            "model": "stub-model",
            "effort": "low",
            "approval": {"by": "test"},
            "max_budget_usd_per_run": 0.1,
        }
        self.pilot_id = "test-" + tmp.name.rsplit("-", 1)[-1]
        self.root = REPO / "artifacts" / "skill-evals" / self.pilot_id
        self.addCleanup(shutil.rmtree, self.root, True)

    def run_eval(self, *args, runtime=None, stub=None, execute=True):
        (self.stub_dir / "config.json").write_text(json.dumps(stub or {}))
        path = Path(self.temp.name) / "runtime.json"
        path.write_text(json.dumps(runtime or self.runtime))
        flags = [
            "--repeats",
            "1",
            "--runtime",
            str(path),
            "--case",
            "IM-01",
            "--pilot-id",
            self.pilot_id,
            *args,
        ]
        flags += ["--execute"] if execute else []
        return subprocess.run(
            [sys.executable, str(SCRIPT), *flags],
            text=True,
            capture_output=True,
            cwd=REPO,
            env=self.env,
            check=False,
        )

    def model_calls(self):
        calls = (
            [json.loads(line) for line in self.log.read_text().splitlines()]
            if self.log.exists()
            else []
        )
        return [c for c in calls if "-p" in c["argv"]]

    def records(self):
        return {
            p.parent.name: json.loads(p.read_text())
            for p in sorted(self.root.glob("runs/*/run.json"))
        }

    def test_dry_run_plans_and_preflights_but_launches_no_model(self):
        done = self.run_eval("--repeats", "2", "--max-cost-usd", "1", execute=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        plan = json.loads(done.stdout)
        self.assertEqual(plan["runs"]["planned"], 4)
        self.assertEqual(plan["blockers"], [])
        self.assertEqual(
            {c["check"]: c["status"] for c in plan["preflight"]}["confine-read"],
            "pending_live",
        )
        self.assertEqual(self.model_calls(), [])
        self.assertFalse(self.root.exists())

    def test_full_run_scores_each_arm_and_a_rerun_launches_nothing(self):
        first = self.run_eval("--max-cost-usd", "1")
        self.assertEqual(first.returncode, 0, first.stderr)
        summary = json.loads(first.stdout)
        self.assertEqual((summary["launched_now"], summary["skipped_finished"]), (2, 0))
        scores = {
            p.parent.name: json.loads(p.read_text())
            for p in self.root.glob("runs/*/score.json")
        }
        self.assertEqual(len(scores), 2)
        self.assertEqual(
            {s["hook_arm"] for s in scores.values()}, {"hook-on", "hook-off"}
        )
        off = next(s for s in scores.values() if s["hook_arm"] == "hook-off")
        self.assertEqual(off["activation"], {"swe:implement": "loaded"})
        self.assertFalse(
            any("IM-01" in name for name in scores),
            "run folders must not name the case",
        )
        self.assertEqual(next(iter(self.records().values()))["usage"]["cost_usd"], 0.06)
        group = summary["aggregate"]["groups"][0]
        self.assertEqual(group["counts"]["positive_unavailable"], 1)
        self.assertEqual((group["recall_denominator"], group["recall_interval"]), (0, None))
        second = self.run_eval("--max-cost-usd", "1")
        self.assertEqual(second.returncode, 0, second.stderr)
        summary = json.loads(second.stdout)
        self.assertEqual((summary["launched_now"], summary["skipped_finished"]), (0, 2))
        self.assertEqual(len(self.model_calls()), 2)

    def test_cost_cap_stops_before_the_launch_that_could_exceed_it(self):
        done = self.run_eval("--repeats", "2", "--max-cost-usd", "0.25")
        self.assertEqual(done.returncode, 3, done.stderr)
        summary = json.loads(done.stdout)
        self.assertIn("cost cap", summary["stopped"])
        self.assertEqual(len(self.model_calls()), 3)
        self.assertAlmostEqual(summary["cost"]["known_usd"], 0.18)

    def test_unknown_cost_stays_unknown_and_counts_at_the_run_budget(self):
        done = self.run_eval(
            "--repeats", "2", "--max-cost-usd", "0.25", stub={"cost": None}
        )
        self.assertEqual(done.returncode, 3, done.stderr)
        summary = json.loads(done.stdout)
        self.assertEqual(len(self.model_calls()), 2)
        self.assertEqual(summary["cost"]["unknown_cost_runs"], 2)
        self.assertEqual(summary["cost"]["known_usd"], 0)
        self.assertIsNone(next(iter(self.records().values()))["usage"]["cost_usd"])

    def test_a_limit_the_cli_cannot_confine_is_rejected_unless_the_runtime_accepts_it_unconfined(
        self,
    ):
        shell = self.runtime | {
            "tools": [*self.runtime["tools"], "Bash"],
            "allowed_tools": [*self.runtime["allowed_tools"], "Bash"],
        }
        refused = self.run_eval("--max-cost-usd", "1", runtime=shell)
        self.assertEqual(refused.returncode, 2)
        self.assertIn("confine-network", refused.stderr)
        self.assertEqual(self.model_calls(), [])
        accepted = shell | {
            "confinement": dict.fromkeys(("read", "write", "network"), "unconfined")
        }
        plan = json.loads(
            self.run_eval("--max-cost-usd", "1", runtime=accepted, execute=False).stdout
        )
        self.assertEqual(
            {c["check"]: c["status"] for c in plan["preflight"]}["confine-network"],
            "accepted_unconfined",
        )
        self.assertEqual(plan["blockers"], [])

    def test_a_session_whose_tools_break_a_confined_limit_stops_the_pilot(self):
        done = self.run_eval(
            "--repeats",
            "2",
            "--max-cost-usd",
            "1",
            stub={"tools": ["Read", "Bash", "Skill"]},
        )
        self.assertEqual(done.returncode, 3, done.stderr)
        self.assertIn("isolation violation", json.loads(done.stdout)["stopped"])
        self.assertEqual(len(self.model_calls()), 1)


if __name__ == "__main__":
    unittest.main()
