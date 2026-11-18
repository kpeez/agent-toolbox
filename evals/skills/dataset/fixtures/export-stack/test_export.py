import io
import os
import tempfile
import unittest

from export import main, write_rows


class ExportTests(unittest.TestCase):
    def test_header_and_row(self):
        out = io.StringIO()
        write_rows([{"number": "INV-2", "customer": "Birch", "cents": 990}], out)
        self.assertEqual(out.getvalue(), "number,customer,total\nINV-2,Birch,9.90\n")

    def test_quotes_a_comma(self):
        out = io.StringIO()
        write_rows([{"number": "INV-1", "customer": "Acme, Ltd", "cents": 1205}], out)
        self.assertIn('"Acme, Ltd"', out.getvalue())

    def test_out_flag_writes_a_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "invoices.csv")
            main(["--out", path])
            with open(path) as written:
                self.assertTrue(written.read().startswith("number,customer,total\n"))


if __name__ == "__main__":
    unittest.main()
