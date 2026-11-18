"""Native runner contract checks. A stub `claude` on PATH replaces the model; no provider is invoked.

Admission: protects the spend and isolation promises of `run_eval.py` at its CLI. The credible
regressions are a dry run that launches the model, a rerun that launches finished runs again, a cost
cap checked after the launch or one that counts unknown cost as zero, a configuration the CLI cannot
confine that runs anyway, a session whose effective tools break a declared limit, and a hook-on run
whose stream lacks any plugin's SessionStart hook (the arm would silently measure hook-off), a hook-off
run that shows a hook, a relaunch of a run that already launched, a runner interrupt that leaves claude
running, a run whose stream has no init event, an execute with no passed or a partial canary record, a
canary judged from the wrong evidence (one file-read tool probed, a refused Edit counted as a refused write,
a budget ceiling that the budget did not cause), and a dry run that creates a folder. Owner: no
other test reaches the runner. Each was seen red under one mutation of run_eval.py (see the PR body).
Every test writes under a temporary output root, never under artifacts/.
"""

from __future__ import annotations

import json
import os
import shutil
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
        if config.get("append_fixture_file"):
            flag = HERE / "appended.flag"
            if not flag.exists():
                flag.write_text("1")
                target_file = Path(config["append_fixture_file"])
                target_file.write_bytes(target_file.read_bytes() + b"\\nx")
        prompt = argv[argv.index("-p") + 1]
        if config.get("stray_write"):
            print(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "s1", "name": "Write", "input": {"file_path": config["stray_write"], "content": "x"}}]}}))
            print(json.dumps({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "s1", "is_error": False, "content": "ok"}]}}))
        if prompt.startswith("CANARY "):
            kind = prompt.split()[1].rstrip(":")
            path = prompt.split("PATH=")[1].split()[0].rstrip(".,") if "PATH=" in prompt else None
            n = [0]
            ceiling_result = None
            def tool(name, text, error=False, emit_result=True, **tool_input):
                n[0] += 1
                tid = "c%d" % n[0]
                print(json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": tid, "name": name, "input": tool_input}]}}))
                if emit_result:
                    print(json.dumps({"type": "user", "message": {"content": [
                        {"type": "tool_result", "tool_use_id": tid, "is_error": error, "content": text}]}}))
            refusal = "refused: outside the allowed directories"
            if kind == "read-outside" and config.get("outside_read", "refused") != "none":
                mode = config.get("outside_read", "refused")
                emit_result = mode != "no_results"
                secret = Path(path).read_text()
                read_path = path + ".wrong" if mode == "wrong_read" else path
                tool("Read", secret if mode == "leaked" else refusal, mode != "leaked", emit_result=emit_result, file_path=read_path)
                if mode == "echoed":
                    print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": secret}]}}))
                if mode != "read_only":
                    folder = str(Path(path).parent)
                    tool("Glob", path if mode == "glob_leaked" else refusal, mode != "glob_leaked", emit_result=emit_result, pattern=folder + "/sentinel-*.txt")
                    grep_out = {"grep_leaked": secret, "grep_listed": path}.get(mode, refusal)
                    tool("Grep", grep_out, mode not in ("grep_leaked", "grep_listed"), emit_result=emit_result, pattern="CANARY-", path=folder)
            if kind == "write-outside":
                mode = config.get("outside_write", "refused")
                if mode == "edit_only":
                    tool("Edit", refusal, True, file_path=path, old_string="a", new_string="b")
                else:
                    if mode in ("wrote", "wrote_but_reported_refused"):
                        Path(path).write_text("canary")
                    elif mode == "wrong_write_succeeded":
                        Path(path + ".wrong").write_text("canary")
                    write_path = path + ".wrong" if mode in ("wrong_write", "wrong_write_succeeded") else path
                    succeeded = mode in ("wrote", "wrong_write_succeeded")
                    tool("Write", "ok" if succeeded else refusal, not succeeded, file_path=write_path, content="canary")
            if kind == "network" and config.get("network") == "fetched":
                tool("WebFetch", "ok", url="https://example.com")
            if kind == "playbook-read":
                ok = config.get("playbook", "ok") == "ok"
                tool("Read", Path(path).read_text()[:200] if ok else refusal, not ok, file_path=path)
            if kind == "budget-ceiling":
                budget = float(argv[argv.index("--max-budget-usd") + 1])
                mode = config.get("ceiling", "stops")
                step, calls, subtype = {
                    "stops": (0.012, 40, "error_max_budget_usd"),
                    "overshoots": (0.2, 40, "error_max_budget_usd"),
                    "keeps_spending": (0.012, 40, "success"),
                    "completes_cheaply": (0.0001, 40, "success"),
                    "stops_before_the_budget": (0.0025, 2, "error_during_execution"),
                    "errors_over_budget": (0.012, 2, "error_during_execution"),
                    "finishes_early_over_the_budget": (0.012, 2, "success"),
                    "stops_after_the_whole_task": (0.0006, 40, "error_max_budget_usd"),
                }[mode]
                spent = 0.0
                for _ in range(calls):
                    tool("Read", "x", file_path=path)
                    spent += step
                    if mode in ("stops", "overshoots") and spent >= budget:
                        break
                ceiling_result = (spent, subtype)
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
            "worst_request": {
                "context_tokens": 10000,
                "output_tokens": 1000,
                "usd_per_mtok_input_max": 4.0,
                "usd_per_mtok_output": 10.0,
            },
            "max_concurrent_requests": 1,
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
        self.assertEqual((again["cost"]["unknown_cost_runs"], aborted["usage"]["cost_usd"]), (0, 0.06))

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
            ("read-outside", {"outside_read": "grep_listed"}),
            ("read-outside", {"outside_read": "read_only"}),
            ("write-outside", {"outside_write": "wrote"}),
            ("write-outside", {"outside_write": "wrote_but_reported_refused"}),
            ("write-outside", {"outside_write": "edit_only"}),
            ("network", {"network": "fetched"}),
            ("playbook-read", {"playbook": "refused"}),
            ("hook-on", {"hook_plugins": ["swe"]}),
            ("hook-off", {"stray_hook_response": True}),
            ("budget-ceiling", {"ceiling": "keeps_spending"}),
            ("budget-ceiling", {"ceiling": "overshoots"}),
            ("budget-ceiling", {"ceiling": "completes_cheaply"}),
            ("budget-ceiling", {"ceiling": "stops_before_the_budget"}),
            ("budget-ceiling", {"ceiling": "finishes_early_over_the_budget"}),
            ("budget-ceiling", {"ceiling": "stops_after_the_whole_task"}),
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

    def test_an_interrupt_that_lands_while_a_timed_out_child_is_killed_records_a_killed_timeout(self):
        script = (
            "import os, signal, sys\n"
            f"sys.path.insert(0, {str(HERE)!r})\n"
            "import run_eval\n"
            "real = os.killpg\n"
            "os.killpg = lambda pid, sig: (real(pid, sig), os.kill(os.getpid(), signal.SIGTERM))\n"
            "sys.argv = ['run_eval.py'] + sys.argv[1:]\n"
            "run_eval.main()\n"
        )
        self.runtime["timeout_seconds"] = 1
        self.record_canaries("--max-cost-usd", "1")
        (self.stub_dir / "config.json").write_text(json.dumps({"sleep": 60}))
        pids = self.stub_dir / "pids"
        done = subprocess.run(
            [sys.executable, "-c", script, *self.flags("--max-cost-usd", "1", mode="--execute")],
            text=True, capture_output=True, cwd=REPO, env=self.env, timeout=60,
        )
        child, grandchild = map(int, pids.read_text().split())
        self.addCleanup(self.kill_quietly, child, grandchild)
        self.assertEqual(done.returncode, 3, done.stderr)
        record = next(iter(self.records().values()))
        self.assertEqual((record["outcome"], record["timed_out"]), ("aborted", True))
        self.assertIn("process group was killed", record["error"])
        self.assertNotIn("before the child started", record["error"])
        for pid in (child, grandchild):
            self.assertTrue(self.gone(pid), f"process {pid} still runs")

    def test_a_dry_run_with_a_backup_dir_writes_nothing(self):
        backup = Path(self.temp.name) / "not" / "yet" / "there"
        plan = json.loads(
            self.run_eval("--max-cost-usd", "1", "--backup-dir", str(backup), mode=None).stdout
        )
        self.assertEqual({c["check"]: c["status"] for c in plan["preflight"]}["backup-dir"], "pass")
        self.assertFalse(backup.parent.parent.exists())

    def test_the_canary_records_a_cost_above_the_per_run_budget_against_that_budget(self):
        self.run_eval("--max-cost-usd", "5", stub={"cost": 0.12}, mode="--canaries")
        result = json.loads((self.root / "canaries.json").read_text())["canaries"]["network"]
        self.assertEqual((result["cost_usd"], result["budget_usd"], result["within_budget"]), (0.12, 0.1, False))
        self.use_pilot("canary-over-bound")
        done = self.run_eval("--max-cost-usd", "5", stub={"cost": 0.5}, mode="--canaries")
        self.assertEqual(done.returncode, 3, done.stderr)
        summary = json.loads(done.stdout)
        self.assertEqual(list(summary["canaries"]), ["read-outside"])
        read_res = summary["canaries"]["read-outside"]
        self.assertEqual((read_res["cost_usd"], read_res["budget_usd"], read_res["within_budget"]), (0.5, 0.1, False))
        self.assertIn("budget assumption broken", summary["stopped"])

    def test_budget_cap_reserves_worst_request_bound(self):
        tight = self.runtime | {"max_budget_usd_per_run": 0.01}
        done = self.run_eval("--max-cost-usd", "0.10", runtime=tight, stub={"cost": 0.006}, mode="--canaries")
        self.assertEqual(done.returncode, 3, done.stderr)
        summary = json.loads(done.stdout)
        self.assertIn("cost cap", summary["stopped"])
        self.assertNotIn("budget-ceiling", summary["canaries"])
        self.assertEqual(len(self.model_calls()), 6)
        self.use_pilot("worst-request-bound")
        concurrent = tight | {"max_concurrent_requests": 2}
        self.record_canaries("--max-cost-usd", "0.12", runtime=concurrent)
        capped = self.run_eval("--max-cost-usd", "0.12", runtime=concurrent, stub={"cost": 0.05}, canaries_passed=False)
        self.assertEqual(capped.returncode, 3, capped.stderr)
        self.assertIn("cost cap", json.loads(capped.stdout)["stopped"])
        self.assertEqual(len(self.model_calls()), 7)

    def test_budget_ceiling_canary_requires_the_budget_stop_subtype(self):
        done = self.run_eval("--max-cost-usd", "5", stub={"ceiling": "errors_over_budget"}, mode="--canaries")
        self.assertEqual(done.returncode, 3, done.stderr)
        ceiling = json.loads((self.root / "canaries.json").read_text())["canaries"]["budget-ceiling"]
        self.assertFalse(ceiling["passed"])
        self.assertEqual(ceiling["stop_subtype"], "error_during_execution")

    def test_read_outside_canary_requires_matching_tool_results(self):
        done = self.run_eval("--max-cost-usd", "5", stub={"outside_read": "no_results"}, mode="--canaries")
        self.assertEqual(done.returncode, 3, done.stderr)
        read = json.loads((self.root / "canaries.json").read_text())["canaries"]["read-outside"]
        self.assertFalse(read["passed"])
        self.assertIn("missing tool_result", read["detail"])

    def test_execute_refuses_when_custom_corpus_or_selected_fixture_changes(self):
        sandbox = Path(self.temp.name) / "eval-copy"
        sandbox.mkdir()
        shutil.copy2(HERE / "facets.json", sandbox / "facets.json")
        shutil.copytree(HERE / "fixtures", sandbox / "fixtures")
        corpus = sandbox / "custom-cases.json"
        cases_data = json.loads((HERE / "cases.json").read_text())
        original_corpus = json.dumps(cases_data)
        corpus.write_text(original_corpus)
        runtime_path = Path(self.temp.name) / "runtime.json"
        runtime_path.write_text(json.dumps(self.runtime))
        wrapper = (
            "import sys\n"
            "from pathlib import Path\n"
            f"sys.path.insert(0, {str(HERE)!r})\n"
            "import run_eval\n"
            f"run_eval.se.HERE = Path({str(sandbox)!r})\n"
            "sys.argv = ['run_eval.py'] + sys.argv[1:]\n"
            "run_eval.main()\n"
        )
        def run_custom(*extra):
            return subprocess.run(
                [sys.executable, "-c", wrapper, "--repeats", "1", "--runtime", str(runtime_path),
                 "--case", "IM-01", "--pilot-id", self.pilot_id, "--output-root", str(self.output_root),
                 "--corpus", str(corpus), "--max-cost-usd", "1", *extra],
                text=True, capture_output=True, cwd=REPO, env=self.env,
            )
        dry = run_custom()
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "canaries.json").write_text(json.dumps({
            "config_sha256": json.loads(dry.stdout)["pilot"]["config_sha256"],
            "canaries": {name: {"passed": True} for name in CANARY_NAMES},
        }))
        cases_data["cases"][0]["messages"][0]["content"] = "edited custom corpus prompt"
        corpus.write_text(json.dumps(cases_data))
        changed_corpus = run_custom("--execute")
        self.assertEqual(changed_corpus.returncode, 2)
        self.assertIn("different frozen configuration", changed_corpus.stderr)
        corpus.write_text(original_corpus)
        fixture_file = next(
            p for p in sorted((sandbox / "fixtures" / "harbor-importer").rglob("*")) if p.is_file()
        )
        fixture_file.write_text(fixture_file.read_text() + "\n# changed\n")
        changed_fixture = run_custom("--execute")
        self.assertEqual(changed_fixture.returncode, 2)
        self.assertIn("different frozen configuration", changed_fixture.stderr)
        self.assertEqual(self.model_calls(), [])

    def test_canaries_stop_at_the_first_isolation_violation_and_launch_nothing_more(self):
        done = self.run_eval("--max-cost-usd", "5", stub={"no_init": True}, mode="--canaries")
        self.assertEqual(done.returncode, 3, done.stderr)
        summary = json.loads(done.stdout)
        self.assertEqual(list(summary["canaries"]), ["read-outside"])
        self.assertFalse(summary["canaries"]["read-outside"]["passed"])
        self.assertIn("isolation violation", summary["stopped"])
        self.assertTrue((self.root / "isolation-violation.json").is_file())
        self.assertEqual(len(self.model_calls()), 1)

    def test_resume_blocks_after_an_isolation_violation_until_record_is_removed(self):
        first = self.run_eval("--repeats", "2", "--max-cost-usd", "1", stub={"no_init": True})
        self.assertEqual(first.returncode, 3, first.stderr)
        self.assertEqual(len(self.model_calls()), 1)
        blocked = self.run_eval("--repeats", "2", "--max-cost-usd", "1")
        self.assertEqual(blocked.returncode, 3, blocked.stderr)
        stopped = json.loads(blocked.stdout)["stopped"]
        self.assertIn("isolation-violation.json", stopped)
        self.assertIn("run.json", stopped)
        self.assertEqual(len(self.model_calls()), 1)
        (self.root / "isolation-violation.json").unlink()
        resumed = self.run_eval("--repeats", "2", "--max-cost-usd", "1")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        summary = json.loads(resumed.stdout)
        self.assertEqual((summary["launched_now"], summary["skipped_finished"]), (3, 1))
        self.assertEqual(len(self.model_calls()), 4)

    def test_relative_output_root_resolves_to_absolute_paths_for_child(self):
        rel_root = Path(self.temp.name) / "rel-out"
        self.output_root = rel_root
        self.root = rel_root / self.pilot_id
        self.record_canaries("--max-cost-usd", "1")
        runtime_path = Path(self.temp.name) / "runtime.json"
        runtime_path.write_text(json.dumps(self.runtime))
        (self.stub_dir / "config.json").write_text(json.dumps({}))
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "--repeats", "1", "--runtime", str(runtime_path),
             "--case", "IM-01", "--pilot-id", self.pilot_id, "--output-root", "rel-out",
             "--max-cost-usd", "1", "--execute"],
            text=True, capture_output=True, cwd=self.temp.name, env=self.env,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        calls = [c["argv"] for c in self.model_calls()]
        self.assertEqual(len(calls), 2)
        for argv in calls:
            for flag in ("--mcp-config", "--add-dir", "--plugin-dir"):
                paths = [argv[i + 1] for i, a in enumerate(argv) if a == flag]
                self.assertTrue(paths and all(Path(p).is_absolute() for p in paths), (flag, paths))

    def test_dry_run_plan_text_does_not_claim_write_canary_probes_edit(self):
        plan = json.loads(self.run_eval("--max-cost-usd", "1", mode=None).stdout)
        steps = next(s for s in plan["live_steps_pending_approval"] if s.startswith("--canaries"))
        self.assertNotIn("Edit", steps)
        self.assertIn("Write to a new path outside the fixture", steps)

    def test_run_exceeding_budget_plus_bound_stops_pilot_and_blocks_resume(self):
        first = self.run_eval("--repeats", "2", "--max-cost-usd", "1", stub={"cost": 0.20})
        self.assertEqual(first.returncode, 3, first.stderr)
        summary = json.loads(first.stdout)
        self.assertIn("budget", summary["stopped"])
        rid = next(iter(self.records()))
        self.assertIn(rid, summary["stopped"])
        self.assertEqual(len(self.model_calls()), 1)
        resumed = self.run_eval("--repeats", "2", "--max-cost-usd", "1")
        self.assertEqual(resumed.returncode, 3, resumed.stderr)
        again = json.loads(resumed.stdout)
        self.assertEqual(again["launched_now"], 0)
        self.assertIn(rid, again["stopped"])
        self.assertEqual(len(self.model_calls()), 1)

    def test_worst_request_and_concurrency_placeholders_block_execute(self):
        for key in ("context_tokens", "output_tokens", "usd_per_mtok_input_max", "usd_per_mtok_output"):
            for idx, bad in enumerate(("UNAPPROVED", True, 0, -1)):
                with self.subTest(field=key, value=bad):
                    self.use_pilot(f"bad-wr-{key}-{idx}")
                    rt = self.runtime | {"worst_request": self.runtime["worst_request"] | {key: bad}}
                    refused = self.run_eval("--max-cost-usd", "1", runtime=rt)
                    self.assertEqual(refused.returncode, 2)
                    self.assertIn(key, refused.stderr)
        for idx, bad in enumerate(("UNAPPROVED", True, 0, 1.5)):
            with self.subTest(field="max_concurrent_requests", value=bad):
                self.use_pilot(f"bad-mcr-{idx}")
                rt = self.runtime | {"max_concurrent_requests": bad}
                refused = self.run_eval("--max-cost-usd", "1", runtime=rt)
                self.assertEqual(refused.returncode, 2)
                self.assertIn("max_concurrent_requests", refused.stderr)
        self.assertEqual(self.model_calls(), [])
        raw_runtime = json.loads((HERE / "runtime.native.json").read_text())
        dry_raw = self.run_eval("--max-cost-usd", "1", runtime=raw_runtime, mode=None)
        self.assertEqual(dry_raw.returncode, 0, dry_raw.stderr)
        self.assertIn("runtime-complete", json.loads(dry_raw.stdout)["blockers"])
        canaries_refused = self.run_eval("--max-cost-usd", "1", runtime=raw_runtime, mode="--canaries")
        self.assertEqual(canaries_refused.returncode, 2)
        self.assertIn("worst_request", canaries_refused.stderr)

    def test_agent_tool_with_single_concurrent_request_blocks_execute(self):
        for field in ("tools", "allowed_tools"):
            with self.subTest(field=field):
                self.use_pilot(f"agent-mcr1-{field}")
                rt = self.runtime | {field: [*self.runtime[field], "Agent"], "max_concurrent_requests": 1}
                refused = self.run_eval("--max-cost-usd", "1", runtime=rt)
                self.assertEqual(refused.returncode, 2)
                self.assertIn("Agent", refused.stderr)
        allowed = self.runtime | {
            "tools": [*self.runtime["tools"], "Agent"],
            "allowed_tools": [*self.runtime["allowed_tools"], "Agent"],
            "max_concurrent_requests": 2,
        }
        plan = json.loads(self.run_eval("--max-cost-usd", "1", runtime=allowed, mode=None).stdout)
        self.assertEqual(plan["blockers"], ["canaries-not-passed"])
        self.assertEqual(self.model_calls(), [])

    def test_budget_ceiling_canary_fails_when_overshoot_exceeds_bound(self):
        tight_bound = self.runtime | {
            "worst_request": {
                "context_tokens": 1000,
                "output_tokens": 100,
                "usd_per_mtok_input_max": 1.0,
                "usd_per_mtok_output": 10.0,
            },
            "max_concurrent_requests": 1,
        }
        done = self.run_eval("--max-cost-usd", "5", runtime=tight_bound, stub={"ceiling": "stops"}, mode="--canaries")
        self.assertEqual(done.returncode, 3, done.stderr)
        ceiling = json.loads((self.root / "canaries.json").read_text())["canaries"]["budget-ceiling"]
        self.assertFalse(ceiling["passed"])
        self.assertAlmostEqual(ceiling["overshoot_bound_usd"], 0.002)
        self.assertNotIn("tolerance_usd", ceiling)

    def test_read_outside_canary_rejects_wrong_target_path(self):
        done = self.run_eval("--max-cost-usd", "5", stub={"outside_read": "wrong_read"}, mode="--canaries")
        self.assertEqual(done.returncode, 3, done.stderr)
        read = json.loads((self.root / "canaries.json").read_text())["canaries"]["read-outside"]
        self.assertFalse(read["passed"])
        self.assertIn("never tried against the sentinel outside the fixture=['Read']", read["detail"])

    def test_write_outside_canary_rejects_wrong_target_path(self):
        done = self.run_eval("--max-cost-usd", "5", stub={"outside_write": "wrong_write"}, mode="--canaries")
        self.assertEqual(done.returncode, 3, done.stderr)
        write = json.loads((self.root / "canaries.json").read_text())["canaries"]["write-outside"]
        self.assertFalse(write["passed"])
        self.assertIn("0 Write call(s)", write["detail"])

    def test_fixture_change_during_execution_stops_before_next_launch(self):
        sandbox = Path(self.temp.name) / "eval-live-drift"
        sandbox.mkdir()
        shutil.copy2(HERE / "facets.json", sandbox / "facets.json")
        shutil.copytree(HERE / "fixtures", sandbox / "fixtures")
        corpus = sandbox / "cases.json"
        shutil.copy2(HERE / "cases.json", corpus)
        fixture_file = next(
            p for p in sorted((sandbox / "fixtures" / "harbor-importer").rglob("*")) if p.is_file()
        )
        runtime_path = Path(self.temp.name) / "runtime.json"
        runtime_path.write_text(json.dumps(self.runtime))
        wrapper = (
            "import sys\n"
            "from pathlib import Path\n"
            f"sys.path.insert(0, {str(HERE)!r})\n"
            "import run_eval\n"
            f"run_eval.se.HERE = Path({str(sandbox)!r})\n"
            "sys.argv = ['run_eval.py'] + sys.argv[1:]\n"
            "run_eval.main()\n"
        )
        dry = subprocess.run(
            [sys.executable, "-c", wrapper, "--repeats", "2", "--runtime", str(runtime_path),
             "--case", "IM-01", "--pilot-id", self.pilot_id, "--output-root", str(self.output_root),
             "--corpus", str(corpus), "--max-cost-usd", "1"],
            text=True, capture_output=True, cwd=REPO, env=self.env,
        )
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "canaries.json").write_text(json.dumps({
            "config_sha256": json.loads(dry.stdout)["pilot"]["config_sha256"],
            "canaries": {name: {"passed": True} for name in CANARY_NAMES},
        }))
        (self.stub_dir / "config.json").write_text(json.dumps({"append_fixture_file": str(fixture_file)}))
        done = subprocess.run(
            [sys.executable, "-c", wrapper, "--repeats", "2", "--runtime", str(runtime_path),
             "--case", "IM-01", "--pilot-id", self.pilot_id, "--output-root", str(self.output_root),
             "--corpus", str(corpus), "--max-cost-usd", "1", "--execute"],
            text=True, capture_output=True, cwd=REPO, env=self.env,
        )
        self.assertEqual(done.returncode, 3, done.stderr)
        summary = json.loads(done.stdout)
        self.assertIn("harbor-importer", summary["stopped"])
        self.assertEqual(len(self.model_calls()), 1)
        self.assertEqual(len(list((self.root / "runs").iterdir())), 1)

    def test_isolation_marker_is_written_before_scoring_crash_blocks_resume(self):
        self.record_canaries("--repeats", "2", "--max-cost-usd", "1")
        runtime_path = Path(self.temp.name) / "runtime.json"
        runtime_path.write_text(json.dumps(self.runtime))
        (self.stub_dir / "config.json").write_text(json.dumps({"no_init": True}))
        wrapper = (
            "import sys\n"
            f"sys.path.insert(0, {str(HERE)!r})\n"
            "import run_eval\n"
            "real_score = run_eval.se.score\n"
            "def score_then_crash(*args, **kw):\n"
            "    real_score(*args, **kw)\n"
            "    raise SystemExit(99)\n"
            "run_eval.se.score = score_then_crash\n"
            "sys.argv = ['run_eval.py'] + sys.argv[1:]\n"
            "run_eval.main()\n"
        )
        crashed = subprocess.run(
            [sys.executable, "-c", wrapper, "--repeats", "2", "--runtime", str(runtime_path),
             "--case", "IM-01", "--pilot-id", self.pilot_id, "--output-root", str(self.output_root),
             "--max-cost-usd", "1", "--execute"],
            text=True, capture_output=True, cwd=REPO, env=self.env,
        )
        self.assertEqual(crashed.returncode, 99)
        self.assertEqual(len(self.model_calls()), 1)
        self.assertTrue((self.root / "isolation-violation.json").is_file())
        resumed = self.run_eval("--repeats", "2", "--max-cost-usd", "1")
        self.assertEqual(resumed.returncode, 3, resumed.stderr)
        summary = json.loads(resumed.stdout)
        self.assertEqual(summary["launched_now"], 0)
        self.assertIn("isolation violation", summary["stopped"])
        self.assertEqual(len(self.model_calls()), 1)

    def test_read_leak_canary_stops_after_first_canary_and_writes_marker(self):
        done = self.run_eval("--max-cost-usd", "5", stub={"outside_read": "leaked"}, mode="--canaries")
        self.assertEqual(done.returncode, 3, done.stderr)
        summary = json.loads(done.stdout)
        self.assertEqual(list(summary["canaries"]), ["read-outside"])
        self.assertFalse(summary["canaries"]["read-outside"]["passed"])
        self.assertIn("isolation violation", summary["stopped"])
        self.assertTrue((self.root / "isolation-violation.json").is_file())
        self.assertEqual(len(self.model_calls()), 1)

    def test_write_escape_canary_stops_after_second_canary_and_writes_marker(self):
        done = self.run_eval("--max-cost-usd", "5", stub={"outside_write": "wrote"}, mode="--canaries")
        self.assertEqual(done.returncode, 3, done.stderr)
        summary = json.loads(done.stdout)
        self.assertEqual(list(summary["canaries"]), ["read-outside", "write-outside"])
        self.assertTrue(summary["canaries"]["read-outside"]["passed"])
        self.assertFalse(summary["canaries"]["write-outside"]["passed"])
        self.assertIn("isolation violation", summary["stopped"])
        self.assertTrue((self.root / "isolation-violation.json").is_file())
        self.assertEqual(len(self.model_calls()), 2)

    def test_budget_marker_is_written_before_scoring_crash_blocks_resume(self):
        self.record_canaries("--repeats", "2", "--max-cost-usd", "1")
        runtime_path = Path(self.temp.name) / "runtime.json"
        runtime_path.write_text(json.dumps(self.runtime))
        (self.stub_dir / "config.json").write_text(json.dumps({"cost": 0.20}))
        wrapper = (
            "import sys\n"
            f"sys.path.insert(0, {str(HERE)!r})\n"
            "import run_eval\n"
            "real_score = run_eval.se.score\n"
            "def score_then_crash(*args, **kw):\n"
            "    real_score(*args, **kw)\n"
            "    raise SystemExit(99)\n"
            "run_eval.se.score = score_then_crash\n"
            "sys.argv = ['run_eval.py'] + sys.argv[1:]\n"
            "run_eval.main()\n"
        )
        crashed = subprocess.run(
            [sys.executable, "-c", wrapper, "--repeats", "2", "--runtime", str(runtime_path),
             "--case", "IM-01", "--pilot-id", self.pilot_id, "--output-root", str(self.output_root),
             "--max-cost-usd", "1", "--execute"],
            text=True, capture_output=True, cwd=REPO, env=self.env,
        )
        self.assertEqual(crashed.returncode, 99)
        self.assertEqual(len(self.model_calls()), 1)
        self.assertTrue((self.root / "budget-assumption-broken.json").is_file())
        rid = next(iter(self.records()))
        resumed = self.run_eval("--repeats", "2", "--max-cost-usd", "1")
        self.assertEqual(resumed.returncode, 3, resumed.stderr)
        summary = json.loads(resumed.stdout)
        self.assertEqual(summary["launched_now"], 0)
        self.assertIn("budget assumption broken", summary["stopped"])
        self.assertIn(rid, summary["stopped"])
        self.assertEqual(len(self.model_calls()), 1)

    def test_a_run_whose_hook_file_vanished_keeps_its_cost_and_the_cap_counts_it(self):
        done = self.run_eval("--max-cost-usd", "0.3", stub={"delete_swe_hook": True, "cost": 0.2})
        self.assertEqual(done.returncode, 3, done.stderr)
        self.assertEqual(len(self.model_calls()), 1)
        aborted = next(iter(self.records().values()))
        self.assertEqual((aborted["arm"], aborted["outcome"]), ("hook-on", "aborted"))
        self.assertEqual(aborted["usage"]["cost_usd"], 0.2)
        self.assertTrue((self.root / "budget-assumption-broken.json").is_file())
        self.assertAlmostEqual(json.loads(done.stdout)["cost"]["known_usd"], 0.2)

    def test_an_outside_write_during_the_read_canary_writes_the_marker_and_stops_the_canaries(self):
        stray = str(Path(self.temp.name) / "stray.txt")
        done = self.run_eval("--max-cost-usd", "5", stub={"stray_write": stray}, mode="--canaries")
        self.assertEqual(done.returncode, 3, done.stderr)
        summary = json.loads(done.stdout)
        self.assertEqual(list(summary["canaries"]), ["read-outside"])
        self.assertFalse(summary["canaries"]["read-outside"]["passed"])
        self.assertIn("isolation violation", summary["stopped"])
        self.assertIn(stray, json.loads((self.root / "isolation-violation.json").read_text())["detail"])
        self.assertEqual(len(self.model_calls()), 1)

    def test_a_crash_before_the_canary_verdict_leaves_the_marker_and_a_resume_launches_nothing(self):
        runtime_path = Path(self.temp.name) / "runtime.json"
        runtime_path.write_text(json.dumps(self.runtime))
        (self.stub_dir / "config.json").write_text(json.dumps({"outside_read": "leaked"}))
        wrapper = (
            "import sys\n"
            f"sys.path.insert(0, {str(HERE)!r})\n"
            "import run_eval\n"
            "def crash(*args, **kw):\n"
            "    raise SystemExit(99)\n"
            "run_eval.canary_verdict = crash\n"
            "sys.argv = ['run_eval.py'] + sys.argv[1:]\n"
            "run_eval.main()\n"
        )
        crashed = subprocess.run(
            [sys.executable, "-c", wrapper, "--repeats", "1", "--runtime", str(runtime_path),
             "--case", "IM-01", "--pilot-id", self.pilot_id, "--output-root", str(self.output_root),
             "--max-cost-usd", "5", "--canaries"],
            text=True, capture_output=True, cwd=REPO, env=self.env,
        )
        self.assertEqual(crashed.returncode, 99, crashed.stderr)
        self.assertTrue((self.root / "canaries" / "read-outside" / "run.json").is_file())
        self.assertFalse((self.root / "canaries" / "read-outside" / "canary.json").exists())
        self.assertTrue((self.root / "isolation-violation.json").is_file())
        resumed = self.run_eval("--max-cost-usd", "5", mode="--canaries")
        self.assertEqual(resumed.returncode, 3, resumed.stderr)
        self.assertIn("isolation violation", json.loads(resumed.stdout)["stopped"])
        self.assertEqual(len(self.model_calls()), 1)

    def test_an_outside_write_in_a_pilot_run_stops_the_pilot(self):
        stray = str(Path(self.temp.name) / "stray.txt")
        done = self.run_eval("--repeats", "2", "--max-cost-usd", "1", stub={"stray_write": stray})
        self.assertEqual(done.returncode, 3, done.stderr)
        self.assertIn("isolation violation", json.loads(done.stdout)["stopped"])
        self.assertIn(stray, json.loads((self.root / "isolation-violation.json").read_text())["detail"])
        self.assertEqual(len(self.model_calls()), 1)

    def test_write_escape_to_other_outside_path_stops_canaries(self):
        done = self.run_eval("--max-cost-usd", "5", stub={"outside_write": "wrong_write_succeeded"}, mode="--canaries")
        self.assertEqual(done.returncode, 3, done.stderr)
        summary = json.loads(done.stdout)
        self.assertEqual(list(summary["canaries"]), ["read-outside", "write-outside"])
        self.assertTrue(summary["canaries"]["read-outside"]["passed"])
        self.assertFalse(summary["canaries"]["write-outside"]["passed"])
        self.assertIn("isolation violation", summary["stopped"])
        self.assertTrue((self.root / "isolation-violation.json").is_file())
        self.assertEqual(len(self.model_calls()), 2)


if __name__ == "__main__":
    unittest.main()
