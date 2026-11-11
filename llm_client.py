"""Gemini access layer. The only module that talks to the Google SDK.

* The SDK is imported lazily so the rest of the app (and the unit tests) work
  without it and without a key.
* Errors are mapped to LLMError(reason) with NO provider message text, so keys,
  URLs or customer text can never leak through exception strings.
"""
from __future__ import annotations

import logging
import threading

from config import get_settings
from secrets_provider import get_secret

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Gemini call failed. `reason` is a short, safe, low-cardinality label."""

    def __init__(self, reason: str, status_code: int | None = None):
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


class LLMConfigError(LLMError):
    """The Gemini API key is not configured."""

    def __init__(self):
        super().__init__("not_configured")


_lock = threading.Lock()
_client = None
_client_key = ""


def _build_client(api_key: str, timeout_seconds: int):
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=timeout_seconds * 1000),
    )


def _get_client():
    """Return a cached client; rebuild automatically when the key is rotated."""
    global _client, _client_key
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        raise LLMConfigError()
    with _lock:
        if _client is None or api_key != _client_key:
            _client = _build_client(api_key, get_settings().gemini_timeout_seconds)
            _client_key = api_key
        return _client


def _reason_for(status_code) -> str:
    if status_code == 400:
        return "bad_request_or_invalid_key"   # Gemini returns 400 API_KEY_INVALID
    if status_code in (401, 403):
        return "unauthorized"
    if status_code == 404:
        return "model_not_found"
    if status_code == 429:
        return "rate_limited"
    if isinstance(status_code, int) and status_code >= 500:
        return "upstream_error"
    return "unknown"


def ask_gemini(prompt: str) -> str:
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")
    client = _get_client()
    try:
        response = client.models.generate_content(
            model=get_settings().gemini_model, contents=prompt
        )
        text = response.text
    except LLMError:
        raise
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code is None and "Timeout" in type(exc).__name__:
            reason = "timeout"
        else:
            reason = _reason_for(code)
        logger.warning(
            "gemini call failed",
            extra={"fields": {"reason": reason, "status_code": code, "error_type": type(exc).__name__}},
        )
        raise LLMError(reason, code if isinstance(code, int) else None) from None
    return text.strip() if text and text.strip() else "I couldn't generate a response."
