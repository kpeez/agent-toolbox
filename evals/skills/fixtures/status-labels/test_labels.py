import unittest
from labels import status_label

class LabelTests(unittest.TestCase):
    def test_pending_label(self):
        self.assertEqual(status_label("pending"), "Pending")

if __name__ == "__main__":
    unittest.main()
