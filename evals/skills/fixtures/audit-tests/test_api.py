import unittest
from api import create, _validate

class ApiTests(unittest.TestCase):
    def test_private_validator_accepts_complete(self):
        self.assertEqual(_validate({"origin": "A", "destination": "B"}), [])
    def test_create_complete(self):
        self.assertEqual(create({"origin": "A", "destination": "B"}), ("A", "B"))
    def test_batch_same_contract(self):
        self.assertEqual(create({"origin": "A", "destination": "B"}), ("A", "B"))

if __name__ == "__main__":
    unittest.main()
