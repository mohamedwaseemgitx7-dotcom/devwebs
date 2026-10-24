"""Pure unit tests — no database."""

import time

import jwt
import pytest
from fastapi import HTTPException

from app.cache import TTLCache
from app.logging_setup import redact
from app.ratelimit import TokenBucketLimiter
from app.routers.webhooks import sign, verify
from app.security import create_access_token, decode_access_token, hash_password, verify_password
from app.services.pricing import shipping_fee
from tests.conftest import make_settings


def test_password_hash_roundtrip_and_no_plaintext():
    h = hash_password("Correct-Horse-9")
    assert h.startswith("$argon2id$") and "Correct-Horse-9" not in h
    assert verify_password(h, "Correct-Horse-9")
    assert not verify_password(h, "wrong")
    assert not verify_password(None, "anything")  # unknown user still runs a hash, returns False
    assert not verify_password("not-a-hash", "x")


def test_jwt_roundtrip_and_tamper_detection():
    s = make_settings()
    token = create_access_token(s, user_id="64b000000000000000000000", role="customer", token_version=0)
    assert decode_access_token(s, token)["sub"] == "64b000000000000000000000"
    other = make_settings(jwt_secret="x" * 48)
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(other, token)
    unsigned = jwt.encode({"sub": "x", "role": "admin"}, key=None, algorithm="none")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(s, unsigned)


def test_jwt_rotation_accepts_previous_key():
    old = make_settings(jwt_secret="o" * 48)
    token = create_access_token(old, user_id="64b000000000000000000000", role="customer", token_version=0)
    rotated = make_settings(jwt_secret="n" * 48, jwt_secret_previous="o" * 48)
    assert decode_access_token(rotated, token)["sub"] == "64b000000000000000000000"


def test_settings_reject_unsafe_values():
    with pytest.raises(ValueError):
        make_settings(jwt_secret="short")
    with pytest.raises(ValueError):
        make_settings(cors_origins=["*"])
    with pytest.raises(ValueError):
        make_settings(env="production", cookie_secure=True)  # missing origin_verify_secret
    with pytest.raises(ValueError):
        make_settings(env="production", cookie_secure=False, origin_verify_secret="o" * 40)


def test_token_bucket_blocks_then_refills(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    limiter = TokenBucketLimiter(per_minute=3)
    assert [limiter.check("ip")[0] for _ in range(4)] == [True, True, True, False]
    allowed, retry = limiter.check("ip")
    assert not allowed and retry >= 1
    clock[0] += 20  # 3/min → one token per 20 s
    assert limiter.check("ip")[0]


def test_token_bucket_memory_is_bounded():
    limiter = TokenBucketLimiter(per_minute=10, max_keys=100)
    for i in range(1000):
        limiter.check(f"ip-{i}")
    assert len(limiter._buckets) == 100


def test_ttl_cache_expiry_and_prefix_invalidation(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    cache = TTLCache(ttl_seconds=10)
    cache.set("products:a", 1)
    cache.set("other", 2)
    assert cache.get("products:a") == 1
    cache.invalidate_prefix("products:")
    assert cache.get("products:a") is None and cache.get("other") == 2
    clock[0] = 11
    assert cache.get("other") is None


@pytest.mark.parametrize(
    ("method", "subtotal", "fee"),
    [("regular", 50_000, 4_900), ("regular", 99_900, 0), ("economic", 10_000, 0), ("next_day", 200_000, 14_900),
     ("instant", 1_000, 29_900), ("regular", 0, 0)],
)
def test_shipping_fee(method, subtotal, fee):
    assert shipping_fee(method, subtotal) == fee


def test_webhook_signature_verification():
    body = b'{"id":"evt_1"}'
    header = sign("s" * 40, 1_700_000_000, body)
    verify("s" * 40, header, body, now=1_700_000_100)
    with pytest.raises(HTTPException):
        verify("s" * 40, header, body + b" ", now=1_700_000_100)  # tampered body
    with pytest.raises(HTTPException):
        verify("s" * 40, header, body, now=1_700_000_000 + 301)  # replay outside tolerance
    with pytest.raises(HTTPException):
        verify("s" * 40, "garbage", body)


def test_log_redaction():
    line = 'connecting mongodb+srv://user:pa55@cluster0.example.net/db password="hunter2" ' \
           'Authorization: Bearer abc eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N'  # gitleaks:allow - fabricated test token
    out = redact(line)
    assert "pa55" not in out and "hunter2" not in out and "eyJhbGciOiJIUzI1NiJ9" not in out
