"""Favorites (wishlist) — the heart icon on product cards."""

from fastapi import APIRouter, HTTPException

from app.deps import DbDep, UserDep, parse_object_id
from app.schemas import FavoritesOut

router = APIRouter(prefix="/api/v1/favorites", tags=["favorites"])

MAX_FAVORITES = 200


@router.get("", response_model=FavoritesOut)
async def list_favorites(user: UserDep, db: DbDep):
    doc = await db["favorites"].find_one({"user_id": user.id})
    return FavoritesOut(product_ids=[str(p) for p in (doc or {}).get("product_ids", [])])


@router.put("/{product_id}", response_model=FavoritesOut)
async def add_favorite(product_id: str, user: UserDep, db: DbDep):
    pid = parse_object_id(product_id, "Product")
    if not await db["products"].count_documents({"_id": pid, "active": True}, limit=1):
        raise HTTPException(status_code=404, detail="Product not found")
    # $addToSet is idempotent; the size guard keeps the document bounded.
    result = await db["favorites"].find_one_and_update(
        {"user_id": user.id, f"product_ids.{MAX_FAVORITES - 1}": {"$exists": False}},
        {"$addToSet": {"product_ids": pid}},
        upsert=False,
        return_document=True,
    )
    if result is None:
        exists = await db["favorites"].find_one({"user_id": user.id}, {"_id": 1})
        if exists:
            raise HTTPException(status_code=422, detail=f"At most {MAX_FAVORITES} favorites")
        await db["favorites"].update_one({"user_id": user.id}, {"$addToSet": {"product_ids": pid}}, upsert=True)
        result = await db["favorites"].find_one({"user_id": user.id})
    return FavoritesOut(product_ids=[str(p) for p in result["product_ids"]])


@router.delete("/{product_id}", response_model=FavoritesOut)
async def remove_favorite(product_id: str, user: UserDep, db: DbDep):
    pid = parse_object_id(product_id, "Product")
    await db["favorites"].update_one({"user_id": user.id}, {"$pull": {"product_ids": pid}})
    doc = await db["favorites"].find_one({"user_id": user.id})
    return FavoritesOut(product_ids=[str(p) for p in (doc or {}).get("product_ids", [])])
