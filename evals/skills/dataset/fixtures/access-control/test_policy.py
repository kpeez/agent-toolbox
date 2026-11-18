import unittest
from policy import can_read

class PolicyTests(unittest.TestCase):
    def test_reader_can_read_published_document(self):
        self.assertTrue(can_read({"role": "reader", "workspace": "w1"},
                                 {"published": True, "workspace": "w1"}))

    def test_writer_role_is_not_a_reader_role(self):
        self.assertFalse(can_read({"role": "writer", "workspace": "w1"},
                                  {"published": True, "workspace": "w1"}))

if __name__ == "__main__":
    unittest.main()
