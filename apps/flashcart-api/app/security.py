"""Password hashing and token handling.

Access tokens: short-lived JWTs (HS256) sent in the Authorization header, held only in browser memory.
Refresh tokens: opaque random IDs in an HttpOnly, SameSite=Strict cookie, rotated on every use. Reusing an
already-rotated refresh token revokes the whole token family (stolen-token detection, concept #47).
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import Settings

_hasher = PasswordHasher()  # Argon2id with library defaults (RFC 9106 recommended parameters)
# Pre-computed hash used to equalise timing when the user does not exist (prevents user enumeration).
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")

JWT_ALG = "HS256"
JWT_ISSUER = "flashcart-api"
JWT_AUDIENCE = "flashcart-web"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def _key_id(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()[:8]


def create_access_token(settings: Settings, *, user_id: str, role: str, token_version: int) -> str:
    secret = settings.jwt_secret.get_secret_value()
    now = datetime.now(UTC)
    claims = {
        "sub": user_id,
        "role": role,
        "tv": token_version,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(claims, secret, algorithm=JWT_ALG, headers={"kid": _key_id(secret)})


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    """Verify with the current key, or the previous key during a rotation window. Raises jwt.PyJWTError."""
    keys = [settings.jwt_secret.get_secret_value()]
    if settings.jwt_secret_previous:
        keys.append(settings.jwt_secret_previous.get_secret_value())
    kid = jwt.get_unverified_header(token).get("kid")
    candidates = [k for k in keys if _key_id(k) == kid] or keys[:1]
    return jwt.decode(
        token,
        candidates[0],
        algorithms=[JWT_ALG],  # fixed list: never trust the token's own "alg"
        audience=JWT_AUDIENCE,
        issuer=JWT_ISSUER,
        leeway=30,  # tolerate small clock skew between instances (concept #94)
        options={"require": ["exp", "iat", "sub", "aud", "iss"]},
    )


def new_refresh_token() -> tuple[str, str]:
    """Returns (raw token for the cookie, sha256 digest stored in the database)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)
