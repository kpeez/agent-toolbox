import unittest
from labels import notification_title

class NotificationLabelTests(unittest.TestCase):
    def test_title(self):
        self.assertEqual(notification_title(), "Notifications")

if __name__ == "__main__":
    unittest.main()
