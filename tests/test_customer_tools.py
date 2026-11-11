
import unittest

from tools.customer_tools import validate_customer_query


class TestCustomerTools(unittest.TestCase):

    def test_valid_query(self):
        result = validate_customer_query("I need help with my payment.")
        self.assertTrue(result["valid"])

    def test_empty_query(self):
        result = validate_customer_query("   ")
        self.assertFalse(result["valid"])

    def test_long_query(self):
        result = validate_customer_query("a" * 2001)
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

