import unittest
from app import run_import

class ImportTests(unittest.TestCase):
    def test_csv_rows_are_normalized(self):
        self.assertEqual(run_import("csv", "id,name\n 7 , Ada \n"),
                         [{"id": "7", "name": "Ada"}])

if __name__ == "__main__":
    unittest.main()
