import unittest
from receipt import format_total, line_label

class ReceiptTests(unittest.TestCase):
    def test_total(self):
        self.assertEqual(format_total(1205), "$12.05")

    def test_refund_total(self):
        self.assertEqual(format_total(-250), "-$2.50")

    def test_line_label(self):
        self.assertEqual(line_label("item: tea"), "tea")

if __name__ == "__main__":
    unittest.main()
