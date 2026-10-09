import unittest
from gateway import submit_charge

class FakeTransport:
    def __init__(self):
        self.ids = 0
        self.calls = []
    def new_request_id(self):
        self.ids += 1
        return "req-" + str(self.ids)
    def charge(self, request_id, account, amount):
        self.calls.append((request_id, account, amount))
        return {"status": "ok"}

class GatewayTests(unittest.TestCase):
    def test_successful_first_attempt(self):
        transport = FakeTransport()
        self.assertEqual(submit_charge(transport, "a2", 700), {"status": "ok"})
        self.assertEqual(len(transport.calls), 1)

if __name__ == "__main__":
    unittest.main()
