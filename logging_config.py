"""Structured JSON logging with secret redaction.

Customer message text is never logged - only metadata (length, category, ids).
"""
from __future__ import annotations

import json
import logging
import re
import sys
import traceback
from datetime import datetime, timezone

from config import get_settings

_PATTERNS = [
    re.compile(r"AQ\.[A-Za-z0-9_.\-]{8,}"),            # Google 'AQ.' keys
    re.compile(r"AIza[0-9A-Za-z_\-]{16,}"),            # legacy Google keys
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=\-]{6,}"),
    re.compile(r"hv[sbr]\.[A-Za-z0-9_\-]{8,}"),        # Vault tokens
    re.compile(r"(?i)(api[_-]?key|token|secret|password)(\s*[=:]\s*)[^\s,;\"']+"),
]


def redact(text: str) -> str:
    for pattern in _PATTERNS:
        if pattern.groups >= 2:
            text = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        for key, value in (getattr(record, "fields", None) or {}).items():
            entry[key] = redact(value) if isinstance(value, str) else value
        if record.exc_info:
            entry["exception"] = redact("".join(traceback.format_exception(*record.exc_info)))
        return json.dumps(entry, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(get_settings().log_level)
    # Keep third-party libraries from logging request URLs/headers.
    for noisy in ("httpx", "httpcore", "google_genai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
