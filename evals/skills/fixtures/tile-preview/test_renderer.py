import unittest

from renderer import render_tiles


class RendererTests(unittest.TestCase):
    def test_maps_color_names_to_normalized_codes(self):
        palette = [(" Sky ", "#00AAFF"), ("Ink", "000000")]
        tiles = [{"id": "t1", "colors": ["sky", "INK"]}, {"id": "t2", "colors": ["Ink"]}]
        self.assertEqual(render_tiles(tiles, palette),
                         [{"id": "t1", "colors": ["#00aaff", "#000000"]}, {"id": "t2", "colors": ["#000000"]}])

    def test_unknown_color_name_raises(self):
        with self.assertRaises(KeyError):
            render_tiles([{"id": "t1", "colors": ["mauve"]}], [("Sky", "#00AAFF")])


if __name__ == "__main__":
    unittest.main()
