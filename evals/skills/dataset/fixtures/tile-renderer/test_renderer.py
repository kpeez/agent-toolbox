import unittest
from renderer import render_tiles

class RendererTests(unittest.TestCase):
    def test_maps_color_names(self):
        self.assertEqual(render_tiles([{"id": "t1", "colors": ["blue"]}],
                                      {"blue": "#00f"}),
                         [{"id": "t1", "colors": ["#00f"]}])

if __name__ == "__main__":
    unittest.main()
