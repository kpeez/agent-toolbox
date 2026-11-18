import unittest
from api import create_from_api

class ApiTests(unittest.TestCase):
    def test_create_shipment(self):
        self.assertEqual(create_from_api({"origin": "A", "destination": "B"}),
                         {"origin": "A", "destination": "B"})

if __name__ == "__main__":
    unittest.main()
