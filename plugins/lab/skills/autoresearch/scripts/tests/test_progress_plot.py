"""Behavioral checks for the shared progress plot's public CLI.

Run with: uv run --with matplotlib python -m unittest discover -s scripts/tests
from the autoresearch skill directory.
"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "plot_trials.py"
LEDGER = SCRIPT.with_name("ledger.py")


class ProgressPlotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        self.config = {
            "metric": "loss", "label": "Validation loss", "direction": "minimize",
            "title": "Synthetic validation run",
        }
        self.records = [self.record(0, "keep", 1.0), self.record(1, "discard", 1.2)]
        self.write_inputs()

    def record(self, number, status, value):
        return {"id": number, "commit": "a" * 40, "status": status,
                "description": f"exp{number:03d}-recipe", "metrics": {"loss": value}}

    def write_inputs(self):
        (self.run / "trial-plot.json").write_text(json.dumps(self.config))
        (self.run / "results.jsonl").write_text(
            "".join(json.dumps(record) + "\n" for record in self.records))

    def invoke(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), str(self.run), *args],
                              capture_output=True, text=True)

    def test_reads_latest_ledger_without_export_and_preserves_inputs(self):
        # An obsolete derived export must not hide the newly appended bad value.
        (self.run / "old-trial-runs.jsonl").write_text("obsolete export")
        subprocess.run([sys.executable, str(LEDGER), "append", str(self.run),
                        "--commit", "b" * 40, "--status", "keep",
                        "--description", "exp002-improvement", "--metric", "loss=0.9"],
                       check=True, capture_output=True)
        before = {name: (self.run / name).read_bytes()
                  for name in ("results.jsonl", "trial-plot.json")}
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.run / "progress.png").read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(before, {name: (self.run / name).read_bytes() for name in before})
        subprocess.run([sys.executable, str(LEDGER), "append", str(self.run),
                        "--commit", "c" * 40, "--status", "keep",
                        "--description", "exp003-invalid", "--metric", "loss=NaN"],
                       check=True, capture_output=True)
        self.assertNotEqual(self.invoke("--validate").returncode, 0)

    def test_missing_objective_is_not_a_successful_candidate(self):
        self.records[1]["metrics"] = {"other": 2.0}
        self.write_inputs()
        result = self.invoke("--validate")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("loss", result.stderr)

    def test_kept_objective_cannot_regress_in_either_direction(self):
        for direction, worse in (("minimize", 1.1), ("maximize", 0.9)):
            with self.subTest(direction=direction):
                self.config["direction"] = direction
                self.records = [self.record(0, "keep", 1.0), self.record(1, "keep", worse)]
                self.write_inputs()
                self.assertNotEqual(self.invoke("--validate").returncode, 0)
                self.records[1]["metrics"]["loss"] = 1.0
                self.write_inputs()
                self.assertEqual(self.invoke("--validate").returncode, 0)

    def test_empty_and_unmeasured_crash_runs_render(self):
        for records in ([], [self.record(0, "crash", None)]):
            with self.subTest(records=records):
                self.records = records
                self.write_inputs()
                result = self.invoke()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue((self.run / "progress.png").is_file())

    def test_calibration_is_not_candidate_progress(self):
        self.records[0]["description"] = "calibration: exp000-500-steps"
        self.write_inputs()
        result = self.invoke("--validate")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("calibration", result.stderr.lower())

    def test_old_multi_metric_configuration_requires_explicit_migration(self):
        self.config = {"primary_metric": "loss", "metrics": {"loss": {"direction": "minimize"}}}
        self.write_inputs()
        self.assertNotEqual(self.invoke("--validate").returncode, 0)


if __name__ == "__main__":
    unittest.main()
