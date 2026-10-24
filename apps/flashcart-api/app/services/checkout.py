"""Checkout: turns the server-side cart into an order atomically.

Guarantees (see docs/ARCHITECTURE.md §Checkout):
- No overselling: each stock decrement is conditional on `stock >= qty`, inside one multi-document ACID
  transaction. Two buyers racing for the last unit cannot both succeed (race conditions #14).
- All-or-nothing: if any line is short, every decrement in the transaction is rolled back.
- Exactly-once orders: the client sends an Idempotency-Key; a unique index on (user_id, idempotency_key)
  makes retries and double-clicks return the original order instead of charging twice (#1).
- Transient failures (write conflicts, primary step-downs) are retried by with_transaction with backoff (#11, #12).
- Prices come from the database at commit time — never from the client.
"""

import hashlib
import json
import secrets
from datetime import UTC, datetime

from bson import ObjectId
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from app.schemas import CheckoutIn
from app.services.audit import audit
from app.services.pricing import shipping_fee


class CheckoutError(Exception):
    def __init__(self, status: int, detail: str | dict) -> None:
        self.status = status
        self.detail = detail


def request_fingerprint(body: CheckoutIn) -> str:
    return hashlib.sha256(json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()


def new_order_number() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity
    return f"FC-{datetime.now(UTC):%Y%m%d}-" + "".join(secrets.choice(alphabet) for _ in range(6))


async def place_order(
    db: AsyncDatabase, *, user_id: ObjectId, user_email: str, body: CheckoutIn, idempotency_key: str,
    ip: str | None,
) -> tuple[dict, bool]:
    """Returns (order_document, replayed). Raises CheckoutError for client-visible failures."""
    fingerprint = request_fingerprint(body)

    existing = await db["orders"].find_one({"user_id": user_id, "idempotency_key": idempotency_key})
    if existing:
        return _check_replay(existing, fingerprint), True

    cart = await db["carts"].find_one({"user_id": user_id})
    cart_items = (cart or {}).get("items", [])
    if not cart_items:
        raise CheckoutError(400, "Your cart is empty")

    client = db.client

    async def txn(session: AsyncClientSession) -> dict:
        lines = []
        shortages = []
        for item in cart_items:
            product = await db["products"].find_one_and_update(
                {"_id": item["product_id"], "active": True, "stock": {"$gte": item["quantity"]}},
                {"$inc": {"stock": -item["quantity"], "sold_count": item["quantity"]}},
                projection={"name": 1, "price_paise": 1, "sku": 1},
                session=session,
            )
            if product is None:
                current = await db["products"].find_one({"_id": item["product_id"]}, {"name": 1, "stock": 1},
                                                        session=session)
                shortages.append({
                    "product_id": str(item["product_id"]),
                    "name": current["name"] if current else "Unavailable product",
                    "requested": item["quantity"],
                    "available": current["stock"] if current else 0,
                })
                continue
            lines.append({
                "product_id": product["_id"],
                "sku": product["sku"],
                "name": product["name"],
                "unit_price_paise": product["price_paise"],
                "quantity": item["quantity"],
                "line_total_paise": product["price_paise"] * item["quantity"],
            })
        if shortages:
            # Raising aborts the transaction: every decrement above is rolled back.
            raise CheckoutError(409, {"message": "Some items are no longer available", "items": shortages})

        subtotal = sum(line["line_total_paise"] for line in lines)
        ship = shipping_fee(body.shipping_method.value, subtotal)
        total = subtotal + ship
        if body.expected_total_paise is not None and body.expected_total_paise != total:
            raise CheckoutError(409, {"message": "Prices changed since you loaded the cart",
                                      "total_paise": total})

        now = datetime.now(UTC)
        order = {
            "order_number": new_order_number(),
            "user_id": user_id,
            "user_email": user_email,
            "items": lines,
            "subtotal_paise": subtotal,
            "shipping_paise": ship,
            "total_paise": total,
            "shipping_method": body.shipping_method.value,
            "shipping_address": body.shipping_address.model_dump(),
            "status": "confirmed",
            "payment": {"provider": "simulated", "status": "authorized"},
            "idempotency_key": idempotency_key,
            "request_fingerprint": fingerprint,
            "created_at": now,
            "status_history": [{"status": "confirmed", "at": now}],
        }
        result = await db["orders"].insert_one(order, session=session)
        order["_id"] = result.inserted_id
        await db["carts"].update_one({"user_id": user_id}, {"$set": {"items": [], "updated_at": now}},
                                     session=session)
        await audit(db, "order.placed", actor_id=user_id, target=str(result.inserted_id), ip=ip,
                    details={"total_paise": total, "lines": len(lines)}, session=session)
        return order

    try:
        async with client.start_session() as session:
            order = await session.with_transaction(
                txn,
                read_concern=ReadConcern("snapshot"),
                write_concern=WriteConcern("majority"),
            )
        return order, False
    except DuplicateKeyError:
        # A concurrent request with the same Idempotency-Key committed first — return that order.
        existing = await db["orders"].find_one({"user_id": user_id, "idempotency_key": idempotency_key})
        if existing is None:
            raise
        return _check_replay(existing, fingerprint), True


def _check_replay(existing: dict, fingerprint: str) -> dict:
    if existing.get("request_fingerprint") != fingerprint:
        raise CheckoutError(422, "Idempotency-Key was already used with a different request")
    return existing
