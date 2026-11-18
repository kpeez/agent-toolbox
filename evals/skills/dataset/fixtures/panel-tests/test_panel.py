import unittest
from panel import render_panel, render_row

class PanelTests(unittest.TestCase):
    def test_private_row_helper_formats_label(self):
        self.assertEqual(render_row("Mode", "quiet"), "Mode: quiet")
    def test_panel_contains_formatted_row(self):
        self.assertIn("Mode: quiet", render_panel([("Mode", "quiet")]))
    def test_panel_uses_row_helper(self):
        self.assertEqual(render_panel([("Mode", "quiet")]), "Mode: quiet")

if __name__ == "__main__":
    unittest.main()
