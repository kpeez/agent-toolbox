import unittest
from quote import monthly_total

class QuoteTests(unittest.TestCase):
    def test_one_month(self):
        self.assertEqual(monthly_total(500, 1), 500)
    def test_twelve_months(self):
        self.assertEqual(monthly_total(500, 12), 6000)
    def test_public_quote_for_one_month(self):
        self.assertEqual(monthly_total(500, 1), 500)
    def test_rejects_zero_months(self):
        with self.assertRaises(ValueError):
            monthly_total(500, 0)

if __name__ == "__main__":
    unittest.main()
