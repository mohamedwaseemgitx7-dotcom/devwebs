"""Public catalog: listing, search, filters, sorting, pagination, facets, product details."""

import json
import math
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Response

from app.cache import catalog_cache
from app.deps import DbDep, parse_object_id
from app.schemas import Category, Color, Facets, ProductOut, ProductPage, Shipping, SortKey

router = APIRouter(prefix="/api/v1/products", tags=["products"])

MAX_PAGE = 200  # bounds skip() cost; deeper browsing should narrow filters instead
SORTS: dict[str, list[tuple[str, int]]] = {
    "rating": [("rating", -1), ("review_count", -1), ("_id", 1)],
    "price_asc": [("price_paise", 1), ("_id", 1)],
    "price_desc": [("price_paise", -1), ("_id", 1)],
    "popular": [("sold_count", -1), ("_id", 1)],
    "newest": [("_id", -1)],
}
# Shared CDN caching for anonymous catalog reads (edge caching #85): short TTL + stale-while-revalidate.
CATALOG_CACHE_CONTROL = "public, max-age=30, s-maxage=60, stale-while-revalidate=120"


def to_product_out(doc: dict) -> ProductOut:
    return ProductOut(
        id=str(doc["_id"]),
        sku=doc["sku"],
        slug=doc["slug"],
        name=doc["name"],
        brand=doc.get("brand", ""),
        category=doc["category"],
        description=doc.get("description", ""),
        price_paise=doc["price_paise"],
        images=doc.get("images", []),
        colors=doc.get("colors", []),
        shipping=doc.get("shipping", []),
        rating=float(doc.get("rating", 0)),
        review_count=doc.get("review_count", 0),
        sold_count=doc.get("sold_count", 0),
        stock=doc["stock"],
        location=doc.get("location", ""),
        version=doc["version"],
    )


@router.get("", response_model=ProductPage)
async def list_products(
    db: DbDep,
    response: Response,
    q: Annotated[str | None, Query(max_length=100)] = None,
    category: Annotated[list[Category] | None, Query(max_length=5)] = None,
    color: Annotated[list[Color] | None, Query(max_length=7)] = None,
    shipping: Annotated[list[Shipping] | None, Query(max_length=4)] = None,
    min_price: Annotated[int | None, Query(ge=0, le=100_000_000)] = None,
    max_price: Annotated[int | None, Query(ge=0, le=100_000_000)] = None,
    min_rating: Annotated[float | None, Query(ge=0, le=5)] = None,
    in_stock: bool = False,
    sort: SortKey = "rating",
    page: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 1,
    page_size: Annotated[int, Query(ge=1, le=48)] = 12,
):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=422, detail="min_price must not exceed max_price")

    # Every value below comes from a validated, typed parameter — user input never becomes an operator.
    match: dict = {"active": True}
    if q and q.strip():
        match["$text"] = {"$search": q.strip()}
    if category:
        match["category"] = {"$in": [c.value for c in category]}
    if color:
        match["colors"] = {"$in": [c.value for c in color]}
    if shipping:
        match["shipping"] = {"$all": [s.value for s in shipping]}
    if min_price is not None or max_price is not None:
        match["price_paise"] = {
            k: v for k, v in (("$gte", min_price), ("$lte", max_price)) if v is not None
        }
    if min_rating is not None:
        match["rating"] = {"$gte": min_rating}
    if in_stock:
        match["stock"] = {"$gt": 0}

    cache_key = "products:" + json.dumps(
        [q, category, color, shipping, min_price, max_price, min_rating, in_stock, sort, page, page_size],
        default=str,
    )
    cached = catalog_cache.get(cache_key)
    if cached is not None:
        response.headers["Cache-Control"] = CATALOG_CACHE_CONTROL
        response.headers["X-Cache"] = "HIT"
        return cached

    # One round trip for both the page and the total count ($facet) — matters on Atlas M0's 100 ops/s.
    pipeline = [
        {"$match": match},
        {
            "$facet": {
                "items": [{"$sort": dict(SORTS[sort])}, {"$skip": (page - 1) * page_size}, {"$limit": page_size}],
                "total": [{"$count": "n"}],
            }
        },
    ]
    result = await (await db["products"].aggregate(pipeline)).to_list(1)
    facet = result[0] if result else {"items": [], "total": []}
    total = facet["total"][0]["n"] if facet["total"] else 0
    page_out = ProductPage(
        items=[to_product_out(d) for d in facet["items"]],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max(1, math.ceil(total / page_size)),
    )
    catalog_cache.set(cache_key, page_out)
    response.headers["Cache-Control"] = CATALOG_CACHE_CONTROL
    response.headers["X-Cache"] = "MISS"
    return page_out


@router.get("/facets", response_model=Facets)
async def facets(db: DbDep, response: Response):
    cached = catalog_cache.get("products:facets")
    if cached is None:
        pipeline = [
            {"$match": {"active": True}},
            {
                "$facet": {
                    "categories": [{"$group": {"_id": "$category", "count": {"$sum": 1}}}, {"$sort": {"_id": 1}}],
                    "price": [{"$group": {"_id": None, "min": {"$min": "$price_paise"},
                                          "max": {"$max": "$price_paise"}}}],
                }
            },
        ]
        res = (await (await db["products"].aggregate(pipeline)).to_list(1))[0]
        price = res["price"][0] if res["price"] else {"min": 0, "max": 0}
        cached = Facets(
            categories=[{"value": c["_id"], "count": c["count"]} for c in res["categories"]],
            price_min_paise=price["min"],
            price_max_paise=price["max"],
        )
        catalog_cache.set("products:facets", cached)
    response.headers["Cache-Control"] = CATALOG_CACHE_CONTROL
    return cached


@router.get("/by-ids", response_model=list[ProductOut])
async def products_by_ids(db: DbDep, ids: Annotated[list[str], Query(max_length=50)]):
    """Batch fetch (avoids N+1 requests from the cart/favorites UI, concept #5)."""
    oids = [parse_object_id(i, "Product") for i in ids]
    docs = await db["products"].find({"_id": {"$in": oids}, "active": True}).to_list(len(oids))
    return [to_product_out(d) for d in docs]


@router.get("/{id_or_slug}", response_model=ProductOut)
async def get_product(
    id_or_slug: Annotated[str, Path(max_length=120, pattern=r"^[a-z0-9-]+$")], db: DbDep, response: Response
):
    query = {"_id": parse_object_id(id_or_slug)} if len(id_or_slug) == 24 and _is_hex(id_or_slug) \
        else {"slug": id_or_slug}
    doc = await db["products"].find_one({**query, "active": True})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    response.headers["Cache-Control"] = CATALOG_CACHE_CONTROL
    return to_product_out(doc)


def _is_hex(value: str) -> bool:
    return all(c in "0123456789abcdef" for c in value)
