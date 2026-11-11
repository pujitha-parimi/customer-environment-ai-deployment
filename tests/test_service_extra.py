import unittest
from unittest.mock import patch

import service
from llm_client import LLMError


class TestServiceExtra(unittest.TestCase):
    def test_classification_tolerates_punctuation_and_case(self):
        with patch("service.ask_gemini", return_value=' "Billing." '):
            self.assertEqual(service.classify_query("x"), "billing")

    @patch("service.handle_billing_query", return_value="B")
    @patch("service.ask_gemini", return_value="billing")
    def test_end_to_end_with_mocked_gemini_calls(self, mock_ask, mock_billing):
        self.assertEqual(service.route_query("Refund please"), ("billing", "B"))

    def test_too_long_and_nul_inputs_do_not_call_gemini(self):
        with patch("service.ask_gemini") as ask:
            self.assertFalse(service.route_query("a" * 2001)[1].startswith("Order"))
            self.assertIn("invalid characters", service.route_query("bad\x00text")[1])
            ask.assert_not_called()

    def test_gemini_failure_propagates_as_llm_error(self):
        with patch("service.ask_gemini", side_effect=LLMError("upstream_error")):
            with self.assertRaises(LLMError):
                service.route_query("Where can I find pricing?")

    def test_lowercase_order_id_is_found(self):
        category, answer = service.route_query("track my order ord1002")
        self.assertIn("Processing", answer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
