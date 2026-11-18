import unittest
from search import visible_records

class SearchTests(unittest.TestCase):
    def test_query_matches_titles_without_case_sensitivity(self):
        rows = [{"title": "Maple"}, {"title": "Pine"}]
        self.assertEqual(visible_records("MAP", rows), [{"title": "Maple"}])

if __name__ == "__main__":
    unittest.main()
