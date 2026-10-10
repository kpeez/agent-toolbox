import unittest
from poller import wait_for_item

class PollerTests(unittest.TestCase):
    def test_returns_first_available_item(self):
        class Clock:
            def __call__(self): return 0
            def sleep(self, seconds): pass
        class Queue:
            def pop(self): return "job-1"
        self.assertEqual(wait_for_item(Queue(), Clock(), 5, 1), "job-1")

if __name__ == "__main__":
    unittest.main()
