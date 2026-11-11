
import unittest
from unittest.mock import patch

import service


class TestOrderRouting(unittest.TestCase):

    @patch("service.classify_query")
    def test_existing_order(self, mock_classify):
        category, answer = service.route_query(
            "Where is my order ORD1001?"
        )

        self.assertEqual(category, "general")
        self.assertIn("Shipped", answer)
        self.assertIn("sample demonstration data", answer)
        mock_classify.assert_not_called()

    @patch("service.classify_query")
    def test_missing_order_id(self, mock_classify):
        category, answer = service.route_query(
            "Where is my order?"
        )

        self.assertIn("order ID", answer)
        mock_classify.assert_not_called()

    @patch("service.classify_query")
    def test_unknown_order(self, mock_classify):
        category, answer = service.route_query(
            "Track my order ORD9999"
        )

        self.assertIn("Order not found", answer)
        mock_classify.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
