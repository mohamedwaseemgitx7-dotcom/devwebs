"""Append-only audit log for security-relevant actions (who did what, when, from where)."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from app.logging_setup import request_id_var


async def audit(
    db: AsyncDatabase,
    action: str,
    *,
    actor_id: ObjectId | None,
    target: str | None = None,
    ip: str | None = None,
    details: dict[str, Any] | None = None,
    session=None,
) -> None:
    await db["audit_log"].insert_one(
        {
            "at": datetime.now(UTC),
            "action": action,
            "actor_id": actor_id,
            "target": target,
            "ip": ip,
            "request_id": request_id_var.get(),
            "details": details or {},
        },
        session=session,
    )
