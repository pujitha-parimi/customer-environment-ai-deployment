import os

# Tests must never read the developer's real .env or call a real Gemini API.
os.environ["SUPPORT_DISABLE_DOTENV"] = "1"
for _name in ("GEMINI_API_KEY", "CUSTOMER_API_TOKENS", "METRICS_TOKEN", "VAULT_ADDR",
              "GEMINI_API_KEY_FILE", "CUSTOMER_API_TOKENS_FILE", "METRICS_TOKEN_FILE"):
    os.environ.pop(_name, None)
