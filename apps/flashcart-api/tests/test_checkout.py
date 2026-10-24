"""Cart, checkout, inventory consistency, idempotency, concurrency and authorization."""

import asyncio
import uuid

from tests.conftest import ADDRESS, idem, make_admin, product_with_stock, signup


async def add(client, user, product_id, qty=1):
    return await client.put("/api/v1/cart/items", json={"product_id": str(product_id), "quantity": qty},
                            headers=user["headers"])


async def test_cart_prices_come_from_server(client, db):
    user = await signup(client)
    p = await product_with_stock(db, 2)
    r = await add(client, user, p["_id"], 2)
    line = r.json()["items"][0]
    assert line["unit_price_paise"] == p["price_paise"] and line["line_total_paise"] == 2 * p["price_paise"]
    # A client-supplied price field is rejected outright.
    bad = await client.put("/api/v1/cart/items", json={"product_id": str(p["_id"]), "quantity": 1, "price_paise": 1},
                           headers=user["headers"])
    assert bad.status_code == 422


async def test_cart_validation(client, db):
    user = await signup(client)
    p = await product_with_stock(db)
    assert (await add(client, user, p["_id"], 11)).status_code == 422
    assert (await add(client, user, p["_id"], 0)).status_code == 422
    assert (await add(client, user, "aaaaaaaaaaaaaaaaaaaaaaaa")).status_code == 404
    assert (await client.put("/api/v1/cart/items", json={"product_id": "x", "quantity": 1},
                             headers=user["headers"])).status_code == 422
    assert (await client.get("/api/v1/cart")).status_code == 401


async def test_cart_update_remove_merge(client, db):
    user = await signup(client)
    a, b = await db["products"].find({"stock": {"$gt": 5}}).limit(2).to_list(2)
    await add(client, user, a["_id"], 1)
    await add(client, user, a["_id"], 3)  # set, not add
    cart = (await client.get("/api/v1/cart", headers=user["headers"])).json()
    assert cart["item_count"] == 3
    merged = await client.post("/api/v1/cart/merge", headers=user["headers"], json={"items": [
        {"product_id": str(a["_id"]), "quantity": 9}, {"product_id": str(b["_id"]), "quantity": 2}]})
    qty = {i["product_id"]: i["quantity"] for i in merged.json()["items"]}
    assert qty == {str(a["_id"]): 10, str(b["_id"]): 2}  # capped at 10
    after = await client.delete(f"/api/v1/cart/items/{a['_id']}", headers=user["headers"])
    assert [i["product_id"] for i in after.json()["items"]] == [str(b["_id"])]


async def test_checkout_happy_path(client, db):
    user = await signup(client)
    p = await product_with_stock(db, 2)
    await add(client, user, p["_id"], 2)
    r = await client.post("/api/v1/checkout", json={"shipping_address": ADDRESS, "shipping_method": "next_day"},
                          headers=user["headers"] | idem())
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["status"] == "confirmed" and order["subtotal_paise"] == 2 * p["price_paise"]
    assert order["shipping_paise"] == 14_900 and order["total_paise"] == order["subtotal_paise"] + 14_900
    after = await db["products"].find_one({"_id": p["_id"]})
    assert after["stock"] == p["stock"] - 2 and after["sold_count"] == p["sold_count"] + 2
    assert (await client.get("/api/v1/cart", headers=user["headers"])).json()["items"] == []
    history = (await client.get("/api/v1/orders", headers=user["headers"])).json()
    assert history["total"] == 1 and history["items"][0]["id"] == order["id"]


async def test_checkout_idempotent_replay(client, db):
    user = await signup(client)
    p = await product_with_stock(db, 3)
    await add(client, user, p["_id"], 1)
    key = {"Idempotency-Key": uuid.uuid4().hex}
    body = {"shipping_address": ADDRESS}
    first = await client.post("/api/v1/checkout", json=body, headers=user["headers"] | key)
    second = await client.post("/api/v1/checkout", json=body, headers=user["headers"] | key)
    assert first.status_code == 201 and second.status_code == 200
    assert second.headers["idempotent-replayed"] == "true" and first.json()["id"] == second.json()["id"]
    assert (await db["products"].find_one({"_id": p["_id"]}))["stock"] == p["stock"] - 1  # charged once
    assert await db["orders"].count_documents({}) == 1
    reused = await client.post("/api/v1/checkout", json={"shipping_address": ADDRESS, "shipping_method": "instant"},
                               headers=user["headers"] | key)
    assert reused.status_code == 422


async def test_checkout_requires_idempotency_key_and_cart(client):
    user = await signup(client)
    assert (await client.post("/api/v1/checkout", json={"shipping_address": ADDRESS},
                              headers=user["headers"])).status_code == 422
    empty = await client.post("/api/v1/checkout", json={"shipping_address": ADDRESS}, headers=user["headers"] | idem())
    assert empty.status_code == 400


async def test_checkout_insufficient_stock_rolls_back_everything(client, db):
    user = await signup(client)
    plenty = await product_with_stock(db, 10)
    scarce = await db["products"].find_one({"_id": {"$ne": plenty["_id"]}, "stock": {"$gt": 0}})
    await add(client, user, plenty["_id"], 2)
    await db["products"].update_one({"_id": scarce["_id"]}, {"$set": {"stock": 1}})
    await add(client, user, scarce["_id"], 3)
    r = await client.post("/api/v1/checkout", json={"shipping_address": ADDRESS}, headers=user["headers"] | idem())
    assert r.status_code == 409
    assert r.json()["detail"]["items"][0]["available"] == 1
    # Atomicity: the item that WAS available was not decremented either.
    assert (await db["products"].find_one({"_id": plenty["_id"]}))["stock"] == plenty["stock"]
    assert await db["orders"].count_documents({}) == 0


