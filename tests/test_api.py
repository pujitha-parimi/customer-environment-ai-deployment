"""HTTP API tests. Mock Gemini at the SDK boundary (llm_client._build_client).

Skipped automatically if FastAPI/httpx are not installed (pip install -r requirements-dev.txt).
"""
import os
import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    HAVE_FASTAPI = True
except ImportError:  # pragma: no cover
    HAVE_FASTAPI = False

from tests.helpers import FakeAPIError, FakeGemini

CUSTOMER = "customer-token-123456"
METRICS = "metrics-token-123456"
AUTH = {"Authorization": f"Bearer {CUSTOMER}"}
LEAKY_KEY = "AQ.SuperSecretKeyValue1234567890"


@unittest.skipUnless(HAVE_FASTAPI, "fastapi/httpx not installed")
class TestAPI(unittest.TestCase):
    def setUp(self):
        import llm_client, secrets_provider
        llm_client._client, llm_client._client_key = None, ""
        secrets_provider.reset_for_tests()
        self.env = patch.dict(os.environ, {
            "GEMINI_API_KEY": LEAKY_KEY, "CUSTOMER_API_TOKENS": f"{CUSTOMER},second-token-abcdef",
            "METRICS_TOKEN": METRICS})
        self.env.start()
        import api
        self.client = TestClient(api.app, raise_server_exceptions=False)

    def tearDown(self):
        self.env.stop()

    def _gemini(self, replies):
        return patch("llm_client._build_client", return_value=FakeGemini(replies))

    # --- operations ---
    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "healthy")

    def test_ready_ok(self):
        r = self.client.get("/ready")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ready")
        self.assertNotIn("SuperSecret", r.text)

    def test_ready_not_ready_without_key_or_tokens(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "CUSTOMER_API_TOKENS": ""}):
            r = self.client.get("/ready")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["status"], "not_ready")

    def test_docs_available(self):
        self.assertEqual(self.client.get("/docs").status_code, 200)

    # --- /query success ---
    def test_query_success_billing(self):
        with self._gemini(["billing", "Please contact billing."]):
            r = self.client.post("/query", json={"query": "I was charged twice"}, headers=AUTH)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual((body["category"], body["answer"]), ("billing", "Please contact billing."))
        self.assertTrue(body["request_id"])
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")

    def test_query_routes_technical_and_general(self):
        with self._gemini(["technical", "Try resetting."]):
            self.assertEqual(self.client.post("/query", json={"query": "login fails"}, headers=AUTH).json()["category"], "technical")
        with self._gemini(["general", "We help."]):
            self.assertEqual(self.client.post("/query", json={"query": "what do you do"}, headers=AUTH).json()["category"], "general")

    def test_order_lookup_needs_no_gemini(self):
        with patch("llm_client._build_client", side_effect=AssertionError("Gemini must not be called")):
            r = self.client.post("/query", json={"query": "Where is my order ORD1001?"}, headers=AUTH)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Shipped", r.json()["answer"])

    def test_second_token_also_valid_for_rotation(self):
        with self._gemini(["general", "ok"]):
            r = self.client.post("/query", json={"query": "hello there"},
                                 headers={"Authorization": "Bearer second-token-abcdef"})
        self.assertEqual(r.status_code, 200)

    # --- auth ---
    def test_missing_wrong_and_malformed_auth_rejected(self):
        body = {"query": "hello"}
        self.assertEqual(self.client.post("/query", json=body).status_code, 401)
        self.assertEqual(self.client.post("/query", json=body, headers={"Authorization": "Bearer nope"}).status_code, 401)
        r = self.client.post("/query", json=body, headers={"Authorization": "Basic abc"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.headers["WWW-Authenticate"], "Bearer")

    def test_fail_closed_when_no_tokens_configured(self):
        with patch.dict(os.environ, {"CUSTOMER_API_TOKENS": ""}):
            r = self.client.post("/query", json={"query": "hello"}, headers=AUTH)
        self.assertEqual(r.status_code, 401)

    def test_metrics_requires_its_own_token(self):
        self.assertEqual(self.client.get("/metrics").status_code, 401)
        self.assertEqual(self.client.get("/metrics", headers=AUTH).status_code, 401)  # customer token not enough
        r = self.client.get("/metrics", headers={"Authorization": f"Bearer {METRICS}"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("http_requests_total", r.text)
        for secret in (LEAKY_KEY, CUSTOMER, METRICS):
            self.assertNotIn(secret, r.text)

    # --- validation ---
    def test_invalid_requests(self):
        for payload in ({}, {"query": ""}, {"query": "   "}, {"query": "a" * 2001},
                        {"query": 123}, {"query": "hi", "extra": "x"}):
            r = self.client.post("/query", json=payload, headers=AUTH)
            self.assertEqual(r.status_code, 422, payload)
            self.assertEqual(r.json()["detail"], "Invalid request.")
        r = self.client.post("/query", content="not json", headers={**AUTH, "Content-Type": "application/json"})
        self.assertEqual(r.status_code, 422)

    def test_validation_errors_do_not_echo_input(self):
        r = self.client.post("/query", json={"query": "x" * 2001}, headers=AUTH)
        self.assertNotIn("xxxxxxxxxx", r.text)

    # --- failure handling ---
    def test_gemini_failure_returns_502_without_leaking(self):
        with self._gemini([FakeAPIError(400, f"API key not valid {LEAKY_KEY}")]):
            r = self.client.post("/query", json={"query": "I need help with billing"}, headers=AUTH)
        self.assertEqual(r.status_code, 502)
        self.assertNotIn("SuperSecret", r.text)
        self.assertNotIn("API key", r.text)

    def test_missing_gemini_key_returns_503(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            r = self.client.post("/query", json={"query": "What is your policy?"}, headers=AUTH)
        self.assertEqual(r.status_code, 503)

    def test_unexpected_error_returns_generic_500(self):
        with patch("api.route_query", side_effect=RuntimeError("internal AQ.SuperSecretKeyValue1234567890")):
            r = self.client.post("/query", json={"query": "hello"}, headers=AUTH)
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.json(), {"detail": "Internal server error."})

    def test_error_metrics_recorded(self):
        with self._gemini([FakeAPIError(429)]):
            self.client.post("/query", json={"query": "billing question"}, headers=AUTH)
        text = self.client.get("/metrics", headers={"Authorization": f"Bearer {METRICS}"}).text
        self.assertIn('gemini_errors_total{reason="rate_limited"}', text)
        self.assertIn('status="502"', text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
