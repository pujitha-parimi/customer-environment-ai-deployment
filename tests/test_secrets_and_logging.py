import json
import logging
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import secrets_provider
from logging_config import JsonFormatter, redact


class FakeVault(BaseHTTPRequestHandler):
    reads = 0
    logins = 0
    data = {"gemini_api_key": "vault-gemini", "customer_api_tokens": "vault-tok1,vault-tok2"}

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/v1/auth/approle/login" and payload == {"role_id": "rid", "secret_id": "sid"}:
            FakeVault.logins += 1
            return self._send(200, {"auth": {"client_token": "hvs.faketoken123", "lease_duration": 900}})
        self._send(403, {"errors": ["denied"]})

    def do_GET(self):
        if self.path == "/v1/secret/data/support-app" and self.headers.get("X-Vault-Token") == "hvs.faketoken123":
            FakeVault.reads += 1
            return self._send(200, {"data": {"data": FakeVault.data}})
        self._send(403, {"errors": ["denied"]})


class TestSecrets(unittest.TestCase):
    def setUp(self):
        secrets_provider.reset_for_tests()

    def test_clean_secret_strips_quotes_crlf_whitespace(self):
        self.assertEqual(secrets_provider.clean_secret('  "abc"\r\n'), "abc")
        self.assertEqual(secrets_provider.clean_secret("abc\r\n"), "abc")

    def test_file_beats_env_and_reads_fresh_for_rotation(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("file-v1\n")
        try:
            with patch.dict(os.environ, {"METRICS_TOKEN": "env", "METRICS_TOKEN_FILE": f.name}):
                self.assertEqual(secrets_provider.get_secret("METRICS_TOKEN"), "file-v1")
                with open(f.name, "w") as g:
                    g.write("file-v2")
                self.assertEqual(secrets_provider.get_secret("METRICS_TOKEN"), "file-v2")
        finally:
            os.unlink(f.name)

    def test_env_fallback_and_missing(self):
        with patch.dict(os.environ, {"METRICS_TOKEN": "e"}):
            self.assertEqual(secrets_provider.get_secret("METRICS_TOKEN"), "e")
        self.assertEqual(secrets_provider.get_secret("METRICS_TOKEN"), "")

    def test_vault_approle_kv_read_with_caching(self):
        FakeVault.reads = FakeVault.logins = 0
        server = HTTPServer(("127.0.0.1", 0), FakeVault)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        d = tempfile.mkdtemp()
        for name, val in (("rid_f", "rid"), ("sid_f", "sid")):
            with open(os.path.join(d, name), "w") as g:
                g.write(val + "\n")
        env = {"VAULT_ADDR": f"http://127.0.0.1:{server.server_port}",
               "VAULT_ROLE_ID_FILE": os.path.join(d, "rid_f"),
               "VAULT_SECRET_ID_FILE": os.path.join(d, "sid_f")}
        try:
            with patch.dict(os.environ, env):
                self.assertEqual(secrets_provider.get_secret("GEMINI_API_KEY"), "vault-gemini")
                self.assertEqual(secrets_provider.get_secret("CUSTOMER_API_TOKENS"), "vault-tok1,vault-tok2")
                self.assertEqual(FakeVault.logins, 1)
                self.assertEqual(FakeVault.reads, 1)     # second get served from cache
                self.assertEqual(secrets_provider.vault_status(), "ok")
        finally:
            server.shutdown()
            server.server_close()

    def test_vault_down_reports_unavailable_and_falls_back_to_env(self):
        env = {"VAULT_ADDR": "http://127.0.0.1:9", "GEMINI_API_KEY": "env-key"}
        with patch.dict(os.environ, env):
            self.assertEqual(secrets_provider.get_secret("GEMINI_API_KEY"), "env-key")
            self.assertEqual(secrets_provider.vault_status(), "unavailable")


class TestLogging(unittest.TestCase):
    def test_redacts_known_secret_shapes(self):
        for raw in ("key AQ.Ab8RN6Kexample_secret-1234", "AIzaSyA1234567890abcdefghijk",
                    "Authorization: Bearer abcDEF123456", "token hvs.CAESIabcdef123456",
                    "api_key=supersecretvalue"):
            out = redact(raw)
            self.assertIn("[REDACTED]", out, raw)
            for leaked in ("Ab8RN6", "AIzaSyA12", "abcDEF123456", "CAESIabc", "supersecretvalue"):
                self.assertNotIn(leaked, out)

    def test_json_formatter_redacts_message_fields_and_exceptions(self):
        rec = logging.LogRecord("t", logging.ERROR, "f", 1, "failed key=AQ.Ab8RN6Kexample1234", (), None)
        rec.fields = {"detail": "Bearer abcDEF123456", "status": 502}
        try:
            raise RuntimeError("AQ.Ab8RN6Kexample1234")
        except RuntimeError:
            import sys
            rec.exc_info = sys.exc_info()
        line = JsonFormatter().format(rec)
        self.assertNotIn("Ab8RN6", line)
        self.assertNotIn("abcDEF123456", line)
        self.assertEqual(json.loads(line)["status"], 502)


if __name__ == "__main__":
    unittest.main(verbosity=2)
