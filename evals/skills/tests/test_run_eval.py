"""Native runner contract checks. A stub `claude` on PATH replaces the model; no provider is invoked.

Admission: protects the spend and isolation promises of `run_eval.py` at its CLI. The credible
regressions are a dry run that launches the model, a rerun that launches finished runs again, a cost
cap checked after the launch or one that counts unknown cost as zero, a configuration the CLI cannot
confine that runs anyway, a session whose effective tools break a declared limit, and a hook-on run
whose stream lacks any plugin's SessionStart hook (the arm would silently measure hook-off), a hook-off
run that shows a hook, a relaunch of a run that already launched, a runner interrupt that leaves claude
running, a run whose stream has no init event, an execute with no passed or a partial canary record, a
canary judged from the wrong evidence (one file-read tool probed, an Edit of a missing file counted, a
budget ceiling that nothing exceeded), and a dry run that creates a folder. Owner: no
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
sys.path.insert(0, str(HERE))
import run_eval

CANARY_NAMES = (
    "read-outside",
    "write-outside",
    "network",
    "playbook-read",
    "hook-on",
    "hook-off",
    "budget-ceiling",
)

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
            path = prompt.split("PATH=")[1].split()[0].rstrip(".,") if "PATH=" in prompt else None
            n = [0]
            ceiling_result = None
            def tool(name, text, error=False, **tool_input):
                n[0] += 1
                tid = "c%d" % n[0]
                print(json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": tid, "name": name, "input": tool_input}]}}))
                print(json.dumps({"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": tid, "is_error": error, "content": text}]}}))
            refusal = "refused: outside the allowed directories"
            if kind == "read-outside" and config.get("outside_read", "refused") != "none":
                mode = config.get("outside_read", "refused")
                secret = Path(path).read_text()
                tool("Read", secret if mode == "leaked" else refusal, mode != "leaked", file_path=path)
                if mode == "echoed":
                    print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": secret}]}}))
                if mode != "read_only":
                    folder = str(Path(path).parent)
                    tool("Glob", path if mode == "glob_leaked" else refusal, mode != "glob_leaked", pattern=folder + "/sentinel-*.txt")
                    tool("Grep", secret if mode == "grep_leaked" else refusal, mode != "grep_leaked", pattern="CANARY-", path=folder)
            if kind == "write-outside":
                mode = config.get("outside_write", "refused")
                edit = Path(path).with_name("edit-target.txt")
                if mode == "edit_of_missing_file_only":
                    tool("Edit", refusal, True, file_path=path, old_string="a", new_string="b")
                else:
                    if mode in ("wrote", "wrote_but_reported_refused"):
                        Path(path).write_text("canary")
                    tool("Write", "ok" if mode == "wrote" else refusal, mode != "wrote", file_path=path, content="canary")
                    if mode == "edited":
                        edit.write_text("edited")
                    tool("Edit", "ok" if mode == "edited" else refusal, mode != "edited", file_path=str(edit),
                         old_string="ORIGINAL-CONTENT", new_string="edited")
            if kind == "network" and config.get("network") == "fetched":
                tool("WebFetch", "ok", url="https://example.com")
            if kind == "playbook-read":
                ok = config.get("playbook", "ok") == "ok"
                tool("Read", Path(path).read_text()[:200] if ok else refusal, not ok, file_path=path)
            if kind == "budget-ceiling":
                budget = float(argv[argv.index("--max-budget-usd") + 1])
                mode = config.get("ceiling", "stops")
                step = {"stops": 0.012, "overshoots": 0.2, "keeps_spending": 0.012, "completes_cheaply": 0.0001}[mode]
                spent = 0.0
                for _ in range(40):
                    tool("Read", "x", file_path=path)
                    spent += step
                    if mode in ("stops", "overshoots") and spent >= budget:
                        break
                ceiling_result = (spent, "error_max_budget_usd" if mode in ("stops", "overshoots") else "success")
        tools = config.get("tools", ["Read", "Write", "Edit", "Glob", "Grep", "Skill"])
        if not config.get("no_init"):
            print(json.dumps({"type": "system", "subtype": "init", "session_id": sid, "tools": tools, "mcp_servers": [],
                              "skills": ["swe:implement"], "model": "stub-model", "permissionMode": "dontAsk",
                              "claude_code_version": "2.1.326", "plugins": [], "memory_paths": {"auto": home + "/memory"}}))
        result = {"type": "result", "subtype": "success", "is_error": False, "session_id": sid, "num_turns": 2}
        cost = config.get("cost", 0.06)
        if prompt.startswith("CANARY ") and ceiling_result:
            result["subtype"] = ceiling_result[1]
            cost = None if cost is None else ceiling_result[0]
        if cost is not None:
            result["total_cost_usd"] = cost
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

    def record_canaries(self, *args, runtime=None, omit=()):
        dry = self.run_eval(*args, runtime=runtime, mode=None)
        record = {
            "config_sha256": json.loads(dry.stdout)["pilot"]["config_sha256"],
            "canaries": {
                name: {"passed": True} for name in CANARY_NAMES if name not in omit
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
        done = self.run_eval("--repeats", "2", "--max-cost-usd", "0.3")
        self.assertEqual(done.returncode, 3, done.stderr)
        summary = json.loads(done.stdout)
        self.assertIn("cost cap", summary["stopped"])
        self.assertEqual(len(self.model_calls()), 3)
        self.assertAlmostEqual(summary["cost"]["known_usd"], 0.18)

    def test_unknown_cost_stays_unknown_and_counts_at_the_run_reservation(self):
        done = self.run_eval(
            "--repeats", "2", "--max-cost-usd", "0.35", stub={"cost": None}
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
        self.assertEqual(sorted(record["canaries"]), sorted(CANARY_NAMES))
        for name, result in record["canaries"].items():
            self.assertTrue(result["passed"], (name, result["detail"]))
            if name != "budget-ceiling":
                self.assertEqual((result["cost_usd"], result["budget_usd"], result["within_budget"]), (0.06, 0.1, True))
        ceiling = record["canaries"]["budget-ceiling"]
        self.assertEqual((ceiling["budget_usd"], ceiling["tool_calls"], ceiling["stopped"]), (0.02, 2, True))
        self.assertAlmostEqual(ceiling["overshoot_usd"], 0.004)
        self.assertEqual(len(self.model_calls()), 7)
        budgets = [c["argv"][c["argv"].index("--max-budget-usd") + 1] for c in self.model_calls()]
        self.assertEqual(budgets, ["0.1"] * 6 + ["0.02"])
        run = self.run_eval("--max-cost-usd", "1", canaries_passed=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertAlmostEqual(json.loads(run.stdout)["cost"]["known_usd"], 8 * 0.06 + 0.024)

    def test_a_failed_canary_is_recorded_and_blocks_execute(self):
        cases = [
            ("read-outside", {"outside_read": "leaked"}),
            ("read-outside", {"outside_read": "none"}),
            ("read-outside", {"outside_read": "echoed"}),
            ("read-outside", {"outside_read": "glob_leaked"}),
            ("read-outside", {"outside_read": "grep_leaked"}),
            ("read-outside", {"outside_read": "read_only"}),
            ("write-outside", {"outside_write": "wrote"}),
            ("write-outside", {"outside_write": "wrote_but_reported_refused"}),
            ("write-outside", {"outside_write": "edited"}),
            ("write-outside", {"outside_write": "edit_of_missing_file_only"}),
            ("network", {"network": "fetched"}),
            ("playbook-read", {"playbook": "refused"}),
            ("hook-on", {"hook_plugins": ["swe"]}),
            ("hook-off", {"stray_hook_response": True}),
            ("budget-ceiling", {"ceiling": "keeps_spending"}),
            ("budget-ceiling", {"ceiling": "overshoots"}),
            ("budget-ceiling", {"ceiling": "completes_cheaply"}),
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

    def test_a_run_whose_stream_has_no_init_event_is_an_isolation_violation_that_stops_the_pilot(self):
        done = self.run_eval("--repeats", "2", "--max-cost-usd", "1", stub={"no_init": True})
        self.assertEqual(done.returncode, 3, done.stderr)
        self.assertIn("isolation violation: no init event", json.loads(done.stdout)["stopped"])
        self.assertEqual(len(self.model_calls()), 1)

    def test_a_run_a_hard_kill_left_with_a_start_and_no_end_is_aborted_and_never_launched_again(self):
        first = self.run_eval("--max-cost-usd", "1")
        self.assertEqual(first.returncode, 0, first.stderr)
        victim = next(p for p in sorted((self.root / "runs").iterdir()) if self.records()[p.name]["arm"] == "hook-off")
        record = json.loads((victim / "run.json").read_text())
        killed = {k: record[k] for k in ("schema_version", "rid", "case", "arm", "repeat", "launch", "started_at")}
        (victim / "run.json").write_text(json.dumps(killed))
        for leftover in ("score.json", "capture.json"):
            (victim / leftover).unlink(missing_ok=True)
        second = self.run_eval("--max-cost-usd", "1")
        self.assertEqual(second.returncode, 0, second.stderr)
        summary = json.loads(second.stdout)
        self.assertEqual((summary["launched_now"], summary["skipped_finished"]), (0, 2))
        self.assertEqual(summary["run_states"], {"aborted": 1, "scored": 1})
        self.assertEqual(len(self.model_calls()), 2)
        self.assertEqual(self.records()[victim.name]["outcome"], "aborted")

    def test_a_canary_that_launched_is_never_launched_again(self):
        earlier = self.root / "canaries" / "read-outside"
        earlier.mkdir(parents=True)
        (earlier / "run.json").write_text(json.dumps({"started_at": "2026-01-01T00:00:00Z"}))
        done = self.run_eval("--max-cost-usd", "5", mode="--canaries")
        self.assertEqual(done.returncode, 3, done.stderr)
        record = json.loads((self.root / "canaries.json").read_text())["canaries"]
        self.assertFalse(record["read-outside"]["passed"])
        self.assertIn("never launched again", record["read-outside"]["detail"])
        self.assertEqual(len(self.model_calls()), len(CANARY_NAMES) - 1)

    def test_an_unknown_canary_cost_fails_the_canary(self):
        self.run_eval("--max-cost-usd", "5", stub={"cost": None}, mode="--canaries")
        record = json.loads((self.root / "canaries.json").read_text())["canaries"]
        for name in ("network", "budget-ceiling"):
            self.assertFalse(record[name]["passed"], name)
            self.assertFalse(record[name]["within_budget"], name)
            self.assertIsNone(record[name]["cost_usd"], name)

    def test_execute_refuses_a_canary_record_that_lacks_any_canary(self):
        self.record_canaries("--max-cost-usd", "1", omit=("hook-on",))
        refused = self.run_eval("--max-cost-usd", "1", canaries_passed=False)
        self.assertEqual(refused.returncode, 2)
        self.assertIn("hook-on", refused.stderr)
        self.assertEqual(self.model_calls(), [])

    def test_launch_restores_the_interrupt_handlers_and_leaves_the_child_unblocked(self):
        interrupts = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
        before = {s: signal.getsignal(s) for s in interrupts}
        probe = "import signal; print(*sorted(s.name for s in signal.pthread_sigmask(signal.SIG_BLOCK, []) if s in (1, 2, 15)))"
        out = Path(self.temp.name) / "mask.txt"
        code, timed_out = run_eval.launch(
            [sys.executable, "-c", probe], dict(self.env), REPO, 30, out, Path(self.temp.name) / "err.txt"
        )
        self.assertEqual((code, timed_out), (0, False))
        self.assertEqual({s: signal.getsignal(s) for s in interrupts}, before)
        self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK, []) & set(interrupts), set())
        self.assertEqual(out.read_text().strip(), "", "the child inherited blocked interrupt signals")

    def test_a_dry_run_with_a_backup_dir_writes_nothing(self):
        backup = Path(self.temp.name) / "not" / "yet" / "there"
        plan = json.loads(
            self.run_eval("--max-cost-usd", "1", "--backup-dir", str(backup), mode=None).stdout
        )
        self.assertEqual({c["check"]: c["status"] for c in plan["preflight"]}["backup-dir"], "pass")
        self.assertFalse(backup.parent.parent.exists())

    def test_the_canary_records_a_cost_above_the_per_run_budget_against_that_budget(self):
        self.run_eval("--max-cost-usd", "5", stub={"cost": 0.5}, mode="--canaries")
        result = json.loads((self.root / "canaries.json").read_text())["canaries"]["network"]
        self.assertEqual((result["cost_usd"], result["budget_usd"], result["within_budget"]), (0.5, 0.1, False))


if __name__ == "__main__":
    unittest.main()
