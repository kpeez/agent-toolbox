from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


class FacetMapContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="facets-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        for part in ("plugins", "evals/skills"):
            shutil.copytree(REPO / part, self.root / part, ignore=ignore)

    def cli(self, command):
        return subprocess.run(
            [sys.executable, str(self.root / "evals/skills/facets.py"), command],
            check=False,
            text=True,
            capture_output=True,
            cwd=self.root,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def append_step(self, playbook, line):
        path = self.root / playbook
        path.write_text(
            path.read_text(encoding="utf-8") + line + "\n", encoding="utf-8"
        )

    def test_check_fails_on_a_stale_map_until_write(self):
        self.assertEqual(
            self.cli("check").returncode, 0, "the checked-in map must match the sources"
        )
        self.append_step(
            "plugins/lab/skills/lab-mode/playbooks/analyze-results.md",
            "12-regrade-the-conclusion: Grade the conclusion again. (grade-the-evidence)",
        )
        stale = self.cli("check")
        self.assertEqual(stale.returncode, 1, stale.stderr)
        self.assertIn("facets.py write", stale.stderr)
        self.assertEqual(self.cli("write").returncode, 0)
        self.assertEqual(self.cli("check").returncode, 0)
        ids = {
            f["id"]
            for f in json.loads((self.root / "evals/skills/facets.json").read_text())[
                "facets"
            ]
        }
        self.assertIn(
            "step-load/lab/analyze-results/12-regrade-the-conclusion/grade-the-evidence",
            ids,
        )

    def test_write_rejects_a_step_name_nothing_owns(self):
        playbook = "plugins/swe/skills/swe-mode/playbooks/build-feature.md"
        self.append_step(playbook, "15-extra-step: Do the extra step. (no-such-skill)")
        result = self.cli("write")
        self.assertNotEqual(result.returncode, 0)
        for fragment in (playbook, "15-extra-step", "no-such-skill"):
            self.assertIn(fragment, result.stderr)

    def test_write_rejects_a_routed_skill_without_handle_steps(self):
        skill = "plugins/swe/skills/handoff/SKILL.md"
        path = self.root / skill
        path.write_text(
            path.read_text(encoding="utf-8")
            .replace("## 1-find-the-record", "## Find the record")
            .replace("## 2-update-the-issue", "## Update the issue")
            .replace("## 3-close-the-log", "## Close the log")
            .replace("## 4-seed-the-next-session", "## Seed the next session"),
            encoding="utf-8",
        )
        result = self.cli("write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(skill, result.stderr)

    def test_write_reads_each_mode_of_a_skill_into_its_own_handle_list(self):
        path = self.root / "plugins/swe/skills/ship-pr/SKILL.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace("`5-merge`:", "`5-merge-the-pr`:"),
            encoding="utf-8",
        )
        self.assertEqual(self.cli("write").returncode, 0)
        route = next(
            f
            for f in json.loads((self.root / "evals/skills/facets.json").read_text())["facets"]
            if f["id"] == "route/swe/ship-pr"
        )
        self.assertEqual(route["handles"], [])
        self.assertEqual(route["modes"]["land"][-1], "5-merge-the-pr")
        self.assertEqual(route["modes"]["publish"][-1], "7-report")

    def test_write_rejects_a_name_that_two_classes_own(self):
        reference = (
            self.root / "plugins/swe/skills/swe-mode/references/plan-multi-phase.md"
        )
        reference.parent.mkdir(exist_ok=True)
        reference.write_text("# plan-multi-phase\n", encoding="utf-8")
        playbook = "plugins/swe/skills/swe-mode/playbooks/build-feature.md"
        self.append_step(
            playbook, "15-extra-step: Do the extra step. (plan-multi-phase)"
        )
        result = self.cli("write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("plan-multi-phase", result.stderr)
        self.assertIn("more than one class", result.stderr)


if __name__ == "__main__":
    unittest.main()
