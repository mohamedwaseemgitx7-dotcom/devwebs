"""Admin endpoints. Every route depends on require_admin (role re-read from the DB on each request) and every
mutation is written to the audit log."""

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.cache import catalog_cache
from app.deps import AdminDep, DbDep, parse_object_id
from app.ratelimit import client_ip
from app.routers.orders import to_order_out
from app.routers.products import to_product_out
from app.schemas import OrderOut, OrderPage, OrderStatusUpdate, ProductCreate, ProductOut, ProductUpdate, StockAdjust
from app.services.audit import audit

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# Order state machine: anything not listed is rejected.
TRANSITIONS = {
    "confirmed": {"paid", "shipped", "cancelled"},
    "paid": {"shipped", "cancelled"},
    "shipped": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}


def slugify(name: str, sku: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80]
    return f"{base}-{sku.lower()}"


@router.get("/products", response_model=list[ProductOut])
async def admin_products(
    admin: AdminDep,
    db: DbDep,
    low_stock_below: Annotated[int | None, Query(ge=0, le=100000)] = None,
    include_inactive: bool = True,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
):
    query: dict = {} if include_inactive else {"active": True}
    if low_stock_below is not None:
        query["stock"] = {"$lt": low_stock_below}
    docs = await db["products"].find(query).sort("name", 1).limit(limit).to_list(limit)
    return [to_product_out(d) for d in docs]


