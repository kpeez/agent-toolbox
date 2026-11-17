"""Native runner contract checks. A stub `claude` on PATH replaces the model; no provider is invoked.

Admission: protects the spend and isolation promises of `run_eval.py` at its CLI. The credible
regressions are a dry run that launches the model, a rerun that launches finished runs again, a cost
cap checked after the launch or one that counts unknown cost as zero, a configuration the CLI cannot
confine that runs anyway, a session whose effective tools break a declared limit, and a hook-on run
whose stream lacks any plugin's SessionStart hook (the arm would silently measure hook-off), a hook-off
run that shows a hook, a relaunch of a run that already launched, a runner interrupt that leaves claude
running, an execute with no passed canary record, and a canary judged from the wrong evidence. Owner: no
other test reaches the runner. Each was seen red under one mutation of run_eval.py (see the PR body).
Every test writes under a temporary output root, never under artifacts/.
"""

from __future__ import annotations

import json
import os
import signal
import time
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
      --include-hook-events                 Include all hook lifecycle events in the output stream
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
    HELP = "\\n".join(l for l in HELP.splitlines() if not l.strip().startswith(config.get("help_without", "\\0")))
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
        if config.get("sleep"):
            import subprocess, time
            grandchild = subprocess.Popen(["sleep", "60"])
            (HERE / "pids").write_text("%d %d" % (os.getpid(), grandchild.pid))
            time.sleep(config["sleep"])
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
        plugin_dirs = [Path(a) for i, a in enumerate(argv) if argv[i - 1] == "--plugin-dir"]
        for pdir in plugin_dirs:
            hook = pdir / "hooks" / "session-start.md"
            if hook.is_file() and pdir.name in config.get("hook_plugins", [d.name for d in plugin_dirs]):
                ident = {"hook_id": "h-" + pdir.name, "hook_name": "SessionStart:startup", "hook_event": "SessionStart", "session_id": sid}
                print(json.dumps({"type": "system", "subtype": "hook_started", **ident}))
                out = hook.read_text()
                print(json.dumps({"type": "system", "subtype": "hook_response", **ident, "output": out, "stdout": out,
                                  "stderr": "", "exit_code": 0, "outcome": "success"}))
        if config.get("stray_hook_response"):
            print(json.dumps({"type": "system", "subtype": "hook_response", "hook_id": "stray", "hook_name": "SessionStart:startup",
                              "hook_event": "SessionStart", "output": "x", "exit_code": 0, "outcome": "success"}))
        if config.get("delete_swe_hook"):
            (plugin / "hooks" / "session-start.md").unlink(missing_ok=True)
        prompt = argv[argv.index("-p") + 1]
        if prompt.startswith("CANARY "):
            kind = prompt.split()[1].rstrip(":")
            path = prompt.split("PATH=")[1].split()[0] if "PATH=" in prompt else None
            n = [0]
            def tool(name, text, error=False, **tool_input):
                n[0] += 1
                tid = "c%d" % n[0]
                print(json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": tid, "name": name, "input": tool_input}]}}))
                print(json.dumps({"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": tid, "is_error": error, "content": text}]}}))
            refusal = "refused: outside the allowed directories"
            if kind == "read-outside" and config.get("outside_read", "refused") != "none":
                leaked = config.get("outside_read") == "leaked"
                tool("Read", Path(path).read_text() if leaked else refusal, not leaked, file_path=path)
                if config.get("outside_read") == "echoed":
                    print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": Path(path).read_text()}]}}))
            if kind == "write-outside":
                wrote = config.get("outside_write") == "wrote"
                if wrote or config.get("outside_write") == "wrote_but_reported_refused":
                    Path(path).write_text("canary")
                tool("Write", "ok" if wrote else refusal, not wrote, file_path=path, content="canary")
            if kind == "network" and config.get("network") == "fetched":
                tool("WebFetch", "ok", url="https://example.com")
            if kind == "playbook-read":
                ok = config.get("playbook", "ok") == "ok"
                tool("Read", Path(path).read_text()[:200] if ok else refusal, not ok, file_path=path)
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
        self.output_root = tmp / "out"
        self.use_pilot("main")

    def use_pilot(self, name):
        self.pilot_id = "test-" + name
        self.root = self.output_root / self.pilot_id

    def flags(self, *args, mode):
        path = Path(self.temp.name) / "runtime.json"
        path.write_text(json.dumps(self.runtime_used))
        return [
            "--repeats",
            "1",
            "--runtime",
            str(path),
            "--case",
            "IM-01",
            "--pilot-id",
            self.pilot_id,
            "--output-root",
            str(self.output_root),
            *args,
            *([mode] if mode else []),
        ]

    def start(self, *args, runtime=None, stub=None, mode="--execute"):
        self.runtime_used = runtime or self.runtime
        (self.stub_dir / "config.json").write_text(json.dumps(stub or {}))
        return subprocess.Popen(
            [sys.executable, str(SCRIPT), *self.flags(*args, mode=mode)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=REPO,
            env=self.env,
        )

    def run_eval(
        self, *args, runtime=None, stub=None, mode="--execute", canaries_passed=True
    ):
        """Run the runner CLI. An execute first gets a hand-written passing canary record unless told not to."""
        if mode == "--execute" and canaries_passed:
            self.record_canaries(*args, runtime=runtime)
        proc = self.start(*args, runtime=runtime, stub=stub, mode=mode)
        out, err = proc.communicate()
        return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)

    def record_canaries(self, *args, runtime=None):
        dry = self.run_eval(*args, runtime=runtime, mode=None)
        record = {
            "config_sha256": json.loads(dry.stdout)["pilot"]["config_sha256"],
            "canaries": {
                name: {"passed": True} for name in ("read-outside", "write-outside", "network", "playbook-read", "hook-on", "hook-off")
            },
        }
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "canaries.json").write_text(json.dumps(record))

    def model_calls(self):
        calls = (
            [json.loads(line) for line in self.log.read_text().splitlines()]
            if self.log.exists()
            else []
        )
        return [c for c in calls if "-p" in c["argv"]]

    def records(self, folder="runs"):
        return {
            p.parent.name: json.loads(p.read_text())
            for p in sorted(self.root.glob(f"{folder}/*/run.json"))
        }

    def test_dry_run_plans_and_preflights_but_launches_no_model(self):
        done = self.run_eval("--repeats", "2", "--max-cost-usd", "1", mode=None)
        self.assertEqual(done.returncode, 0, done.stderr)
        plan = json.loads(done.stdout)
        self.assertEqual(plan["runs"]["planned"], 4)
        self.assertEqual(plan["blockers"], ["canaries-not-passed"])
        self.assertEqual(
            {c["check"]: c["status"] for c in plan["preflight"]}["confine-read"],
            "pending_live",
        )
        self.assertEqual(self.model_calls(), [])
        self.assertFalse(self.root.exists())

    def test_the_flags_check_covers_the_plugin_dir_flag_a_launch_passes(self):
        plan = json.loads(
            self.run_eval(
                "--max-cost-usd", "1", stub={"help_without": "--plugin-dir"}, mode=None
            ).stdout
        )
        self.assertIn("flags-in-help", plan["blockers"])

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
            self.run_eval("--max-cost-usd", "1", runtime=accepted, mode=None).stdout
        )
        self.assertEqual(
            {c["check"]: c["status"] for c in plan["preflight"]}["confine-network"],
            "accepted_unconfined",
        )
        self.assertEqual(plan["blockers"], ["canaries-not-passed"])

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

    def test_a_hook_on_run_missing_any_plugins_session_start_hook_stops_the_pilot(self):
        for plugins in ([], ["swe"]):
            with self.subTest(hooks_that_ran=plugins):
                self.use_pilot("hook-on-" + "-".join(plugins or ["none"]))
                done = self.run_eval(
                    "--repeats", "2", "--max-cost-usd", "1", stub={"hook_plugins": plugins}
                )
                self.assertEqual(done.returncode, 3, done.stderr)
                self.assertIn("arm violation", json.loads(done.stdout)["stopped"])
                on = next(r for r in self.records().values() if r["arm"] == "hook-on")
                self.assertEqual([h["plugin"] for h in on["hook_events"]], plugins)

    def test_a_hook_off_run_that_shows_any_hook_event_stops_the_pilot(self):
        done = self.run_eval(
            "--repeats", "2", "--max-cost-usd", "1", stub={"stray_hook_response": True}
        )
        self.assertEqual(done.returncode, 3, done.stderr)
        self.assertIn("hook-off run, but a SessionStart:startup hook ran", json.loads(done.stdout)["stopped"])
        self.assertEqual(len(self.model_calls()), 2)

    def test_each_run_records_the_hook_events_its_arm_allows(self):
        done = self.run_eval("--max-cost-usd", "1")
        self.assertEqual(done.returncode, 0, done.stderr)
        by_arm = {r["arm"]: r["hook_events"] for r in self.records().values()}
        self.assertEqual(by_arm["hook-off"], [])
        self.assertEqual(
            sorted((h["event"], h["completed"], h["plugin"]) for h in by_arm["hook-on"]),
            [("SessionStart", True, p) for p in ("lab", "swe", "uni")],
        )

    def test_a_run_that_launched_and_then_failed_is_final_and_a_rerun_never_launches_it_again(self):
        first = self.run_eval("--max-cost-usd", "1", stub={"delete_swe_hook": True})
        self.assertEqual(first.returncode, 0, first.stderr)
        summary = json.loads(first.stdout)
        self.assertEqual(summary["run_states"], {"aborted": 1, "scored": 1})
        aborted = next(r for r in self.records().values() if r.get("outcome") == "aborted")
        self.assertEqual(aborted["arm"], "hook-on")
        self.assertIn("after the launch", aborted["error"])
        second = self.run_eval("--max-cost-usd", "1", stub={"delete_swe_hook": True})
        self.assertEqual(second.returncode, 0, second.stderr)
        again = json.loads(second.stdout)
        self.assertEqual((again["launched_now"], again["skipped_finished"]), (0, 2))
        self.assertEqual(again["run_states"], {"aborted": 1, "scored": 1})
        self.assertEqual(len(self.model_calls()), 2)
        self.assertEqual(sorted(p.name for p in (self.root / "runs").iterdir()), sorted(self.records()))
        self.assertEqual(again["cost"]["unknown_cost_runs"], 1)

    def test_an_interrupt_kills_the_childs_process_group_and_records_the_run_as_aborted(self):
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=signum.name):
                self.use_pilot("interrupt-" + signum.name.lower())
                pids = self.stub_dir / "pids"
                pids.unlink(missing_ok=True)
                self.record_canaries("--max-cost-usd", "1")
                runner = self.start("--max-cost-usd", "1", stub={"sleep": 60})
                deadline = time.monotonic() + 30
                while not pids.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                child, grandchild = map(int, pids.read_text().split())
                self.addCleanup(self.kill_quietly, child, grandchild)
                runner.send_signal(signum)
                runner.communicate(timeout=30)
                self.assertNotEqual(runner.returncode, 0)
                for pid in (child, grandchild):
                    self.assertTrue(self.gone(pid), f"process {pid} still runs after {signum.name}")
                record = next(iter(self.records().values()))
                self.assertEqual(record["outcome"], "aborted")
                self.assertIn(signum.name, record["error"])

    @staticmethod
    def gone(pid):
        for _ in range(50):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            time.sleep(0.1)
        return False

    @staticmethod
    def kill_quietly(*pids):
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def test_execute_refuses_without_a_canary_record_for_the_same_frozen_configuration(self):
        refused = self.run_eval("--max-cost-usd", "1", canaries_passed=False)
        self.assertEqual(refused.returncode, 2)
        self.assertIn("no canary record", refused.stderr)
        self.record_canaries("--max-cost-usd", "1")
        other = self.run_eval("--max-cost-usd", "2", canaries_passed=False)
        self.assertEqual(other.returncode, 2)
        self.assertIn("different frozen configuration", other.stderr)
        self.assertEqual(self.model_calls(), [])

    def test_passing_canaries_are_recorded_with_their_cost_and_allow_execute(self):
        done = self.run_eval("--max-cost-usd", "1", mode="--canaries")
        self.assertEqual(done.returncode, 0, done.stderr)
        record = json.loads((self.root / "canaries.json").read_text())
        self.assertEqual(
            sorted(record["canaries"]),
            ["hook-off", "hook-on", "network", "playbook-read", "read-outside", "write-outside"],
        )
        for name, result in record["canaries"].items():
            self.assertTrue(result["passed"], (name, result["detail"]))
            self.assertEqual((result["cost_usd"], result["budget_usd"], result["within_budget"]), (0.06, 0.1, True))
        self.assertEqual(len(self.model_calls()), 6)
        run = self.run_eval("--max-cost-usd", "1", canaries_passed=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertAlmostEqual(json.loads(run.stdout)["cost"]["known_usd"], 8 * 0.06)

    def test_a_failed_canary_is_recorded_and_blocks_execute(self):
        cases = [
            ("read-outside", {"outside_read": "leaked"}),
            ("read-outside", {"outside_read": "none"}),
            ("read-outside", {"outside_read": "echoed"}),
            ("write-outside", {"outside_write": "wrote"}),
            ("write-outside", {"outside_write": "wrote_but_reported_refused"}),
            ("network", {"network": "fetched"}),
            ("playbook-read", {"playbook": "refused"}),
            ("hook-on", {"hook_plugins": ["swe"]}),
            ("hook-off", {"stray_hook_response": True}),
        ]
        for index, (failing, stub) in enumerate(cases):
            with self.subTest(failing=failing, stub=stub):
                self.use_pilot(f"canary-{index}")
                done = self.run_eval("--max-cost-usd", "5", stub=stub, mode="--canaries")
                self.assertEqual(done.returncode, 3, done.stderr)
                record = json.loads((self.root / "canaries.json").read_text())
                self.assertFalse(record["canaries"][failing]["passed"], record["canaries"][failing])
                refused = self.run_eval("--max-cost-usd", "5", canaries_passed=False)
                self.assertEqual(refused.returncode, 2)
                self.assertIn(failing, refused.stderr)

    def test_the_canary_records_a_cost_above_the_per_run_budget_against_that_budget(self):
        self.run_eval("--max-cost-usd", "5", stub={"cost": 0.5}, mode="--canaries")
        result = json.loads((self.root / "canaries.json").read_text())["canaries"]["network"]
        self.assertEqual((result["cost_usd"], result["budget_usd"], result["within_budget"]), (0.5, 0.1, False))


if __name__ == "__main__":
    unittest.main()
