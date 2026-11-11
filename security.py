"""Bearer-token verification (constant-time, supports multiple tokens for rotation)."""
import hmac

from secrets_provider import get_secret


def configured_tokens(secret_name: str) -> list[str]:
    return [t.strip() for t in get_secret(secret_name).split(",") if t.strip()]


def verify_token(presented: str | None, secret_name: str) -> bool:
    """True if `presented` equals any configured token. Fails closed if none are set."""
    tokens = configured_tokens(secret_name)
    if not presented or not tokens:
        return False
    presented_bytes = presented.encode()
    ok = False
    for token in tokens:  # no early exit: constant work per configured token
        ok |= hmac.compare_digest(presented_bytes, token.encode())
    return ok
