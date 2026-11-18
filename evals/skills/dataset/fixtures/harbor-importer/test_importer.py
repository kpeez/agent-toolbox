import unittest
from importer import read_rows

class ImporterTests(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(read_rows(""), [])

    def test_regular_records(self):
        self.assertEqual(read_rows("sku,count\na7,2\nb4,5\n"),
                         [{"sku": "a7", "count": "2"}, {"sku": "b4", "count": "5"}])

if __name__ == "__main__":
    unittest.main()
