"""Seeds the demo catalog. Safe to re-run: upserts by SKU and never touches users or orders.

Usage:
  python -m app.seed                         # upsert products into FLASHCART_MONGODB_URI / FLASHCART_MONGODB_DB
  python -m app.seed --write-svgs <dir>      # also (re)generate the SVG artwork
"""

import argparse
import asyncio
import pathlib
from datetime import UTC, datetime

from pymongo import UpdateOne

from app.config import get_settings
from app.db import close_client, ensure_schema, get_db
from app.seed_data import all_svgs, build_products


async def seed_products() -> int:
    db = get_db(get_settings())
    await ensure_schema(db)
    now = datetime.now(UTC)
    ops = []
    for p in build_products():
        p = {k: v for k, v in p.items() if k != "kind"}
        stock = p.pop("stock")
        ops.append(UpdateOne(
            {"sku": p["sku"]},
            {"$set": p | {"updated_at": now}, "$setOnInsert": {"stock": stock, "created_at": now}},
            upsert=True,
        ))
    result = await db["products"].bulk_write(ops, ordered=False)
    await close_client()
    return result.upserted_count + result.modified_count


def write_svgs(target: pathlib.Path) -> int:
    target.mkdir(parents=True, exist_ok=True)
    svgs = all_svgs()
    for name, content in svgs.items():
        (target / name).write_text(content, encoding="utf-8")
    return len(svgs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-svgs", type=pathlib.Path)
    parser.add_argument("--skip-db", action="store_true")
    args = parser.parse_args()
    if args.write_svgs:
        print(f"wrote {write_svgs(args.write_svgs)} SVG files to {args.write_svgs}")
    if not args.skip_db:
        print(f"products upserted/updated: {asyncio.run(seed_products())}")


if __name__ == "__main__":
    main()
