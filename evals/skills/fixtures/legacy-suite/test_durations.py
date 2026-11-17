import unittest
from durations import format_duration

class DurationTests(unittest.TestCase):
    def test_zero_units_are_dropped(self):
        self.assertEqual(format_duration(59), "59s")

    def test_hours_minutes_seconds(self):
        self.assertEqual(format_duration(3725), "1h 2m 5s")

    def test_whole_minutes_drop_seconds(self):
        self.assertEqual(format_duration(120), "2m")

if __name__ == "__main__":
    unittest.main()
