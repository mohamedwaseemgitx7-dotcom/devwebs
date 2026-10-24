"""Rate limiting (concept #2).

- General API traffic: in-process token bucket per client IP. Cheap (no DB round trip) but per instance —
  on Lambda each concurrent instance has its own bucket, so the effective limit is limit × instances.
  The hard global ceiling in production is Lambda reserved concurrency (see docs/ARCHITECTURE.md).
- Login/signup: fixed-window counter stored in MongoDB with a TTL index, so the limit holds across all
  instances. These endpoints are low-volume, so the extra DB operation is affordable on Atlas M0.
"""

import math
import time
from collections import OrderedDict
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase


def client_ip(request: Request) -> str:
    # Behind CloudFront the viewer IP is in CloudFront-Viewer-Address ("ip:port"); only trusted when the
    # origin-verify middleware has already proven the request came via CloudFront.
    viewer = request.headers.get("cloudfront-viewer-address")
    if viewer and getattr(request.app.state, "trust_cdn_headers", False):
        return viewer.rsplit(":", 1)[0]
    return request.client.host if request.client else "unknown"


class TokenBucketLimiter:
    def __init__(self, per_minute: int, max_keys: int = 10_000) -> None:
        self.rate = per_minute / 60.0
        self.capacity = float(per_minute)
        self.max_keys = max_keys
        self._buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()

    def check(self, key: str) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds). Bounded memory: oldest keys are evicted (memory leaks, #16)."""
        now = time.monotonic()
        tokens, last = self._buckets.pop(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.rate)
        allowed = tokens >= 1
        if allowed:
            tokens -= 1
        self._buckets[key] = (tokens, now)
        if len(self._buckets) > self.max_keys:
            self._buckets.popitem(last=False)
        retry = 0 if allowed else math.ceil((1 - tokens) / self.rate)
        return allowed, retry


async def enforce_db_limit(db: AsyncDatabase, *, bucket: str, key: str, limit: int, window_s: int = 60) -> None:
    now = datetime.now(UTC)
    window_start = int(now.timestamp()) // window_s * window_s
    doc = await db["rate_limits"].find_one_and_update(
        {"_id": f"{bucket}:{key}:{window_start}"},
        {
            "$inc": {"count": 1},
            "$setOnInsert": {"expires_at": now + timedelta(seconds=window_s * 2)},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if doc["count"] > limit:
        retry = window_start + window_s - int(now.timestamp())
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please wait and try again.",
            headers={"Retry-After": str(max(retry, 1))},
        )
