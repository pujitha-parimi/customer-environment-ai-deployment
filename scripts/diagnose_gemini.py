"""Diagnose a Gemini API key WITHOUT ever printing it.

    python scripts/diagnose_gemini.py            # offline: key shape checks only
    python scripts/diagnose_gemini.py --live     # one free 'list models' request

Replaces check_gemini_config.py / check_key_details.py / list_gemini_models.py.
Uses only the standard library so it works even if dependencies are broken.
Output contains: key family (AQ./AIza/other), length, formatting flags, and
the HTTP status + Google error *reason code*. Never the key, never the message text.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from secrets_provider import get_secret  # noqa: E402  (also loads .env via config)

HINTS = {
    ("400", "API_KEY_INVALID"): "Google does not recognise this key. Causes: key revoked/deleted, copied with missing characters, "
                                "or the key belongs to a different Google API (e.g. Vertex AI) than generativelanguage.googleapis.com. "
                                "Create a NEW key in Google AI Studio (https://aistudio.google.com/apikey), paste it once, retry.",
    ("401", None): "Key type/credential not accepted by this endpoint. Regenerate the key in AI Studio and confirm the project has the "
                   "Generative Language API enabled.",
    ("403", None): "Key is recognised but not permitted: API not enabled on the project, key restrictions (API/IP/referrer), "
                   "billing, or unsupported region.",
    ("404", None): "Endpoint/model not found - check GEMINI_MODEL against the model list printed below.",
    ("429", None): "Quota or rate limit reached for this key/project.",
}


def shape(key: str) -> None:
    family = "AQ." if key.startswith("AQ.") else "AIza" if key.startswith("AIza") else "other/unknown"
    print(f"Key present            : {bool(key)}")
    print(f"Length                 : {len(key)}")
    print(f"Key family             : {family}   (AI Studio now issues 'AQ.' keys; legacy keys start 'AIza')")
    print(f"Contains whitespace    : {any(c.isspace() for c in key)}")
    print(f"Contains quote chars   : {any(c in key for c in chr(34) + chr(39))}")
    print(f"Contains placeholder   : {'your_' in key.lower() or 'placeholder' in key.lower()}")
    print(f"Non-ASCII characters   : {any(ord(c) > 127 for c in key)}")


def live(key: str, model: str) -> int:
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=100",
        headers={"x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            names = [m.get("name", "").removeprefix("models/") for m in json.load(resp).get("models", [])]
    except urllib.error.HTTPError as exc:
        try:
            err = json.load(exc).get("error", {})
        except Exception:
            err = {}
        reason = next((d.get("reason") for d in err.get("details", []) if isinstance(d, dict) and d.get("reason")), None)
        print(f"\nLIVE CHECK FAILED  : HTTP {exc.code}  status={err.get('status')}  reason={reason}")
        print("Meaning            :", HINTS.get((str(exc.code), reason)) or HINTS.get((str(exc.code), None)) or "See Google AI docs for this status.")
        return 1
    except Exception as exc:
        print(f"\nLIVE CHECK NOT COMPLETED: {type(exc).__name__} (network/DNS/proxy problem - key not evaluated)")
        return 2
    print(f"\nLIVE CHECK OK      : key accepted; {len(names)} models visible")
    print(f"Configured model   : {model}  -> {'AVAILABLE' if model in names else 'NOT in list; set GEMINI_MODEL to one below'}")
    for n in names:
        if "gemini" in n:
            print("  ", n)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="send one free list-models request to Google")
    args = ap.parse_args()
    key = get_secret("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    shape(key)
    if not key:
        print("\nNo key found (GEMINI_API_KEY / GEMINI_API_KEY_FILE / Vault).")
        return 1
    return live(key, model) if args.live else 0


if __name__ == "__main__":
    sys.exit(main())
