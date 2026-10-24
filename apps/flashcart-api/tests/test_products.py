"""Catalog: listing, search, filters, sorting, pagination, details."""

import pytest


async def test_listing_paginates(client):
    r = await client.get("/api/v1/products", params={"page_size": 12})
    data = r.json()
    assert r.status_code == 200 and data["total"] == 80 and len(data["items"]) == 12 and data["total_pages"] == 7
    last = (await client.get("/api/v1/products", params={"page_size": 12, "page": 7})).json()
    assert len(last["items"]) == 8
    ids = {p["id"] for page in range(1, 8)
           for p in (await client.get("/api/v1/products", params={"page_size": 12, "page": page})).json()["items"]}
    assert len(ids) == 80  # stable sort → no duplicates or gaps across pages


@pytest.mark.parametrize(("sort", "key", "reverse"), [("price_asc", "price_paise", False),
                                                      ("price_desc", "price_paise", True),
                                                      ("rating", "rating", True), ("popular", "sold_count", True)])
async def test_sorting(client, sort, key, reverse):
    items = (await client.get("/api/v1/products", params={"sort": sort, "page_size": 48})).json()["items"]
    values = [p[key] for p in items]
    assert values == sorted(values, reverse=reverse)


async def test_filters_combine(client):
    r = await client.get("/api/v1/products", params={"category": ["Electronics", "Tools"], "min_price": 100000,
                                                     "max_price": 400000, "color": "black", "page_size": 48})
    items = r.json()["items"]
    assert items
    for p in items:
        assert p["category"] in ("Electronics", "Tools") and 100000 <= p["price_paise"] <= 400000
        assert "black" in p["colors"]


async def test_rating_shipping_and_stock_filters(client):
    items = (await client.get("/api/v1/products", params={"min_rating": 4.5, "shipping": "next_day",
                                                          "in_stock": True, "page_size": 48})).json()["items"]
    assert all(p["rating"] >= 4.5 and "next_day" in p["shipping"] and p["stock"] > 0 for p in items)


async def test_text_search(client):
    items = (await client.get("/api/v1/products", params={"q": "headphones"})).json()["items"]
    assert items and all("headphone" in (p["name"] + p["description"]).lower() for p in items)
    assert (await client.get("/api/v1/products", params={"q": "zzzqqq"})).json()["total"] == 0


@pytest.mark.parametrize("params", [{"page_size": 49}, {"page": 0}, {"page": 201}, {"sort": "evil"},
                                    {"category": "Weapons"}, {"min_price": -1}, {"q": "x" * 101},
                                    {"min_price": 500, "max_price": 100}])
async def test_query_limits_enforced(client, params):
    assert (await client.get("/api/v1/products", params=params)).status_code == 422


async def test_product_detail_by_slug_and_id(client):
    first = (await client.get("/api/v1/products", params={"page_size": 1})).json()["items"][0]
    by_slug = await client.get(f"/api/v1/products/{first['slug']}")
    by_id = await client.get(f"/api/v1/products/{first['id']}")
    assert by_slug.json()["id"] == by_id.json()["id"] == first["id"]
    assert (await client.get("/api/v1/products/does-not-exist")).status_code == 404
    assert (await client.get("/api/v1/products/aaaaaaaaaaaaaaaaaaaaaaaa")).status_code == 404


async def test_inactive_products_hidden(client, db):
    p = await db["products"].find_one({})
    await db["products"].update_one({"_id": p["_id"]}, {"$set": {"active": False}})
    assert (await client.get(f"/api/v1/products/{p['_id']}")).status_code == 404
    assert (await client.get("/api/v1/products")).json()["total"] == 79


async def test_by_ids_batch(client, db):
    docs = await db["products"].find({}).limit(3).to_list(3)
    r = await client.get("/api/v1/products/by-ids", params={"ids": [str(d["_id"]) for d in docs]})
    assert {p["id"] for p in r.json()} == {str(d["_id"]) for d in docs}


async def test_facets(client):
    data = (await client.get("/api/v1/products/facets")).json()
    assert {c["value"] for c in data["categories"]} == {"Electronics", "Fashion", "Foods", "Furniture", "Tools"}
    assert sum(c["count"] for c in data["categories"]) == 80
    assert 0 < data["price_min_paise"] < data["price_max_paise"]


async def test_catalog_cache_hit(client):
    assert (await client.get("/api/v1/products?page_size=5")).headers["x-cache"] == "MISS"
    assert (await client.get("/api/v1/products?page_size=5")).headers["x-cache"] == "HIT"
