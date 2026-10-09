import unittest
from balance import balance

class BalanceTests(unittest.TestCase):
    def test_empty_ledger(self):
        self.assertEqual(balance([]), 0)
    def test_one_entry(self):
        self.assertEqual(balance([{"cents": 50}]), 50)
    def test_same_one_entry_again(self):
        self.assertEqual(balance([{"cents": 50}]), 50)

if __name__ == "__main__":
    unittest.main()
