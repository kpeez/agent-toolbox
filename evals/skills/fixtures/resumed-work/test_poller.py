import unittest
from poller import wait_for_item


class FakeClock:
    def __init__(self, start=0):
        self.now = start

    def __call__(self):
        return self.now

    def sleep(self, interval):
        self.now += interval


class FakeQueue:
    def __init__(self, clock, arrive_at, item):
        self._clock = clock
        self._arrive_at = arrive_at
        self._item = item

    def pop(self):
        if self._clock() >= self._arrive_at:
            item = self._item
            self._item = None
            return item
        return None


class PollerTests(unittest.TestCase):
    def test_returns_item_available_immediately(self):
        clock = FakeClock(start=0)
        queue = FakeQueue(clock, arrive_at=0, item="job-1")
        self.assertEqual(wait_for_item(queue, clock, timeout=10, interval=5), "job-1")
        self.assertEqual(clock(), 0)

    def test_returns_item_arriving_at_timeout_boundary(self):
        clock = FakeClock(start=0)
        queue = FakeQueue(clock, arrive_at=10, item="job-2")
        self.assertEqual(wait_for_item(queue, clock, timeout=10, interval=5), "job-2")


if __name__ == "__main__":
    unittest.main()
