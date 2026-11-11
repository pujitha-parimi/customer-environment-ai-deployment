import os
import unittest
from unittest.mock import patch

import llm_client
import secrets_provider
from llm_client import LLMConfigError, LLMError
from tests.helpers import FakeAPIError, FakeGemini

LEAKY = "AQ.SuperSecretKeyValue1234567890 https://x?key=AQ.SuperSecretKeyValue1234567890"


class TestLLMClient(unittest.TestCase):
    def setUp(self):
        llm_client._client, llm_client._client_key = None, ""
        secrets_provider.reset_for_tests()
        self.env = patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-not-real"})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_returns_stripped_text(self):
        fake = FakeGemini(["  hello  "])
        with patch("llm_client._build_client", return_value=fake):
            self.assertEqual(llm_client.ask_gemini("hi"), "hello")

    def test_uses_configured_model(self):
        fake = FakeGemini(["x"])
        with patch.dict(os.environ, {"GEMINI_MODEL": "my-model-1"}), \
             patch("llm_client._build_client", return_value=fake):
            with patch.object(fake.models, "generate_content", wraps=fake.models.generate_content) as spy:
                llm_client.ask_gemini("hi")
                self.assertEqual(spy.call_args.kwargs["model"], "my-model-1")

    def test_empty_response_text_gets_fallback(self):
        with patch("llm_client._build_client", return_value=FakeGemini([""])):
            self.assertIn("couldn't generate", llm_client.ask_gemini("hi"))

    def test_missing_key_raises_config_error(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaises(LLMConfigError):
                llm_client.ask_gemini("hi")

    def test_status_codes_map_to_safe_reasons_without_leaking_message(self):
        cases = {400: "bad_request_or_invalid_key", 401: "unauthorized", 403: "unauthorized",
                 404: "model_not_found", 429: "rate_limited", 503: "upstream_error", 418: "unknown"}
        for code, reason in cases.items():
            llm_client._client, llm_client._client_key = None, ""
            with patch("llm_client._build_client", return_value=FakeGemini([FakeAPIError(code, LEAKY)])):
                with self.assertRaises(LLMError) as ctx:
                    llm_client.ask_gemini("hi")
            self.assertEqual(ctx.exception.reason, reason)
            self.assertNotIn("SuperSecret", str(ctx.exception))
            self.assertIsNone(ctx.exception.__cause__)  # raised `from None`

    def test_client_rebuilt_when_key_rotates(self):
        builds = []
        def build(key, timeout):
            builds.append(key)
            return FakeGemini(["a", "b"])
        with patch("llm_client._build_client", side_effect=build):
            llm_client.ask_gemini("1")
            llm_client.ask_gemini("2")
            self.assertEqual(builds, ["test-key-not-real"])
            with patch.dict(os.environ, {"GEMINI_API_KEY": "rotated-key"}):
                llm_client.ask_gemini("3")
            self.assertEqual(builds, ["test-key-not-real", "rotated-key"])

    def test_blank_prompt_rejected(self):
        with self.assertRaises(ValueError):
            llm_client.ask_gemini("  ")


if __name__ == "__main__":
    unittest.main(verbosity=2)
