"""Test fixtures. Every test session uses its own throwaway database on the local MongoDB replica set
(FLASHCART_TEST_MONGODB_URI, default mongodb://127.0.0.1:27017/?replicaSet=rs0) and drops it afterwards."""

import os
import secrets
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from app import db as db_module
from app.cache import catalog_cache
from app.config import Settings
from app.db import ensure_schema
from app.deps import settings_dep
from app.main import create_app
from app.security import hash_password
from app.seed_data import build_products

MONGO_URI = os.environ.get("FLASHCART_TEST_MONGODB_URI", "mongodb://127.0.0.1:27017/?replicaSet=rs0")
TEST_DB = f"fc_test_{uuid.uuid4().hex[:8]}"
PASSWORD = "Str0ng!Passw0rd"


def make_settings(**overrides) -> Settings:
    values = dict(
        env="test",
        mongodb_uri=MONGO_URI,
        mongodb_db=TEST_DB,
        jwt_secret="t" * 48,
        webhook_secret="w" * 48,
        cookie_secure=False,
        cors_origins=["http://localhost:5173"],
        rate_limit_per_minute=100_000,
        auth_rate_limit_per_minute=100_000,
        metrics_token="metrics-token-for-tests",
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


@pytest.fixture(scope="session")
def settings() -> Settings:
    return make_settings()


@pytest.fixture(scope="session")
async def db(settings):
    database = db_module.get_db(settings)
    await ensure_schema(database)
    yield database
    await db_module.get_client(settings).drop_database(TEST_DB)
    await db_module.close_client()


def build_client(settings: Settings) -> httpx.AsyncClient:
    app = create_app(settings, run_migrations=False)
    app.dependency_overrides[settings_dep] = lambda: settings
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


@pytest.fixture
async def client(settings, db) -> AsyncIterator[httpx.AsyncClient]:
    async with build_client(settings) as c:
        yield c


@pytest.fixture(autouse=True)
async def clean_state(db):
    """Each test starts with a fresh catalog and no users/orders."""
    catalog_cache.clear()
    for name in ("users", "orders", "carts", "favorites", "refresh_tokens", "rate_limits", "webhook_events",
                 "audit_log", "products"):
        await db[name].delete_many({})
    docs = [{k: v for k, v in p.items() if k != "kind"} for p in build_products()]
    await db["products"].insert_many(docs)
    yield


async def signup(client: httpx.AsyncClient, email: str | None = None) -> dict:
    email = email or f"user-{secrets.token_hex(4)}@example.com"
    r = await client.post("/api/v1/auth/signup", json={"email": email, "name": "Test User", "password": PASSWORD})
    assert r.status_code == 201, r.text
    data = r.json()
    return {"email": email, "token": data["access_token"], "id": data["user"]["id"],
            "headers": {"Authorization": f"Bearer {data['access_token']}"}}


async def make_admin(client: httpx.AsyncClient, db) -> dict:
    email = f"admin-{secrets.token_hex(4)}@example.com"
    from datetime import UTC, datetime
    await db["users"].insert_one({"email": email, "name": "Admin", "password_hash": hash_password(PASSWORD),
                                  "role": "admin", "session_version": 0, "created_at": datetime.now(UTC)})
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"email": email, "headers": {"Authorization": f"Bearer {token}"}}


async def product_with_stock(db, minimum: int = 1) -> dict:
    p = await db["products"].find_one({"stock": {"$gte": minimum}, "active": True}, sort=[("_id", 1)])
    assert p, "seed data should contain a product with stock"
    return p


ADDRESS = {"full_name": "Asha Kumar", "line1": "12 MG Road", "city": "Bengaluru", "postal_code": "560001",
           "phone": "9876543210"}


def idem() -> dict:
    return {"Idempotency-Key": uuid.uuid4().hex}
