"""Password hashing and signed session tokens.

Stdlib-only (pbkdf2 + hmac) so we don't add bcrypt/PyJWT as dependencies —
keeps the lean deploy requirements lean. Good enough for a small personal app;
not meant to replace a real auth provider for a large multi-tenant product.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

_PBKDF2_ITERATIONS = 260_000
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2${_PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        scheme, iterations_s, salt_b64, digest_b64 = hashed.split("$")
        if scheme != "pbkdf2":
            return False
        iterations = int(iterations_s)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(user_id: int, secret_key: str, *, ttl_seconds: int = TOKEN_TTL_SECONDS) -> str:
    payload = {"uid": user_id, "exp": int(time.time()) + ttl_seconds}
    payload_b64 = _b64url_encode(json.dumps(payload).encode("utf-8"))
    sig = hmac.new(secret_key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_b64}.{_b64url_encode(sig)}"


def decode_token(token: str, secret_key: str) -> int | None:
    """Return the user id if the token is well-formed, unexpired, and correctly
    signed; otherwise None."""
    try:
        payload_b64, sig_b64 = token.split(".")
        expected_sig = hmac.new(
            secret_key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected_sig, _b64url_decode(sig_b64)):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return int(payload["uid"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
