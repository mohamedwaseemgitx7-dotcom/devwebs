"""Health checks (#74), liveness & readiness probes (#75), dependency health (#76) and metrics (#103)."""

import hmac
import time
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest

from app.cache import catalog_cache
from app.deps import DbDep, SettingsDep

router = APIRouter(tags=["health"])
STARTED = time.time()
DB_UP = Gauge("flashcart_dependency_up", "1 if the dependency answered its last health check", ["dependency"])
DB_LATENCY = Gauge("flashcart_dependency_latency_seconds", "Latency of the last dependency ping", ["dependency"])


@router.get("/healthz", include_in_schema=False)
async def liveness():
    """Liveness: the process is up and the event loop responds. Deliberately does NOT touch the database —
    a DB outage should make the pod unready, not get it restarted in a loop."""
    return {"status": "ok"}


async def _db_check(db) -> tuple[bool, float]:
    start = time.perf_counter()
    try:
        await db.command("ping")
        ok = True
    except Exception:  # noqa: BLE001 - health checks report, never raise
        ok = False
    elapsed = time.perf_counter() - start
    DB_UP.labels("mongodb").set(1 if ok else 0)
    DB_LATENCY.labels("mongodb").set(elapsed)
    return ok, elapsed


@router.get("/readyz", include_in_schema=False)
async def readiness(db: DbDep, response: Response):
    ok, _ = await _db_check(db)
    if not ok:
        response.status_code = 503
        return {"status": "unavailable", "dependencies": {"mongodb": "down"}}
    return {"status": "ready", "dependencies": {"mongodb": "up"}}


@router.get("/api/v1/health")
async def health(db: DbDep, settings: SettingsDep, response: Response):
    """Detailed status consumed by CloudOps Sentinel. Contains no secrets or internal hostnames."""
    ok, elapsed = await _db_check(db)
    response.headers["Cache-Control"] = "no-store"
    if not ok:
        response.status_code = 503
    return {
        "status": "ok" if ok else "degraded",
        "version": settings.app_version,
        "environment": settings.env,
        "uptime_seconds": round(time.time() - STARTED, 1),
        "dependencies": {"mongodb": {"status": "up" if ok else "down", "latency_ms": round(elapsed * 1000, 2)}},
        "cache": {"hits": catalog_cache.hits, "misses": catalog_cache.misses},
    }


@router.get("/metrics", include_in_schema=False)
async def metrics(settings: SettingsDep, authorization: Annotated[str | None, Header()] = None):
    if settings.metrics_token is not None:
        expected = f"Bearer {settings.metrics_token.get_secret_value()}"
        if not authorization or not hmac.compare_digest(authorization.encode(), expected.encode()):
            raise HTTPException(status_code=401, detail="Not authenticated")
    elif settings.is_production:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
