import unittest
from amounts import with_fee

class AmountTests(unittest.TestCase):
    def test_zero_fee(self):
        self.assertEqual(with_fee(1200, 0.0), 1200)

if __name__ == "__main__":
    unittest.main()
