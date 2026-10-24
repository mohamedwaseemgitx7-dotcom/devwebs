"""Resets the end-to-end test database: wipes data (keeps indexes), reseeds products, creates an e2e admin.

Used by apps/flashcart-web/e2e/global-setup.ts. Refuses to run unless FLASHCART_MONGODB_DB ends with "_e2e",
so it can never wipe the development or production database.
Admin credentials come from E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD (generated per run, never stored).
"""

import asyncio
import os
import sys
from datetime import UTC, datetime

from app.config import get_settings
from app.db import close_client, ensure_schema, get_db
from app.security import hash_password
from app.seed_data import build_products


async def main() -> None:
    settings = get_settings()
    if not settings.mongodb_db.endswith("_e2e"):
        sys.exit(f"refusing to reset non-e2e database {settings.mongodb_db!r}")
    db = get_db(settings)
    await ensure_schema(db)
    for name in await db.list_collection_names():
        if name != "schema_meta":
            await db[name].delete_many({})
    await db["products"].insert_many([{k: v for k, v in p.items() if k != "kind"} for p in build_products()])
    await db["users"].insert_one({
        "email": os.environ["E2E_ADMIN_EMAIL"],
        "name": "E2E Admin",
        "password_hash": hash_password(os.environ["E2E_ADMIN_PASSWORD"]),
        "role": "admin",
        "session_version": 0,
        "created_at": datetime.now(UTC),
    })
    await close_client()
    print(f"e2e database {settings.mongodb_db} reset")


if __name__ == "__main__":
    asyncio.run(main())
