import unittest
from versions import parse_version

class VersionTests(unittest.TestCase):
    def test_numbers_compare_as_numbers(self):
        self.assertGreater(parse_version("1.10.0"), parse_version("1.9.0"))

    def test_a_leading_v_is_ignored(self):
        self.assertEqual(parse_version("v2.1"), (2, 1))

if __name__ == "__main__":
    unittest.main()