@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(body: ProductCreate, request: Request, admin: AdminDep, db: DbDep):
    now = datetime.now(UTC)
    doc = body.model_dump(mode="json") | {
        "slug": slugify(body.name, body.sku),
        "rating": 0.0,
        "review_count": 0,
        "sold_count": 0,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = await db["products"].insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="A product with this SKU already exists") from None
    doc["_id"] = result.inserted_id
    catalog_cache.invalidate_prefix("products:")
    await audit(db, "product.create", actor_id=admin.id, target=str(result.inserted_id), ip=client_ip(request))
    return to_product_out(doc)


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(product_id: str, body: ProductUpdate, request: Request, admin: AdminDep, db: DbDep):
    pid = parse_object_id(product_id, "Product")
    changes = body.model_dump(mode="json", exclude_unset=True, exclude={"version"})
    if not changes:
        raise HTTPException(status_code=422, detail="No changes supplied")
    if "name" in changes:
        sku = (await db["products"].find_one({"_id": pid}, {"sku": 1}) or {}).get("sku", "")
        changes["slug"] = slugify(changes["name"], sku)
    changes["updated_at"] = datetime.now(UTC)
    # Optimistic locking (#25): the update only applies if nobody changed the product since the admin loaded it.
    doc = await db["products"].find_one_and_update(
        {"_id": pid, "version": body.version},
        {"$set": changes, "$inc": {"version": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        if await db["products"].count_documents({"_id": pid}, limit=1):
            raise HTTPException(status_code=409, detail="Product was modified by someone else. Reload and retry.")
        raise HTTPException(status_code=404, detail="Product not found")
    catalog_cache.invalidate_prefix("products:")
    await audit(db, "product.update", actor_id=admin.id, target=product_id, ip=client_ip(request),
                details={"fields": sorted(k for k in changes if k != "updated_at")})
    return to_product_out(doc)


@router.post("/products/{product_id}/stock", response_model=ProductOut)
async def adjust_stock(product_id: str, body: StockAdjust, request: Request, admin: AdminDep, db: DbDep):
    """Relative stock change; atomic $inc that can never take stock below zero."""
    pid = parse_object_id(product_id, "Product")
    condition = {"_id": pid} if body.delta >= 0 else {"_id": pid, "stock": {"$gte": -body.delta}}
    doc = await db["products"].find_one_and_update(
        condition, {"$inc": {"stock": body.delta, "version": 1}, "$set": {"updated_at": datetime.now(UTC)}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        if await db["products"].count_documents({"_id": pid}, limit=1):
            raise HTTPException(status_code=409, detail="Stock cannot go below zero")
        raise HTTPException(status_code=404, detail="Product not found")
    catalog_cache.invalidate_prefix("products:")
    await audit(db, "product.stock_adjust", actor_id=admin.id, target=product_id, ip=client_ip(request),
                details={"delta": body.delta, "reason": body.reason, "new_stock": doc["stock"]})
    return to_product_out(doc)


@router.delete("/products/{product_id}", status_code=204)
async def deactivate_product(product_id: str, request: Request, admin: AdminDep, db: DbDep):
    """Soft delete: keeps order history and references intact."""
    pid = parse_object_id(product_id, "Product")
    result = await db["products"].update_one({"_id": pid}, {"$set": {"active": False}, "$inc": {"version": 1}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    catalog_cache.invalidate_prefix("products:")
    await audit(db, "product.deactivate", actor_id=admin.id, target=product_id, ip=client_ip(request))


@router.get("/orders", response_model=OrderPage)
async def all_orders(
    admin: AdminDep,
    db: DbDep,
    status: Annotated[str | None, Query(pattern=r"^(confirmed|paid|shipped|delivered|cancelled)$")] = None,
    page: Annotated[int, Query(ge=1, le=500)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    query = {"status": status} if status else {}
    total = await db["orders"].count_documents(query)
    docs = await db["orders"].find(query).sort("created_at", -1).skip((page - 1) * page_size).limit(
        page_size).to_list(page_size)
    return OrderPage(items=[to_order_out(d, include_email=True) for d in docs], page=page, page_size=page_size,
                     total=total)


@router.patch("/orders/{order_id}", response_model=OrderOut)
async def update_order_status(order_id: str, body: OrderStatusUpdate, request: Request, admin: AdminDep,
                              db: DbDep):
    oid = parse_object_id(order_id, "Order")
    now = datetime.now(UTC)

    async def txn(session):
        order = await db["orders"].find_one({"_id": oid}, session=session)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        if body.status not in TRANSITIONS[order["status"]]:
            raise HTTPException(status_code=409,
                                detail=f"Cannot change order from {order['status']} to {body.status}")
        # Compare-and-set on the current status so two admins cannot apply conflicting transitions.
        updated = await db["orders"].find_one_and_update(
            {"_id": oid, "status": order["status"]},
            {"$set": {"status": body.status, "updated_at": now},
             "$push": {"status_history": {"status": body.status, "at": now, "by": admin.id}}},
            return_document=ReturnDocument.AFTER,
            session=session,
        )
        if updated is None:
            raise HTTPException(status_code=409, detail="Order was modified concurrently. Reload and retry.")
        if body.status == "cancelled":  # compensating action: return reserved stock
            for item in order["items"]:
                await db["products"].update_one(
                    {"_id": item["product_id"]},
                    {"$inc": {"stock": item["quantity"], "sold_count": -item["quantity"]}},
                    session=session,
                )
        await audit(db, "order.status", actor_id=admin.id, target=order_id, ip=client_ip(request),
                    details={"from": order["status"], "to": body.status}, session=session)
        return updated

    async with db.client.start_session() as session:
        doc = await session.with_transaction(txn)
    catalog_cache.invalidate_prefix("products:")
    return to_order_out(doc, include_email=True)


@router.get("/stats")
async def stats(admin: AdminDep, db: DbDep):
    since = datetime.now(UTC) - timedelta(days=30)
    pipeline = [
        {"$match": {"created_at": {"$gte": since}, "status": {"$ne": "cancelled"}}},
        {"$group": {"_id": None, "orders": {"$sum": 1}, "revenue_paise": {"$sum": "$total_paise"}}},
    ]
    agg = await (await db["orders"].aggregate(pipeline)).to_list(1)
    by_status = await (await db["orders"].aggregate(
        [{"$group": {"_id": "$status", "count": {"$sum": 1}}}])).to_list(10)
    return {
        "last_30_days": {
            "orders": agg[0]["orders"] if agg else 0,
            "revenue_paise": agg[0]["revenue_paise"] if agg else 0,
        },
        "orders_by_status": {s["_id"]: s["count"] for s in by_status},
        "products_active": await db["products"].count_documents({"active": True}),
        "low_stock": await db["products"].count_documents({"active": True, "stock": {"$lt": 5}}),
        "customers": await db["users"].count_documents({"role": "customer"}),
    }


@router.get("/audit")
async def audit_log(admin: AdminDep, db: DbDep, limit: Annotated[int, Query(ge=1, le=200)] = 50):
    docs = await db["audit_log"].find({}, {"_id": 0}).sort("at", -1).limit(limit).to_list(limit)
    for d in docs:
        d["actor_id"] = str(d["actor_id"]) if d.get("actor_id") else None
    return docs