async def test_checkout_detects_price_change(client, db):
    user = await signup(client)
    p = await product_with_stock(db, 1)
    await add(client, user, p["_id"], 1)
    r = await client.post("/api/v1/checkout", json={"shipping_address": ADDRESS, "expected_total_paise": 1},
                          headers=user["headers"] | idem())
    assert r.status_code == 409 and "Prices changed" in r.text


async def test_checkout_rejects_client_supplied_totals(client, db):
    user = await signup(client)
    p = await product_with_stock(db)
    await add(client, user, p["_id"])
    r = await client.post("/api/v1/checkout", json={"shipping_address": ADDRESS, "total_paise": 1},
                          headers=user["headers"] | idem())
    assert r.status_code == 422


async def test_checkout_validates_address(client, db):
    user = await signup(client)
    p = await product_with_stock(db)
    await add(client, user, p["_id"])
    bad = ADDRESS | {"postal_code": "12AB", "phone": "123"}
    r = await client.post("/api/v1/checkout", json={"shipping_address": bad}, headers=user["headers"] | idem())
    assert r.status_code == 422


async def test_concurrent_buyers_never_oversell(client, db):
    """20 customers race for the last 5 units. Exactly 5 orders succeed and stock ends at 0, never negative."""
    p = await product_with_stock(db)
    await db["products"].update_one({"_id": p["_id"]}, {"$set": {"stock": 5}})
    users = [await signup(client) for _ in range(20)]
    for u in users:
        await add(client, u, p["_id"], 1)

    async def buy(u):
        return (await client.post("/api/v1/checkout", json={"shipping_address": ADDRESS},
                                  headers=u["headers"] | idem())).status_code

    codes = await asyncio.gather(*(buy(u) for u in users))
    assert codes.count(201) == 5 and codes.count(409) == 15, codes
    assert (await db["products"].find_one({"_id": p["_id"]}))["stock"] == 0
    assert await db["orders"].count_documents({}) == 5


async def test_concurrent_duplicate_submissions_create_one_order(client, db):
    """A user double-clicks / retries 10 times in parallel with the same key → one order, one stock decrement."""
    user = await signup(client)
    p = await product_with_stock(db, 5)
    await add(client, user, p["_id"], 1)
    key = {"Idempotency-Key": uuid.uuid4().hex}
    responses = await asyncio.gather(*(
        client.post("/api/v1/checkout", json={"shipping_address": ADDRESS}, headers=user["headers"] | key)
        for _ in range(10)))
    ok = [r for r in responses if r.status_code in (200, 201)]
    assert len(ok) == 10 and len({r.json()["id"] for r in ok}) == 1
    assert [r.status_code for r in responses].count(201) == 1
    assert await db["orders"].count_documents({}) == 1
    assert (await db["products"].find_one({"_id": p["_id"]}))["stock"] == p["stock"] - 1


async def test_users_cannot_read_each_others_orders(client, db):
    alice, bob = await signup(client), await signup(client)
    p = await product_with_stock(db)
    await add(client, alice, p["_id"])
    order = (await client.post("/api/v1/checkout", json={"shipping_address": ADDRESS},
                               headers=alice["headers"] | idem())).json()
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=alice["headers"])).status_code == 200
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=bob["headers"])).status_code == 404
    assert (await client.get("/api/v1/orders", headers=bob["headers"])).json()["total"] == 0


async def test_admin_routes_are_locked_down(client, db):
    customer = await signup(client)
    for method, path in [("GET", "/api/v1/admin/orders"), ("GET", "/api/v1/admin/stats"),
                         ("GET", "/api/v1/admin/products"), ("POST", "/api/v1/admin/products"),
                         ("GET", "/api/v1/admin/audit")]:
        assert (await client.request(method, path)).status_code == 401
        assert (await client.request(method, path, headers=customer["headers"], json={})).status_code == 403
    admin = await make_admin(client, db)
    assert (await client.get("/api/v1/admin/stats", headers=admin["headers"])).status_code == 200


async def test_role_downgrade_takes_effect_immediately(client, db):
    admin = await make_admin(client, db)
    await db["users"].update_one({"email": admin["email"]}, {"$set": {"role": "customer"}})
    assert (await client.get("/api/v1/admin/stats", headers=admin["headers"])).status_code == 403


async def test_favorites(client, db):
    user = await signup(client)
    p = await product_with_stock(db)
    r = await client.put(f"/api/v1/favorites/{p['_id']}", headers=user["headers"])
    assert r.json()["product_ids"] == [str(p["_id"])]
    await client.put(f"/api/v1/favorites/{p['_id']}", headers=user["headers"])  # idempotent
    assert (await client.get("/api/v1/favorites", headers=user["headers"])).json()["product_ids"] == [str(p["_id"])]
    r = await client.delete(f"/api/v1/favorites/{p['_id']}", headers=user["headers"])
    assert r.json()["product_ids"] == []
