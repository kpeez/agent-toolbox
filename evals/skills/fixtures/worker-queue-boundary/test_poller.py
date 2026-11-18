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

    def test_returns_item_arriving_at_timeout(self):
        class Clock:
            def __init__(self):
                self.now = 0
            def __call__(self):
                return self.now
            def sleep(self, seconds):
                self.now += seconds
        class Queue:
            def __init__(self, clock):
                self.clock = clock
            def pop(self):
                return "job-2" if self.clock() >= 2 else None
        clock = Clock()
        self.assertEqual(wait_for_item(Queue(clock), clock, 2, 1), "job-2")


if __name__ == "__main__":
    unittest.main()
