"""Payment-provider webhook receiver (simulated provider). Webhooks #17, signature verification, replay
protection with a timestamp tolerance (clock skew #94) and event-ID de-duplication (idempotency #1).

Signature header:  X-FlashCart-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret, f"{t}.{raw_body}")>
"""

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from pymongo.errors import DuplicateKeyError

from app.deps import DbDep, SettingsDep
from app.services.audit import audit

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

TOLERANCE_SECONDS = 300


def sign(secret: str, timestamp: int, body: bytes) -> str:
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={mac}"


def verify(secret: str, header: str, body: bytes, now: float | None = None) -> None:
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        timestamp = int(parts["t"])
        supplied = parts["v1"]
    except (ValueError, KeyError):
        raise HTTPException(status_code=400, detail="Malformed signature header") from None
    if abs((now or time.time()) - timestamp) > TOLERANCE_SECONDS:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")
    expected = sign(secret, timestamp, body).split("v1=", 1)[1]
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=400, detail="Invalid signature")


@router.post("/payments", status_code=200)
async def payment_webhook(
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    x_flashcart_signature: Annotated[str, Header(max_length=300)],
):
    raw = await request.body()
    verify(settings.webhook_secret.get_secret_value(), x_flashcart_signature, raw)  # verify BEFORE parsing
    try:
        event = json.loads(raw)
        event_id = str(event["id"])[:100]
        event_type = str(event["type"])
        order_number = str(event["data"]["order_number"])[:40]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=400, detail="Malformed event") from None

    try:
        await db["webhook_events"].insert_one(
            {"event_id": event_id, "type": event_type, "received_at": datetime.now(UTC)}
        )
    except DuplicateKeyError:
        return {"status": "duplicate_ignored"}

    if event_type == "payment.succeeded":
        now = datetime.now(UTC)
        result = await db["orders"].update_one(
            {"order_number": order_number, "status": "confirmed"},
            {"$set": {"status": "paid", "payment.status": "captured", "updated_at": now},
             "$push": {"status_history": {"status": "paid", "at": now, "by": "webhook"}}},
        )
        await audit(db, "webhook.payment_succeeded", actor_id=None, target=order_number,
                    details={"event_id": event_id, "applied": result.modified_count == 1})
        return {"status": "processed", "applied": result.modified_count == 1}
    return {"status": "ignored", "type": event_type}
