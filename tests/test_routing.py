
import unittest
from unittest.mock import patch

import service


class TestCustomerSupportRouting(unittest.TestCase):

    @patch("service.handle_support_query", return_value="General response")
    @patch("service.handle_billing_query", return_value="Billing response")
    @patch("service.handle_technical_query", return_value="Technical response")
    @patch("service.classify_query", return_value="general")
    def test_general_query(
        self, mock_classify, mock_technical, mock_billing, mock_support
    ):
        result = service.route_query("What are your working hours?")

        self.assertEqual(result, ("general", "General response"))
        mock_support.assert_called_once()

    @patch("service.handle_support_query", return_value="General response")
    @patch("service.handle_billing_query", return_value="Billing response")
    @patch("service.handle_technical_query", return_value="Technical response")
    @patch("service.classify_query", return_value="billing")
    def test_billing_query(
        self, mock_classify, mock_technical, mock_billing, mock_support
    ):
        result = service.route_query("I was charged twice.")

        self.assertEqual(result, ("billing", "Billing response"))
        mock_billing.assert_called_once()

    @patch("service.handle_support_query", return_value="General response")
    @patch("service.handle_billing_query", return_value="Billing response")
    @patch("service.handle_technical_query", return_value="Technical response")
    @patch("service.classify_query", return_value="technical")
    def test_technical_query(
        self, mock_classify, mock_technical, mock_billing, mock_support
    ):
        result = service.route_query("The website returns a 500 error.")

        self.assertEqual(result, ("technical", "Technical response"))
        mock_technical.assert_called_once()

    def test_empty_query(self):
        result = service.route_query("   ")

        self.assertEqual(
            result,
            ("general", "Please enter a question.")
        )

    @patch("service.ask_gemini")
    def test_empty_query_does_not_call_gemini(self, mock_gemini):
        result = service.route_query("   ")

        self.assertEqual(
            result,
            ("general", "Please enter a question.")
        )
        mock_gemini.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
