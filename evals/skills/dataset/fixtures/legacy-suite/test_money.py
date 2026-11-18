import unittest
from money import format_cents

class MoneyTests(unittest.TestCase):
    def test_cents_have_two_digits(self):
        self.assertEqual(format_cents(5), "$0.05")

    def test_thousands_are_grouped(self):
        self.assertEqual(format_cents(123456), "$1,234.56")

if __name__ == "__main__":
    unittest.main()
