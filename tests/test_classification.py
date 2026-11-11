
import unittest
from unittest.mock import patch

import service


class TestQueryClassification(unittest.TestCase):

    @patch("service.ask_gemini", return_value="billing")
    def test_billing_category(self, mock_gemini):
        result = service.classify_query("I was charged twice.")
        self.assertEqual(result, "billing")

    @patch("service.ask_gemini", return_value="technical")
    def test_technical_category(self, mock_gemini):
        result = service.classify_query("The website shows an error.")
        self.assertEqual(result, "technical")

    @patch("service.ask_gemini", return_value="general")
    def test_general_category(self, mock_gemini):
        result = service.classify_query("Where can I find information?")
        self.assertEqual(result, "general")

    @patch("service.ask_gemini", return_value="unexpected output")
    def test_invalid_category_defaults_to_general(self, mock_gemini):
        result = service.classify_query("I have a question.")
        self.assertEqual(result, "general")


if __name__ == "__main__":
    unittest.main(verbosity=2)
