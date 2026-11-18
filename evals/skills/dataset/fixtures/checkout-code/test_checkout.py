import unittest
from checkout import summarize

class CheckoutTests(unittest.TestCase):
    def test_line_count_counts_entries_not_units(self):
        self.assertEqual(summarize({"lines": [{"price_cents": 250, "quantity": 3}]}),
                         {"total_cents": 750, "line_count": 1})

if __name__ == "__main__":
    unittest.main()
