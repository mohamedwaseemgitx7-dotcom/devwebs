"""MongoDB client lifecycle, collection schema validation and indexes.

One AsyncMongoClient per process (connection pooling, concept #4). On Lambda the client lives at
module scope so warm invocations reuse the pool instead of reconnecting (cold starts, concept #87).
"""

import logging

from pymongo import ASCENDING, DESCENDING, TEXT, AsyncMongoClient, IndexModel
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import CollectionInvalid, OperationFailure

from app.config import Settings

log = logging.getLogger("flashcart.db")

SCHEMA_VERSION = 1

_client: AsyncMongoClient | None = None


def get_client(settings: Settings) -> AsyncMongoClient:
    global _client
    if _client is None:
        _client = AsyncMongoClient(
            settings.mongodb_uri.get_secret_value(),
            maxPoolSize=settings.mongodb_max_pool_size,
            minPoolSize=0,
            maxIdleTimeMS=60_000,
            serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
            connectTimeoutMS=settings.mongodb_timeout_ms,
            socketTimeoutMS=settings.mongodb_timeout_ms * 2,
            timeoutMS=settings.mongodb_timeout_ms * 2,
            retryWrites=True,
            retryReads=True,
            appname=f"flashcart-api/{settings.env}",
            tz_aware=True,
        )
    return _client


def get_db(settings: Settings) -> AsyncDatabase:
    return get_client(settings)[settings.mongodb_db]


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


# $jsonSchema validators: the database rejects malformed documents even if application code has a bug.
VALIDATORS: dict[str, dict] = {
    "users": {
        "bsonType": "object",
        "required": ["email", "password_hash", "role", "created_at"],
        "properties": {
            "email": {"bsonType": "string", "maxLength": 254},
            "name": {"bsonType": "string", "maxLength": 100},
            "password_hash": {"bsonType": "string"},
            "role": {"enum": ["customer", "admin"]},
            "token_version": {"bsonType": "int", "minimum": 0},
        },
    },
    "products": {
        "bsonType": "object",
        "required": ["sku", "name", "category", "price_paise", "stock", "version", "active"],
        "properties": {
            "sku": {"bsonType": "string", "maxLength": 40},
            "name": {"bsonType": "string", "minLength": 1, "maxLength": 120},
            "category": {"bsonType": "string", "maxLength": 40},
            "price_paise": {"bsonType": ["int", "long"], "minimum": 1},
            "stock": {"bsonType": ["int", "long"], "minimum": 0},
            "version": {"bsonType": ["int", "long"], "minimum": 1},
            "active": {"bsonType": "bool"},
            "rating": {"bsonType": ["double", "int"], "minimum": 0, "maximum": 5},
        },
    },
    "orders": {
        "bsonType": "object",
        "required": ["user_id", "items", "total_paise", "status", "idempotency_key", "created_at"],
        "properties": {
            "items": {"bsonType": "array", "minItems": 1, "maxItems": 50},
            "total_paise": {"bsonType": ["int", "long"], "minimum": 1},
            "status": {"enum": ["confirmed", "paid", "shipped", "delivered", "cancelled"]},
            "idempotency_key": {"bsonType": "string", "minLength": 8, "maxLength": 100},
        },
    },
    "carts": {
        "bsonType": "object",
        "required": ["user_id", "items"],
        "properties": {"items": {"bsonType": "array", "maxItems": 50}},
    },
}

INDEXES: dict[str, list[IndexModel]] = {
    "users": [IndexModel([("email", ASCENDING)], unique=True, name="uniq_email")],
    "products": [
        IndexModel([("sku", ASCENDING)], unique=True, name="uniq_sku"),
        IndexModel([("slug", ASCENDING)], unique=True, name="uniq_slug"),
        # Equality → sort → range (ESR) ordering for the common listing query.
        IndexModel([("active", ASCENDING), ("category", ASCENDING), ("rating", DESCENDING)], name="cat_rating"),
        IndexModel([("active", ASCENDING), ("category", ASCENDING), ("price_paise", ASCENDING)], name="cat_price"),
        IndexModel([("active", ASCENDING), ("sold_count", DESCENDING)], name="popular"),
        IndexModel(
            [("name", TEXT), ("brand", TEXT), ("description", TEXT)],
            weights={"name": 10, "brand": 5, "description": 1},
            name="text_search",
        ),
    ],
    "orders": [
        IndexModel([("user_id", ASCENDING), ("idempotency_key", ASCENDING)], unique=True, name="uniq_idem"),
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_orders"),
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="status_recent"),
    ],
    "carts": [IndexModel([("user_id", ASCENDING)], unique=True, name="uniq_user")],
    "favorites": [IndexModel([("user_id", ASCENDING)], unique=True, name="uniq_user")],
    "refresh_tokens": [
        IndexModel([("jti", ASCENDING)], unique=True, name="uniq_jti"),
        IndexModel([("family", ASCENDING)], name="family"),
        IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl"),
    ],
    "rate_limits": [IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl")],
    "webhook_events": [
        IndexModel([("event_id", ASCENDING)], unique=True, name="uniq_event"),
        IndexModel([("received_at", ASCENDING)], expireAfterSeconds=7 * 86400, name="ttl"),
    ],
    "audit_log": [
        IndexModel([("at", DESCENDING)], name="recent"),
        IndexModel([("actor_id", ASCENDING), ("at", DESCENDING)], name="actor"),
    ],
}


async def ensure_schema(db: AsyncDatabase) -> None:
    """Idempotent migration: create collections with validators and indexes (database migrations, #23)."""
    existing = set(await db.list_collection_names())
    for name in INDEXES:
        validator = {"$jsonSchema": VALIDATORS[name]} if name in VALIDATORS else None
        if name not in existing:
            try:
                await db.create_collection(name, validator=validator) if validator else await db.create_collection(name)
            except CollectionInvalid:
                pass  # created concurrently by another instance
        elif validator:
            await db.command({"collMod": name, "validator": validator, "validationLevel": "strict"})
        try:
            await db[name].create_indexes(INDEXES[name])
        except OperationFailure as exc:  # index option conflicts must be fixed by a migration, not ignored
            log.error("index creation failed", extra={"collection": name, "error": str(exc)})
            raise
    await db["schema_meta"].update_one(
        {"_id": "schema"}, {"$max": {"version": SCHEMA_VERSION}}, upsert=True
    )


async def ping(db: AsyncDatabase) -> bool:
    try:
        await db.command("ping")
        return True
    except Exception:  # noqa: BLE001 - readiness must never raise
        return False
