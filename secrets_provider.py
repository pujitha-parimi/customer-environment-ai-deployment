"""Secret resolution with rotation support.

Resolution order for each secret NAME (e.g. GEMINI_API_KEY):
  1. HashiCorp Vault KV v2 via AppRole, when VAULT_ADDR is set
  2. file whose path is in NAME_FILE (Docker/Kubernetes secrets, Vault Agent)
  3. plain environment variable NAME (local development only)

Values are re-read on every call (files) or cached briefly (Vault), so a
rotated secret takes effect without restarting the application. Secret values
are never logged.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request

from config import Settings, get_settings

logger = logging.getLogger(__name__)

# env/file name -> key inside the Vault secret
SECRET_KEYS = {
    "GEMINI_API_KEY": "gemini_api_key",
    "CUSTOMER_API_TOKENS": "customer_api_tokens",
    "METRICS_TOKEN": "metrics_token",
}

VAULT_CACHE_TTL = 30.0       # seconds a fetched secret set is reused
VAULT_STALE_GRACE = 300.0    # serve last-known values this long if Vault is down
VAULT_TIMEOUT = 3.0


def clean_secret(value: str) -> str:
    """Trim whitespace/CRLF and one pair of wrapping quotes (common .env mistake)."""
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value


def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return clean_secret(handle.read())
    except OSError:
        return ""


class VaultClient:
    """Minimal Vault HTTP client (AppRole login + KV v2 read) using only stdlib."""

    def __init__(self, settings: Settings):
        self.s = settings
        self._lock = threading.Lock()
        self._token = ""
        self._token_expiry = 0.0
        self._data: dict = {}
        self._data_time = 0.0
        self.last_ok = False

    def _call(self, method: str, path: str, body: dict | None = None, token: str = "") -> dict:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Vault-Token"] = token
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.s.vault_addr + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=VAULT_TIMEOUT) as resp:  # noqa: S310 (operator-configured URL)
            return json.loads(resp.read().decode())

    def _login(self) -> None:
        role_id = _read_file(self.s.vault_role_id_file)
        secret_id = _read_file(self.s.vault_secret_id_file)
        if not role_id or not secret_id:
            raise RuntimeError("vault approle credentials missing")
        auth = self._call("POST", "/v1/auth/approle/login", {"role_id": role_id, "secret_id": secret_id})["auth"]
        ttl = float(auth.get("lease_duration", 60))
        self._token = auth["client_token"]
        self._token_expiry = time.monotonic() + ttl * 0.8

    def _fetch(self) -> dict:
        if not self._token or time.monotonic() >= self._token_expiry:
            self._login()
        path = f"/v1/{self.s.vault_kv_mount}/data/{self.s.vault_secret_path}"
        try:
            return self._call("GET", path, token=self._token)["data"]["data"]
        except urllib.error.HTTPError as exc:
            if exc.code == 403:  # token revoked/expired early: log in once more
                self._login()
                return self._call("GET", path, token=self._token)["data"]["data"]
            raise

    def get(self, key: str) -> str:
        with self._lock:
            now = time.monotonic()
            if now - self._data_time >= VAULT_CACHE_TTL or not self._data:
                try:
                    self._data = self._fetch()
                    self._data_time = now
                    self.last_ok = True
                except Exception as exc:  # never include exc text: may hold URLs/ids
                    self.last_ok = False
                    logger.warning("vault read failed", extra={"fields": {"error_type": type(exc).__name__}})
                    if now - self._data_time > VAULT_STALE_GRACE:
                        self._data = {}
            return clean_secret(str(self._data.get(key, "")))


_vault: VaultClient | None = None
_vault_lock = threading.Lock()


def _vault_client(settings: Settings) -> VaultClient:
    global _vault
    with _vault_lock:
        if _vault is None or _vault.s != settings:
            _vault = VaultClient(settings)
        return _vault


def reset_for_tests() -> None:
    global _vault
    _vault = None


def get_secret(name: str) -> str:
    settings = get_settings()
    if settings.vault_addr and name in SECRET_KEYS:
        value = _vault_client(settings).get(SECRET_KEYS[name])
        if value:
            return value
    path = os.getenv(f"{name}_FILE", "").strip()
    if path:
        value = _read_file(path)
        if value:
            return value
    return clean_secret(os.getenv(name, ""))


def vault_status() -> str:
    """'disabled' | 'ok' | 'unavailable' - for the readiness probe."""
    settings = get_settings()
    if not settings.vault_addr:
        return "disabled"
    client = _vault_client(settings)
    client.get("gemini_api_key")  # triggers a (cached) fetch
    return "ok" if client.last_ok else "unavailable"
