import unittest
from store import mark_delivery

class StoreTests(unittest.TestCase):
    def test_accepted_delivery_is_sent(self):
        self.assertEqual(mark_delivery({"state": "queued"}, {"status": "accepted"})["state"], "sent")

if __name__ == "__main__":
    unittest.main()
