"""OPT-IN live smoke test: makes ONE real Gemini request using your configured key/model.

Not part of the automated suite (kept out of tests/ on purpose). Requires network + valid key.
    python scripts/verify_gemini_live.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm_client import LLMError, ask_gemini  # noqa: E402
from config import get_settings  # noqa: E402

print("Model:", get_settings().gemini_model)
try:
    print("Response:", ask_gemini("Reply with exactly: Gemini connection successful!"))
except LLMError as exc:
    print(f"FAILED: reason={exc.reason} http_status={exc.status_code}")
    print("Run: python scripts/diagnose_gemini.py --live")
    sys.exit(1)
