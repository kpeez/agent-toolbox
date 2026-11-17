import unittest
from receipt import format_total

class ReceiptTests(unittest.TestCase):
    def test_total(self):
        self.assertEqual(format_total(1205), "$12.05")

    def test_refund_total(self):
        self.assertEqual(format_total(-250), "-$2.50")

    def test_thousands(self):
        self.assertEqual(format_total(123456), "$1,234.56")

if __name__ == "__main__":
    unittest.main()
