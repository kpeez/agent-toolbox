"""Contract checks for the blinded relevant-action labeler."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from corpus_io import read_cases

HERE = Path(__file__).resolve().parents[1]
SCRIPT = HERE / "label_relevant_action.py"
REPO = HERE.parents[1]

STUB = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, sys
    from pathlib import Path

    argv = sys.argv[1:]
    prompt = sys.stdin.read()
    cfg_path = os.environ.get("STUB_CONFIG")
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8")) if cfg_path else {}
    log_path = os.environ.get("STUB_LOG")
    if log_path:
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"argv": argv, "prompt": prompt}) + "\\n")

    model = argv[argv.index("--model") + 1] if "--model" in argv else ""
    reply = cfg.get("by_model", {}).get(model, cfg.get("default"))
    if isinstance(reply, list):
        count_file = Path(f"{cfg['counter_file']}.{model}")
        idx = int(count_file.read_text()) if count_file.exists() else 0
        count_file.write_text(str(idx + 1))
        reply = reply[idx]
    if isinstance(reply, str):
        sys.stdout.write(reply)
    else:
        sys.stdout.write(json.dumps(reply))
''')


def write_claude_transcript(
    path: Path,
    steps: list[tuple],
    *,
    hook_rows: list[dict] | None = None,
    sid: str = "claude-session",
) -> None:
    rows: list[dict] = []

    def add(row: dict, *, is_sidechain: bool = False, agent_id: str | None = None) -> None:
        extra = {"agentId": agent_id} if agent_id is not None else {}
        entry = {
            "uuid": f"u-{len(rows)}",
            "parentUuid": rows[-1]["uuid"] if rows else None,
            "sessionId": sid,
            "isSidechain": is_sidechain,
            **extra,
            **row,
        }
        rows.append(entry)

    if hook_rows:
        for att in hook_rows:
            add({"type": "attachment", "attachment": att})
    add({"type": "user", "message": {"role": "user", "content": "Transcript prompt mentioning hook-off"}})
    for item in steps:
        kind = item[0]
        if kind == "call":
            _, message_id, tool_use_id, payload = item
            add({
                "type": "assistant",
                "message": {
                    "id": message_id,
                    "content": [{
                        "type": "tool_use",
                        "id": tool_use_id,
                        "name": payload["name"],
                        "input": payload["input"],
                    }],
                },
            })
        elif kind == "sidechain_call":
            _, message_id, tool_use_id, agent_id, payload = item
            add(
                {
                    "type": "assistant",
                    "message": {
                        "id": message_id,
                        "content": [{
                            "type": "tool_use",
                            "id": tool_use_id,
                            "name": payload["name"],
                            "input": payload["input"],
                        }],
                    },
                },
                is_sidechain=True,
                agent_id=agent_id,
            )
        elif kind == "result":
            _, tool_use_id, payload = item
            add({
                "type": "user",
                "toolUseResult": payload,
                "message": {
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": "ok"}],
                },
            })
        elif kind == "body":
            _, tool_use_id, text = item
            add({
                "type": "user",
                "isMeta": True,
                "sourceToolUseID": tool_use_id,
                "message": {"role": "user", "content": [{"type": "text", "text": text}]},
            })
        elif kind == "text":
            _, message_id, text = item
            add({"type": "assistant", "message": {"id": message_id, "content": [{"type": "text", "text": text}]}})
        elif kind == "system":
            _, subtype = item
            add({"type": "system", "subtype": subtype})

    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


class RelevantActionLabelerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="labeler-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stub = self.root / "claude-stub"
        self.stub.write_text(STUB, encoding="utf-8")
        self.stub.chmod(0o755)
        self.stub_cfg = self.root / "stub-config.json"
        self.stub_log = self.root / "stub-log.jsonl"
        self.counter_file = self.root / "stub-counter.txt"
        self.plugin_dir = self.root / "inputs" / "plugins" / "swe"
        (self.plugin_dir / "skills" / "swe-mode" / "playbooks").mkdir(parents=True)
        self.cases = {c["id"]: c for c in read_cases()}

    def run_cli(self, *args: object, ok: bool = True) -> object:
        env = {
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "SKILL_EVAL_CLAUDE": str(self.stub),
            "STUB_CONFIG": str(self.stub_cfg),
            "STUB_LOG": str(self.stub_log),
        }
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            text=True,
            capture_output=True,
            cwd=REPO,
            env=env,
        )
        if ok:
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        return proc

    def set_stub(self, default: object = None, by_model: dict | None = None) -> None:
        self.stub_cfg.write_text(
            json.dumps({
                "default": default,
                "by_model": by_model or {},
                "counter_file": str(self.counter_file),
            }),
            encoding="utf-8",
        )

    def test_view_drops_skill_plugin_and_sidechain_calls_and_blinds_transcript_leakage(self) -> None:
        transcript = self.root / "trace.jsonl"
        playbook_path = str(self.plugin_dir / "skills" / "swe-mode" / "playbooks" / "fix-bug.md")
        skill_path = str(self.plugin_dir / "skills" / "implement" / "SKILL.md")
        real_skill_path = os.path.realpath(skill_path)
        long_note = "x" * 350
        steps = [
            ("text", "m1", "Playbook: swe-mode/fix-bug under hook-on; loading swe:implement."),
            ("call", "m1", "use-skill", {"name": "Skill", "input": {"skill": "swe:implement"}}),
            ("result", "use-skill", {"success": True}),
            ("body", "use-skill", f"Base directory for this skill: {self.plugin_dir / 'skills' / 'implement'}\n\nSENTINEL_BODY"),
            ("call", "m2", "use-glob", {"name": "Glob", "input": {"pattern": "*.py"}}),
            ("result", "use-glob", {"filenames": ["importer.py"]}),
            ("call", "m3", "use-pb-read", {"name": "Read", "input": {"file_path": playbook_path}}),
            ("result", "use-pb-read", {"type": "text"}),
            ("call", "m3", "use-skill-read", {"name": "Read", "input": {"file_path": real_skill_path}}),
            ("call", "m3", "use-skill-grep", {"name": "Grep", "input": {"pattern": "secret", "path": str(self.plugin_dir)}}),
            ("call", "m3", "use-skill-bash", {"name": "Bash", "input": {"command": f"cat {skill_path}"}}),
            ("sidechain_call", "sub-m1", "sub-edit", "sub1", {"name": "Edit", "input": {"file_path": "importer.py"}}),
            ("call", "m4", "use-read", {"name": "Read", "input": {"file_path": "/work/importer.py"}}),
            ("call", "m5", "use-edit", {"name": "Edit", "input": {"file_path": "/work/importer.py", "old_string": "a", "new_string": "b"}}),
            ("call", "m6", "use-bash", {"name": "Bash", "input": {"command": "pytest -q"}}),
            ("call", "m7", "use-agent", {"name": "Agent", "input": {"prompt": long_note}}),
            ("system", "stop_hook_summary"),
        ]
        hook_rows = [{
            "type": "hook_success",
            "hookEvent": "SessionStart",
            "stdout": "SENTINEL_HOOK_TEXT hook-on swe:swe-mode",
            "exitCode": 0,
        }]
        write_claude_transcript(transcript, steps, hook_rows=hook_rows)

        view = self.run_cli("view", "--transcript", transcript, "--case", "IM-01", "--plugin-dir", self.plugin_dir)
        self.assertEqual(view["case"], "IM-01")
        self.assertEqual(view["user_message"], self.cases["IM-01"]["messages"][-1]["content"])
        self.assertEqual(view["relevant_action"], self.cases["IM-01"]["relevant_action"])
        self.assertEqual(
            view["tool_calls"],
            [
                {"tool_use_id": "use-glob", "tool": "Glob", "target": "*.py"},
                {"tool_use_id": "use-read", "tool": "Read", "target": "/work/importer.py"},
                {"tool_use_id": "use-edit", "tool": "Edit", "target": "/work/importer.py"},
                {"tool_use_id": "use-bash", "tool": "Bash", "target": "pytest -q"},
                {
                    "tool_use_id": "use-agent",
                    "tool": "Agent",
                    "target": json.dumps({"prompt": long_note}, separators=(",", ":"), sort_keys=True)[:300],
                },
            ],
        )
        serialized = json.dumps(view)
        for leaked in ("swe:implement", "swe-mode", "fix-bug", "SENTINEL_HOOK_TEXT", "SENTINEL_BODY", "hook-on", "hook-off", "sub-edit"):
            self.assertNotIn(leaked, serialized)

    def test_label_accepts_valid_id_and_none_and_rejects_bad_replies(self) -> None:
        transcript = self.root / "label.jsonl"
        write_claude_transcript(
            transcript,
            [
                ("call", "m1", "use-skill", {"name": "Skill", "input": {"skill": "swe:implement"}}),
                ("call", "m2", "use-read", {"name": "Read", "input": {"file_path": "importer.py"}}),
                ("call", "m3", "use-edit", {"name": "Edit", "input": {"file_path": "importer.py"}}),
            ],
        )

        self.set_stub(default={"type": "result", "is_error": False, "structured_output": {"tool_use_id": "use-edit"}, "total_cost_usd": 0.0042})
        labeled = self.run_cli("label", "--transcript", transcript, "--case", "IM-01", "--plugin-dir", self.plugin_dir, "--model", "haiku")
        self.assertEqual(labeled["case"], "IM-01")
        self.assertEqual(labeled["tool_use_id"], "use-edit")
        self.assertEqual(labeled["model"], "haiku")
        self.assertEqual(len(labeled["prompt_sha256"]), 64)
        self.assertEqual(labeled["cost_usd"], 0.0042)

        logged = json.loads(self.stub_log.read_text(encoding="utf-8").splitlines()[-1])
        argv = logged["argv"]
        for flag in ("-p", "--no-session-persistence", "--effort", "low", "--model", "haiku", "--output-format", "json"):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        schema = json.loads(argv[argv.index("--json-schema") + 1])
        self.assertEqual(schema["properties"]["tool_use_id"]["enum"], ["use-read", "use-edit", "none"])
        self.assertIn(self.cases["IM-01"]["relevant_action"], logged["prompt"])
        self.assertIn("use-edit", logged["prompt"])
        self.assertNotIn("use-skill", logged["prompt"])

        self.set_stub(default={"type": "result", "is_error": False, "structured_output": {"tool_use_id": "none"}})
        none_res = self.run_cli("label", "--transcript", transcript, "--case", "IM-01", "--plugin-dir", self.plugin_dir, "--model", "haiku")
        self.assertEqual(none_res["tool_use_id"], "none")
        self.assertIsNone(none_res["cost_usd"])

        self.set_stub(default={"type": "result", "is_error": False, "structured_output": {"tool_use_id": "use-unknown"}})
        unknown_err = self.run_cli("label", "--transcript", transcript, "--case", "IM-01", "--plugin-dir", self.plugin_dir, "--model", "haiku", ok=False)
        self.assertIn("not in the labeler view", unknown_err.stderr)

        self.set_stub(default={"type": "result", "is_error": False, "result": "use-edit"})
        missing_err = self.run_cli("label", "--transcript", transcript, "--case", "IM-01", "--plugin-dir", self.plugin_dir, "--model", "haiku", ok=False)
        self.assertIn("structured_output", missing_err.stderr)

        self.set_stub(default="not json")
        malformed_err = self.run_cli("label", "--transcript", transcript, "--case", "IM-01", "--plugin-dir", self.plugin_dir, "--model", "haiku", ok=False)
        self.assertIn("malformed claude JSON reply", malformed_err.stderr)

    def test_calibrate_reports_agreement_fraction_and_mismatches(self) -> None:
        t1 = self.root / "t1.jsonl"
        t2 = self.root / "t2.jsonl"
        t3 = self.root / "t3.jsonl"
        write_claude_transcript(t1, [("call", "m1", "c1", {"name": "Edit", "input": {"file_path": "importer.py"}})])
        write_claude_transcript(t2, [("call", "m1", "c2", {"name": "Edit", "input": {"file_path": "search.py"}})])
        write_claude_transcript(t3, [("call", "m1", "c3", {"name": "Read", "input": {"file_path": "cache.py"}})])

        labels = self.root / "labels.jsonl"
        rows = [
            {"transcript": str(t1), "case": "IM-01", "plugin_dirs": [str(self.plugin_dir)], "tool_use_id": "c1"},
            {"transcript": str(t2), "case": "IM-02", "plugin_dirs": [str(self.plugin_dir)], "tool_use_id": "c2"},
            {"transcript": str(t3), "case": "IM-07", "plugin_dirs": [str(self.plugin_dir)], "tool_use_id": "none"},
        ]
        labels.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

        self.set_stub(
            by_model={
                "model-a": [
                    {"structured_output": {"tool_use_id": "c1"}, "total_cost_usd": 0.001},
                    {"structured_output": {"tool_use_id": "c2"}, "total_cost_usd": 0.001},
                    {"structured_output": {"tool_use_id": "none"}, "total_cost_usd": 0.001},
                ],
                "model-b": [
                    {"structured_output": {"tool_use_id": "c1"}, "total_cost_usd": 0.002},
                    {"structured_output": {"tool_use_id": "none"}, "total_cost_usd": 0.002},
                    {"structured_output": {"tool_use_id": "c3"}, "total_cost_usd": 0.002},
                ],
            }
        )
        report = self.run_cli("calibrate", "--labels", labels, "--model", "model-a", "--model", "model-b")
        self.assertEqual(report["total"], 3)
        by_model = {entry["model"]: entry for entry in report["results"]}
        self.assertEqual(by_model["model-a"]["agreement"], "3/3")
        self.assertEqual(by_model["model-a"]["fraction"], 1.0)
        self.assertEqual(by_model["model-a"]["mismatches"], [])
        self.assertAlmostEqual(by_model["model-a"]["cost_usd"], 0.003)

        self.assertEqual(by_model["model-b"]["agreement"], "1/3")
        self.assertAlmostEqual(by_model["model-b"]["fraction"], 1 / 3)
        self.assertEqual(
            by_model["model-b"]["mismatches"],
            [
                {"case": "IM-02", "expected": "c2", "got": "none"},
                {"case": "IM-07", "expected": "none", "got": "c3"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
