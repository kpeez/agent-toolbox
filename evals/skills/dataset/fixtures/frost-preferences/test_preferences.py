import unittest
from preferences import load_preferences, save_preferences

class PreferenceTests(unittest.TestCase):
    def test_missing_digest_defaults_off(self):
        self.assertEqual(load_preferences('{"time_zone":"UTC"}'),
                         {"time_zone": "UTC", "digest": False})

    def test_offset_survives_load_and_save(self):
        value = load_preferences('{"time_zone":"UTC-07:00","digest":true}')
        self.assertEqual(load_preferences(save_preferences(value)),
                         {"time_zone": "UTC-07:00", "digest": True})

if __name__ == "__main__":
    unittest.main()
