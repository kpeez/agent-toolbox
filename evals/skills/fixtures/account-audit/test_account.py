import unittest
from account import lockout

class AccountTests(unittest.TestCase):
    def test_below_limit(self):
        self.assertFalse(lockout(2, 3))
    def test_at_limit(self):
        self.assertTrue(lockout(3, 3))
    def test_greater_than_limit(self):
        self.assertTrue(lockout(4, 3))

if __name__ == "__main__":
    unittest.main()
