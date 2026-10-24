"""Pure-ASGI middleware: request IDs, access logging, metrics, security headers, body limits, timeouts.

Written as raw ASGI (not BaseHTTPMiddleware) so streaming bodies are limited without buffering and the
timeout wraps the whole downstream call.
"""

import asyncio
import hmac
import logging
import re
import secrets
import time

from prometheus_client import Counter, Gauge, Histogram
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.logging_setup import request_id_var

log = logging.getLogger("flashcart.http")

REQUESTS = Counter("flashcart_http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram(
    "flashcart_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
IN_FLIGHT = Gauge("flashcart_http_in_flight_requests", "Requests currently being processed")

_RID_OK = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
    # The API only returns JSON; nothing may be rendered or framed from it.
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"),
]


def _route_label(scope: Scope) -> str:
    route = scope.get("route")
    return getattr(route, "path", None) or "unmatched"


async def _send_json(send: Send, status: int, body: bytes, extra: list | None = None) -> None:
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    await send({"type": "http.response.start", "status": status, "headers": headers + (extra or [])})
    await send({"type": "http.response.body", "body": body})


class ObservabilityMiddleware:
    """Assigns X-Request-ID, logs one structured line per request, records Prometheus metrics, adds headers."""

    def __init__(self, app: ASGIApp, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        rid = incoming if _RID_OK.match(incoming) else secrets.token_hex(8)
        token = request_id_var.set(rid)
        start = time.perf_counter()
        status_holder = {"status": 500}
        IN_FLIGHT.inc()

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", rid.encode()))
                headers.extend(SECURITY_HEADERS)
                if self.hsts:
                    headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            IN_FLIGHT.dec()
            elapsed = time.perf_counter() - start
            route = _route_label(scope)
            REQUESTS.labels(scope["method"], route, str(status_holder["status"])).inc()
            LATENCY.labels(scope["method"], route).observe(elapsed)
            log.info(
                "request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "route": route,
                    "status": status_holder["status"],
                    "duration_ms": round(elapsed * 1000, 2),
                    "client": (scope.get("client") or ("-",))[0],
                },
            )
            request_id_var.reset(token)


class BodySizeLimitMiddleware:
    """Rejects request bodies larger than max_bytes with 413, whether or not Content-Length is sent."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > self.max_bytes):
            await _send_json(send, 413, b'{"detail":"Request body too large"}')
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await _send_json(send, 413, b'{"detail":"Request body too large"}')


class _BodyTooLarge(Exception):
    pass


class TimeoutMiddleware:
    """Bounds total request time so a slow dependency cannot pin a worker forever (timeouts, #10)."""

    def __init__(self, app: ASGIApp, seconds: float) -> None:
        self.app = app
        self.seconds = seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = {"value": False}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                started["value"] = True
            await send(message)

        try:
            await asyncio.wait_for(self.app(scope, receive, send_wrapper), timeout=self.seconds)
        except TimeoutError:
            log.warning("request timed out", extra={"path": scope["path"], "timeout_s": self.seconds})
            if not started["value"]:
                await _send_json(send, 504, b'{"detail":"Request timed out"}')


RATE_LIMITED = Counter("flashcart_rate_limited_total", "Requests rejected by the rate limiter")


class RateLimitMiddleware:
    """Per-client token bucket for all API traffic (health probes exempt). Returns 429 with Retry-After."""

    EXEMPT = ("/healthz", "/readyz", "/metrics")

    def __init__(self, app: ASGIApp, limiter, key_func) -> None:
        self.app = app
        self.limiter = limiter
        self.key_func = key_func

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in self.EXEMPT:
            await self.app(scope, receive, send)
            return
        allowed, retry_after = self.limiter.check(self.key_func(scope))
        if not allowed:
            RATE_LIMITED.inc()
            await _send_json(send, 429, b'{"detail":"Too many requests"}',
                             [(b"retry-after", str(retry_after).encode())])
            return
        await self.app(scope, receive, send)


class OriginVerifyMiddleware:
    """In production, only accept requests that came through CloudFront (which injects a secret header).

    Health endpoints stay open so external uptime checks work against the origin too.
    """

    OPEN_PATHS = ("/healthz",)

    def __init__(self, app: ASGIApp, secret: str | None) -> None:
        self.app = app
        self.secret = secret.encode() if secret else None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.secret is None or scope["path"] in self.OPEN_PATHS:
            await self.app(scope, receive, send)
            return
        supplied = dict(scope["headers"]).get(b"x-origin-verify", b"")
        if not hmac.compare_digest(supplied, self.secret):
            await _send_json(send, 403, b'{"detail":"Forbidden"}')
            return
        await self.app(scope, receive, send)
