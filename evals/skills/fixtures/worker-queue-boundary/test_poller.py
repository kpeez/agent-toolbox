import unittest
from poller import wait_for_item


class FakeClock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeQueue:
    def __init__(self, clock, arrive_at, item):
        self._clock = clock
        self._arrive_at = arrive_at
        self._item = item

    def pop(self):
        if self._clock() >= self._arrive_at:
            item, self._item = self._item, None
            return item
        return None


class PollerTests(unittest.TestCase):
    def test_returns_first_available_item(self):
        clock = FakeClock()
        queue = FakeQueue(clock, arrive_at=0, item="job-1")
        self.assertEqual(wait_for_item(queue, clock, timeout=5, interval=1), "job-1")

    def test_returns_item_arriving_at_timeout(self):
        clock = FakeClock()
        queue = FakeQueue(clock, arrive_at=10, item="job-2")
        self.assertEqual(wait_for_item(queue, clock, timeout=10, interval=4), "job-2")

    def test_ignores_item_arriving_after_timeout(self):
        clock = FakeClock()
        queue = FakeQueue(clock, arrive_at=11, item="job-3")
        self.assertIsNone(wait_for_item(queue, clock, timeout=10, interval=4))


if __name__ == "__main__":
    unittest.main()
