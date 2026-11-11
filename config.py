"""Central, non-secret configuration read from environment variables.

Secrets (API keys, tokens) are deliberately NOT part of Settings; they are
resolved on demand by secrets_provider so they can be rotated without restart.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

# Local-development convenience only. Containers do not ship a .env file.
if os.getenv("SUPPORT_DISABLE_DOTENV") != "1":
    try:
        from dotenv import load_dotenv

        load_dotenv(override=False)
    except ImportError:  # python-dotenv is optional at runtime
        pass

DEFAULT_MODEL = "gemini-2.5-flash"
_MODEL_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(low, min(high, value))


@dataclass(frozen=True)
class Settings:
    gemini_model: str
    gemini_timeout_seconds: int
    log_level: str
    max_query_length: int
    enable_docs: bool
    vault_addr: str
    vault_kv_mount: str
    vault_secret_path: str
    vault_role_id_file: str
    vault_secret_id_file: str

    @classmethod
    def from_env(cls) -> "Settings":
        model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip()
        if not _MODEL_RE.match(model):
            model = DEFAULT_MODEL
        level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        return cls(
            gemini_model=model,
            gemini_timeout_seconds=_int("GEMINI_TIMEOUT_SECONDS", 30, 1, 120),
            log_level=level if level in _LEVELS else "INFO",
            max_query_length=_int("MAX_QUERY_LENGTH", 2000, 1, 2000),
            enable_docs=_bool("ENABLE_DOCS", True),
            vault_addr=os.getenv("VAULT_ADDR", "").strip().rstrip("/"),
            vault_kv_mount=os.getenv("VAULT_KV_MOUNT", "secret").strip("/ "),
            vault_secret_path=os.getenv("VAULT_SECRET_PATH", "support-app").strip("/ "),
            vault_role_id_file=os.getenv("VAULT_ROLE_ID_FILE", "/run/secrets/vault_role_id"),
            vault_secret_id_file=os.getenv("VAULT_SECRET_ID_FILE", "/run/secrets/vault_secret_id"),
        )


def get_settings() -> Settings:
    """Read settings fresh each call (cheap) so tests/ops changes are honoured."""
    return Settings.from_env()
