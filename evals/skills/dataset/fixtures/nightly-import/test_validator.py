import unittest

from validator import validate


class ValidatorTests(unittest.TestCase):
    def test_complete_rows_pass(self):
        rows = [{"station_id": "N-01", "reading": "1.5"}]
        self.assertEqual(validate(rows, "schema.json"), rows)

    def test_blank_required_field_names_the_row(self):
        with self.assertRaisesRegex(ValueError, "row 1: missing reading"):
            validate([{"station_id": "N-01", "reading": "1"}, {"station_id": "N-02", "reading": " "}], "schema.json")


if __name__ == "__main__":
    unittest.main()
