import unittest
from paths import relative_to, common_prefix

class PathTests(unittest.TestCase):
    def test_relative_path_has_no_leading_slash(self):
        self.assertEqual(relative_to("/a/b/c", "/a"), "b/c")

    def test_common_prefix_ends_on_a_whole_segment(self):
        self.assertEqual(common_prefix(["/data/run1", "/data/run2"]), "/data")

if __name__ == "__main__":
    unittest.main()
