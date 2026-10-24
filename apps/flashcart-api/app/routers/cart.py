"""Server-side cart for signed-in users. Prices and stock are always re-read from the products collection."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pymongo.asynchronous.database import AsyncDatabase

from app.deps import DbDep, UserDep, parse_object_id
from app.schemas import CartItemIn, CartLine, CartOut, CartReplaceIn
from app.services.pricing import shipping_fee

router = APIRouter(prefix="/api/v1/cart", tags=["cart"])

MAX_LINES = 50
MAX_QTY = 10


async def build_cart(db: AsyncDatabase, items: list[dict], shipping_method: str = "regular") -> CartOut:
    """Prices a list of {product_id, quantity} with ONE query (no N+1, concept #5)."""
    ids = [i["product_id"] for i in items]
    products = {p["_id"]: p for p in await db["products"].find(
        {"_id": {"$in": ids}, "active": True}, {"name": 1, "price_paise": 1, "stock": 1, "images": 1}
    ).to_list(len(ids) or 1)}
    lines: list[CartLine] = []
    for item in items:
        p = products.get(item["product_id"])
        if p is None:
            continue  # product was removed or deactivated; silently drop from the priced view
        qty = item["quantity"]
        lines.append(
            CartLine(
                product_id=str(p["_id"]),
                name=p["name"],
                image=(p.get("images") or [None])[0],
                unit_price_paise=p["price_paise"],
                quantity=qty,
                line_total_paise=p["price_paise"] * qty,
                in_stock=p["stock"] >= qty,
                available=p["stock"],
            )
        )
    subtotal = sum(line.line_total_paise for line in lines)
    ship = shipping_fee(shipping_method, subtotal)
    return CartOut(
        items=lines,
        subtotal_paise=subtotal,
        shipping_paise=ship,
        total_paise=subtotal + ship,
        item_count=sum(line.quantity for line in lines),
    )


async def _load_items(db: AsyncDatabase, user_id) -> list[dict]:
    cart = await db["carts"].find_one({"user_id": user_id})
    return cart["items"] if cart else []


async def _save_items(db: AsyncDatabase, user_id, items: list[dict]) -> None:
    await db["carts"].update_one(
        {"user_id": user_id},
        {"$set": {"items": items, "updated_at": datetime.now(UTC)}},
        upsert=True,
    )


@router.get("", response_model=CartOut)
async def get_cart(user: UserDep, db: DbDep, shipping_method: str = "regular"):
    if shipping_method not in ("economic", "regular", "next_day", "instant"):
        raise HTTPException(status_code=422, detail="Unknown shipping method")
    return await build_cart(db, await _load_items(db, user.id), shipping_method)


@router.put("/items", response_model=CartOut)
async def set_item(body: CartItemIn, user: UserDep, db: DbDep):
    """Sets the quantity of one product (adds the line if missing)."""
    pid = parse_object_id(body.product_id, "Product")
    if not await db["products"].count_documents({"_id": pid, "active": True}, limit=1):
        raise HTTPException(status_code=404, detail="Product not found")
    items = [i for i in await _load_items(db, user.id) if i["product_id"] != pid]
    if len(items) >= MAX_LINES:
        raise HTTPException(status_code=422, detail=f"A cart can hold at most {MAX_LINES} different products")
    items.append({"product_id": pid, "quantity": body.quantity})
    await _save_items(db, user.id, items)
    return await build_cart(db, items)


@router.delete("/items/{product_id}", response_model=CartOut)
async def remove_item(product_id: str, user: UserDep, db: DbDep):
    pid = parse_object_id(product_id, "Product")
    items = [i for i in await _load_items(db, user.id) if i["product_id"] != pid]
    await _save_items(db, user.id, items)
    return await build_cart(db, items)


@router.post("/merge", response_model=CartOut)
async def merge_cart(body: CartReplaceIn, user: UserDep, db: DbDep):
    """Merges a guest (browser) cart into the server cart after login. Quantities add up, capped at 10."""
    merged: dict = {i["product_id"]: i["quantity"] for i in await _load_items(db, user.id)}
    for line in body.items:
        pid = parse_object_id(line.product_id, "Product")
        merged[pid] = min(MAX_QTY, merged.get(pid, 0) + line.quantity)
    valid = {p["_id"] for p in await db["products"].find(
        {"_id": {"$in": list(merged)}, "active": True}, {"_id": 1}
    ).to_list(len(merged) or 1)}
    items = [{"product_id": pid, "quantity": q} for pid, q in merged.items() if pid in valid][:MAX_LINES]
    await _save_items(db, user.id, items)
    return await build_cart(db, items)


@router.delete("", response_model=CartOut)
async def clear_cart(user: UserDep, db: DbDep):
    await _save_items(db, user.id, [])
    return await build_cart(db, [])
