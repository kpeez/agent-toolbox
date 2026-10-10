import unittest
from session import valid

class SessionTests(unittest.TestCase):
    def test_rejects_exact_expiry(self):
        self.assertFalse(valid({"expires_at": 50}, 50))

if __name__ == "__main__":
    unittest.main()
