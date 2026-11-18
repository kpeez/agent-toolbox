import unittest

from normalizer import normalize


class NormalizerTests(unittest.TestCase):
    def test_renames_aliases_and_strips_values(self):
        self.assertEqual(normalize([{"station": " N-01 ", "value": " 12.5 ", "unit": "mm"}], "aliases.json"),
                         [{"station_id": "N-01", "reading": "12.5", "unit": "mm"}])


if __name__ == "__main__":
    unittest.main()
