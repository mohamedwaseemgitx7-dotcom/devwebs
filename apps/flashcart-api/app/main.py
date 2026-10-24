"""FlashCart API application factory."""

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import Scope

from app.config import Settings, get_settings
from app.db import close_client, ensure_schema, get_db
from app.logging_setup import configure_logging, request_id_var
from app.middleware import (
    BodySizeLimitMiddleware,
    ObservabilityMiddleware,
    OriginVerifyMiddleware,
    RateLimitMiddleware,
    TimeoutMiddleware,
)
from app.ratelimit import TokenBucketLimiter
from app.routers import admin, auth, cart, favorites, health, orders, products, webhooks
from app.security import hash_password

log = logging.getLogger("flashcart")


async def bootstrap_admin(settings: Settings) -> None:
    """Creates the first admin from env vars if no admin exists. Never resets an existing password."""
    if not (settings.admin_email and settings.admin_password):
        return
    db = get_db(settings)
    if await db["users"].count_documents({"role": "admin"}, limit=1):
        return
    await db["users"].update_one(
        {"email": settings.admin_email.lower()},
        {"$setOnInsert": {
            "email": settings.admin_email.lower(),
            "name": "Administrator",
            "password_hash": hash_password(settings.admin_password.get_secret_value()),
            "role": "admin",
            "token_version": 0,  # nosec B105 - session counter, not a password
            "created_at": datetime.now(UTC),
        }},
        upsert=True,
    )
    log.info("bootstrap admin ensured")


def create_app(settings: Settings | None = None, *, run_migrations: bool = True) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if run_migrations:
            await ensure_schema(get_db(settings))
            await bootstrap_admin(settings)
        log.info("startup complete", extra={"env": settings.env, "version": settings.app_version})
        yield
        await close_client()

    docs = not settings.is_production
    app = FastAPI(
        title="FlashCart API",
        version=settings.app_version,
        description="E-commerce API for FlashCart. All prices are integer paise (INR × 100).",
        lifespan=lifespan,
        docs_url="/api/docs" if docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs else None,
    )
    app.state.trust_cdn_headers = settings.origin_verify_secret is not None

    for r in (health.router, auth.router, products.router, cart.router, orders.router, favorites.router,
              admin.router, webhooks.router):
        app.include_router(r)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        # Return field locations and messages only — never echo the submitted values back.
        errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(HTTPException)
    async def http_handler(_: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        # Full details go to the log (with request ID); the client gets a generic message (no stack traces).
        log.exception("unhandled error", extra={"error_type": type(exc).__name__})
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id_var.get()},
        )

    limiter = TokenBucketLimiter(settings.rate_limit_per_minute)

    def rate_key(scope: Scope) -> str:
        headers = dict(scope["headers"])
        viewer = headers.get(b"cloudfront-viewer-address", b"").decode("latin-1")
        if viewer and app.state.trust_cdn_headers:
            return viewer.rsplit(":", 1)[0]
        return (scope.get("client") or ("unknown",))[0]

    # Starlette runs the LAST added middleware FIRST. Effective order for a request:
    # Observability → OriginVerify → BodySize → RateLimit → Timeout → CORS → routes
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Requested-With", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After", "Idempotent-Replayed"],
        max_age=600,
    )
    app.add_middleware(TimeoutMiddleware, seconds=settings.request_timeout_seconds)
    app.add_middleware(RateLimitMiddleware, limiter=limiter, key_func=rate_key)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(
        OriginVerifyMiddleware,
        secret=settings.origin_verify_secret.get_secret_value() if settings.origin_verify_secret else None,
    )
    app.add_middleware(ObservabilityMiddleware, hsts=settings.is_production)
    return app
