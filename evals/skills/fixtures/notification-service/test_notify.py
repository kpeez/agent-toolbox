import unittest
from notify import deliver

class Transport:
    def __init__(self): self.sent = []
    def send(self, channel, message):
        self.sent.append((channel, message))
        return True

class NotifyTests(unittest.TestCase):
    def test_empty_channels_send_nothing(self):
        transport = Transport()
        self.assertEqual(deliver({"channels": []}, transport, "hello"), [])
        self.assertEqual(transport.sent, [])

    def test_send_uses_default_priority_without_mutating_input(self):
        transport = Transport()
        message = {"body": "hello"}
        deliver({"channels": ["email"]}, transport, message)
        self.assertEqual(transport.sent, [("email", {"body": "hello", "priority": "normal"})])
        self.assertEqual(message, {"body": "hello"})

if __name__ == "__main__":
    unittest.main()
