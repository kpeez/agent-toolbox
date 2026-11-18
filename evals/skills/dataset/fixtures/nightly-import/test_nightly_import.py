import json
import tempfile
import unittest
from pathlib import Path

from nightly_import import run


class NightlyImportTests(unittest.TestCase):
    def tmp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return Path(folder.name)

    def test_imports_every_inbox_file_in_name_order(self):
        out = self.tmp() / "readings.jsonl"
        self.assertEqual(run("inbox", out), 6)
        rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["station_id"] for row in rows], ["E-01", "E-02", "N-01", "N-02", "S-01", "S-02"])
        self.assertEqual(rows[2], {"reading": "12.5", "station_id": "N-01", "unit": "mm"})


if __name__ == "__main__":
    unittest.main()
