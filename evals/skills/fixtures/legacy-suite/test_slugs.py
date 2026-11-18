import unittest
from slugs import slugify

class SlugTests(unittest.TestCase):
    def test_runs_of_spaces_make_one_dash(self):
        self.assertEqual(slugify("Hello   World"), "hello-world")

    def test_edges_are_trimmed(self):
        self.assertEqual(slugify("  Edge case "), "edge-case")

if __name__ == "__main__":
    unittest.main()
