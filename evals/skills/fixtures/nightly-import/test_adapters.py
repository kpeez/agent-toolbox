import tempfile
import unittest
from pathlib import Path

from csv_adapter import read_csv
from json_adapter import read_json
from jsonl_adapter import read_jsonl


class AdapterTests(unittest.TestCase):
    def tmp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return Path(folder.name)

    def write(self, name, text):
        path = self.tmp() / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_csv_rows_are_dictionaries(self):
        path = self.write("a.csv", "station,value\nN-01,1.5\n")
        self.assertEqual(read_csv(path), [{"station": "N-01", "value": "1.5"}])

    def test_json_reads_a_list(self):
        path = self.write("a.json", '[{"station_id": "E-01"}]')
        self.assertEqual(read_json(path), [{"station_id": "E-01"}])

    def test_jsonl_skips_blank_lines(self):
        path = self.write("a.jsonl", '{"station": "S-01"}\n\n{"station": "S-02"}\n')
        self.assertEqual(read_jsonl(path), [{"station": "S-01"}, {"station": "S-02"}])


if __name__ == "__main__":
    unittest.main()
