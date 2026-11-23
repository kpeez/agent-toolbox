"""Score one real Claude Code transcript per harness version through the capture and score CLI.

Admission: protects the claim that a completed real session of each fixture version scores with
every Skill load proved and no issue. The credible regression is a harness shape the scorer does
not read, such as a filled placeholder or a new record or attachment type, which makes every real
run partial. The hand-built transcripts in test_skill_eval.py hold only the shapes someone wrote
down. Seen red at fcb44b7 (filled session id), ab79deb (filled $ARGUMENTS), and 0ae7a24
(silent_turn_reminder). To add a version, run fixtures/claude-transcripts/reduce.py on an eval run.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from corpus_io import read_cases, se

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "claude-transcripts"


class RealClaudeTranscripts(unittest.TestCase):
    def cli(self, *args):
        result = subprocess.run(
            [sys.executable, str(se.HERE / "skill_eval.py"), *map(str, args)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_each_version_scores_with_every_load_proved_and_no_issue(self):
        versions = sorted(
            path for path in FIXTURES.iterdir() if (path / "transcript.jsonl").is_file()
        )
        self.assertTrue(versions)
        case = next(
            c
            for c in read_cases()
            if not c.get("expected_route") and not c.get("facets")
        )
        for fixture in versions:
            with (
                self.subTest(version=fixture.name),
                tempfile.TemporaryDirectory() as temp,
            ):
                run = Path(temp) / "run"
                skills = json.loads(
                    (fixture / "skills.json").read_text(encoding="utf-8")
                )
                plugin = run / "inputs" / "plugins" / next(iter(skills)).split(":")[0]
                (plugin / ".claude-plugin").mkdir(parents=True)
                (plugin / ".claude-plugin" / "plugin.json").write_text(
                    json.dumps({"name": plugin.name})
                )
                frozen = {}
                for skill, text in skills.items():
                    file = plugin / "skills" / skill.split(":")[1] / "SKILL.md"
                    file.parent.mkdir(parents=True)
                    file.write_text(text, encoding="utf-8")
                    frozen[skill] = {
                        "path": str(file),
                        "sha256": se.digest(file.read_bytes()),
                        "body_sha256": se.digest(se.delivered_body(text).encode()),
                    }
                (run / "workspace").mkdir()
                se.save_json(
                    run / "manifest.json",
                    {
                        "schema_version": 1,
                        "case_id": case["id"],
                        "corpus_sha256": se.digest(se.DATASET.read_bytes()),
                        "hook_arm": "hook-off",
                        "runtime": {},
                        "skills": frozen,
                        "resources": {},
                        "input_files": se.inventory(run / "inputs"),
                        "source_catalog_files": {},
                        "removed_bindings": [],
                        "fixture_catalog_files": {},
                        "harness_sha256": "",
                    },
                )
                transcript = Path(temp) / "transcript.jsonl"
                transcript.write_text(
                    (fixture / "transcript.jsonl")
                    .read_text(encoding="utf-8")
                    .replace("@PLUGIN_ROOT@", str(plugin)),
                    encoding="utf-8",
                )
                self.cli(
                    "capture",
                    "--run",
                    run,
                    "--source",
                    transcript,
                    "--state",
                    "completed",
                    "--format",
                    "claude-transcript",
                    "--plugin-dir",
                    plugin,
                    "--stream",
                    fixture / "stream.jsonl",
                    "--relevant-action",
                    "none",
                )
                score = self.cli("score", "--run", run)
                evidence = json.loads(
                    (run / "evidence.json").read_text(encoding="utf-8")
                )
                observed = {
                    "coverage": score["evidence_coverage"],
                    "issues": evidence["issues"],
                    "warnings": score.get("warnings", []),
                    "loads": sorted(
                        [load["skill"], load["status"], load["detail"]]
                        for load in evidence["loads"]
                    ),
                }
                expected = {
                    "coverage": "complete",
                    "issues": [],
                    "warnings": [],
                    "loads": sorted([skill, "success", None] for skill in skills),
                }
                self.assertEqual(observed, expected)


if __name__ == "__main__":
    unittest.main()
