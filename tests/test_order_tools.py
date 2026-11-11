
import unittest

from tools.order_tools import get_order_status


class TestOrderTools(unittest.TestCase):

    def test_existing_order(self):
        result = get_order_status("ORD1001")

        self.assertTrue(result["found"])
        self.assertEqual(result["status"], "Shipped")

    def test_order_id_is_case_insensitive(self):
        result = get_order_status("ord1002")

        self.assertTrue(result["found"])
        self.assertEqual(result["status"], "Processing")

    def test_unknown_order(self):
        result = get_order_status("ORD9999")

        self.assertFalse(result["found"])

    def test_empty_order_id(self):
        result = get_order_status(" ")

        self.assertFalse(result["found"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
