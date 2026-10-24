"""Checkout and order history. Users can only ever see their own orders (ownership check on every query)."""

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from app.deps import DbDep, UserDep, parse_object_id
from app.ratelimit import client_ip
from app.schemas import CheckoutIn, OrderItemOut, OrderOut, OrderPage
from app.services.checkout import CheckoutError, place_order

router = APIRouter(prefix="/api/v1", tags=["orders"])

IDEMPOTENCY_PATTERN = r"^[A-Za-z0-9_-]{8,100}$"


def to_order_out(doc: dict, include_email: bool = False) -> OrderOut:
    return OrderOut(
        id=str(doc["_id"]),
        order_number=doc["order_number"],
        status=doc["status"],
        items=[
            OrderItemOut(
                product_id=str(i["product_id"]),
                name=i["name"],
                unit_price_paise=i["unit_price_paise"],
                quantity=i["quantity"],
                line_total_paise=i["line_total_paise"],
            )
            for i in doc["items"]
        ],
        subtotal_paise=doc["subtotal_paise"],
        shipping_paise=doc["shipping_paise"],
        total_paise=doc["total_paise"],
        shipping_method=doc["shipping_method"],
        shipping_address=doc["shipping_address"],
        created_at=doc["created_at"],
        user_email=doc.get("user_email") if include_email else None,
    )


@router.post("/checkout", response_model=OrderOut, status_code=201)
async def checkout(
    body: CheckoutIn,
    request: Request,
    response: Response,
    user: UserDep,
    db: DbDep,
    idempotency_key: Annotated[str, Header(pattern=IDEMPOTENCY_PATTERN)],
):
    try:
        order, replayed = await place_order(
            db, user_id=user.id, user_email=user.email, body=body, idempotency_key=idempotency_key,
            ip=client_ip(request),
        )
    except CheckoutError as exc:
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail})
    if replayed:
        response.status_code = 200
        response.headers["Idempotent-Replayed"] = "true"
    return to_order_out(order)


@router.get("/orders", response_model=OrderPage)
async def my_orders(
    user: UserDep,
    db: DbDep,
    page: Annotated[int, Query(ge=1, le=100)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 10,
):
    query = {"user_id": user.id}
    total = await db["orders"].count_documents(query)
    docs = await db["orders"].find(query).sort("created_at", -1).skip((page - 1) * page_size).limit(
        page_size).to_list(page_size)
    return OrderPage(items=[to_order_out(d) for d in docs], page=page, page_size=page_size, total=total)


@router.get("/orders/{order_id}", response_model=OrderOut)
async def my_order(order_id: str, user: UserDep, db: DbDep):
    # Ownership is part of the query, so another user's order is indistinguishable from a missing one (IDOR).
    doc = await db["orders"].find_one({"_id": parse_object_id(order_id, "Order"), "user_id": user.id})
    if not doc:
        raise HTTPException(status_code=404, detail="Order not found")
    return to_order_out(doc)
