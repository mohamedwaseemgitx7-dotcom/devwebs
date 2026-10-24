"""Admin workflows, webhooks, health, metrics and HTTP-level security controls."""

import json
import time

from app.routers.webhooks import sign
from tests.conftest import ADDRESS, build_client, idem, make_admin, make_settings, product_with_stock, signup

NEW_PRODUCT = {"sku": "FC-TST-9001", "name": "Test Lamp", "brand": "Lumen", "category": "Furniture",
               "price_paise": 199900, "stock": 7, "colors": ["white"], "shipping": ["regular"],
               "images": ["/products/lamp-white.svg"]}


async def test_admin_product_lifecycle_with_optimistic_locking(client, db):
    admin = await make_admin(client, db)
    h = admin["headers"]
    created = await client.post("/api/v1/admin/products", json=NEW_PRODUCT, headers=h)
    assert created.status_code == 201, created.text
    pid, version = created.json()["id"], created.json()["version"]
    assert (await client.post("/api/v1/admin/products", json=NEW_PRODUCT, headers=h)).status_code == 409

    ok = await client.patch(f"/api/v1/admin/products/{pid}", json={"version": version, "price_paise": 249900},
                            headers=h)
    assert ok.status_code == 200 and ok.json()["version"] == version + 1
    stale = await client.patch(f"/api/v1/admin/products/{pid}", json={"version": version, "name": "Stale"},
                               headers=h)
    assert stale.status_code == 409  # someone else saved in between

    assert (await client.post(f"/api/v1/admin/products/{pid}/stock", json={"delta": -100, "reason": "audit"},
                              headers=h)).status_code == 409
    adj = await client.post(f"/api/v1/admin/products/{pid}/stock", json={"delta": 3, "reason": "restock"}, headers=h)
    assert adj.json()["stock"] == 10

    assert (await client.delete(f"/api/v1/admin/products/{pid}", headers=h)).status_code == 204
    assert (await client.get(f"/api/v1/products/{pid}")).status_code == 404
    actions = {d["action"] for d in await db["audit_log"].find({}).to_list(100)}
    assert {"product.create", "product.update", "product.stock_adjust", "product.deactivate"} <= actions


async def test_admin_rejects_unsafe_product_fields(client, db):
    admin = await make_admin(client, db)
    bad_image = NEW_PRODUCT | {"images": ["https://evil.example/x.svg"]}
    assert (await client.post("/api/v1/admin/products", json=bad_image, headers=admin["headers"])).status_code == 422
    xss = NEW_PRODUCT | {"sku": "<script>"}
    assert (await client.post("/api/v1/admin/products", json=xss, headers=admin["headers"])).status_code == 422


async def test_order_state_machine_and_cancel_restores_stock(client, db):
    admin = await make_admin(client, db)
    user = await signup(client)
    p = await product_with_stock(db, 2)
    await client.put("/api/v1/cart/items", json={"product_id": str(p["_id"]), "quantity": 2}, headers=user["headers"])
    order = (await client.post("/api/v1/checkout", json={"shipping_address": ADDRESS},
                               headers=user["headers"] | idem())).json()
    url = f"/api/v1/admin/orders/{order['id']}"
    assert (await client.patch(url, json={"status": "delivered"}, headers=admin["headers"])).status_code == 409
    assert (await client.patch(url, json={"status": "cancelled"}, headers=admin["headers"])).status_code == 200
    assert (await db["products"].find_one({"_id": p["_id"]}))["stock"] == p["stock"]
    assert (await client.patch(url, json={"status": "shipped"}, headers=admin["headers"])).status_code == 409
    listing = (await client.get("/api/v1/admin/orders?status=cancelled", headers=admin["headers"])).json()
    assert listing["total"] == 1 and listing["items"][0]["user_email"] == user["email"]


async def test_payment_webhook(client, db, settings):
    user = await signup(client)
    p = await product_with_stock(db)
    await client.put("/api/v1/cart/items", json={"product_id": str(p["_id"]), "quantity": 1}, headers=user["headers"])
    order = (await client.post("/api/v1/checkout", json={"shipping_address": ADDRESS},
                               headers=user["headers"] | idem())).json()
    body = json.dumps({"id": "evt_123", "type": "payment.succeeded",
                       "data": {"order_number": order["order_number"]}}).encode()
    secret = settings.webhook_secret.get_secret_value()
    good = {"X-FlashCart-Signature": sign(secret, int(time.time()), body), "Content-Type": "application/json"}

    forged = {"X-FlashCart-Signature": sign("x" * 40, int(time.time()), body), "Content-Type": "application/json"}
    assert (await client.post("/api/v1/webhooks/payments", content=body, headers=forged)).status_code == 400
    stale = {"X-FlashCart-Signature": sign(secret, int(time.time()) - 3600, body)}
    assert (await client.post("/api/v1/webhooks/payments", content=body, headers=stale)).status_code == 400

    r = await client.post("/api/v1/webhooks/payments", content=body, headers=good)
    assert r.json() == {"status": "processed", "applied": True}
    replay = await client.post("/api/v1/webhooks/payments", content=body, headers=good)
    assert replay.json()["status"] == "duplicate_ignored"
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=user["headers"])).json()["status"] == "paid"


async def test_health_endpoints(client):
    assert (await client.get("/healthz")).json() == {"status": "ok"}
    assert (await client.get("/readyz")).json()["status"] == "ready"
    h = (await client.get("/api/v1/health")).json()
    assert h["status"] == "ok" and h["dependencies"]["mongodb"]["status"] == "up"
    assert "mongodb://" not in json.dumps(h)


async def test_readiness_reports_db_outage(db):
    broken = make_settings(mongodb_uri="mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=300", mongodb_timeout_ms=300)
    from app import db as db_module
    saved = db_module._client
    db_module._client = None  # force a client pointed at the dead port
    try:
        async with build_client(broken) as c:
            assert (await c.get("/healthz")).status_code == 200  # liveness unaffected
            r = await c.get("/readyz")
            assert r.status_code == 503 and r.json()["dependencies"]["mongodb"] == "down"
    finally:
        await db_module.close_client()
        db_module._client = saved


async def test_metrics_requires_token(client):
    assert (await client.get("/metrics")).status_code == 401
    r = await client.get("/metrics", headers={"Authorization": "Bearer metrics-token-for-tests"})
    assert r.status_code == 200 and "flashcart_http_requests_total" in r.text


async def test_security_headers_and_request_id(client):
    r = await client.get("/api/v1/products?page_size=1", headers={"X-Request-ID": "trace-abc-12345"})
    assert r.headers["x-request-id"] == "trace-abc-12345"
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    bogus = await client.get("/healthz", headers={"X-Request-ID": "bad id\nwith newline"})
    assert bogus.headers["x-request-id"] != "bad id\nwith newline"


async def test_body_size_limit(client):
    r = await client.post("/api/v1/auth/login", content=b"x" * 70_000, headers={"Content-Type": "application/json"})
    assert r.status_code == 413


async def test_cors_only_allows_configured_origin(client):
    allowed = await client.options("/api/v1/products", headers={"Origin": "http://localhost:5173",
                                                                 "Access-Control-Request-Method": "GET"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    denied = await client.options("/api/v1/products", headers={"Origin": "https://evil.example",
                                                                "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in denied.headers


async def test_general_rate_limit(db):
    async with build_client(make_settings(rate_limit_per_minute=5)) as c:
        codes = [(await c.get("/api/v1/products/facets")).status_code for _ in range(7)]
        assert codes[:5] == [200] * 5 and codes[5:] == [429, 429]
        assert (await c.get("/healthz")).status_code == 200  # probes exempt


async def test_origin_verify_in_production_mode(db):
    prod = make_settings(env="production", cookie_secure=True, origin_verify_secret="o" * 40, cors_origins=[])
    async with build_client(prod) as c:
        assert (await c.get("/api/v1/products")).status_code == 403
        assert (await c.get("/api/v1/products", headers={"X-Origin-Verify": "o" * 40})).status_code == 200
        assert (await c.get("/healthz")).status_code == 200
        assert (await c.get("/api/docs", headers={"X-Origin-Verify": "o" * 40})).status_code == 404  # no docs UI
        r = await c.get("/api/v1/health", headers={"X-Origin-Verify": "o" * 40})
        assert "strict-transport-security" in r.headers


async def test_unhandled_errors_do_not_leak_details(db, monkeypatch):
    from app.routers import products

    def boom(_):
        raise RuntimeError("secret internal detail mongodb://user:pw@host")

    monkeypatch.setattr(products, "to_product_out", boom)
    import httpx

    from app.deps import settings_dep
    from app.main import create_app
    settings = make_settings()
    app = create_app(settings, run_migrations=False)
    app.dependency_overrides[settings_dep] = lambda: settings
    # Starlette re-raises after sending the 500; raise_app_exceptions=False shows what a real client receives.
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.get("/api/v1/products?page_size=2&sort=newest")
    assert r.status_code == 500
    assert "secret" not in r.text and "mongodb" not in r.text and "Traceback" not in r.text
    assert r.json()["detail"] == "Internal server error" and r.json()["request_id"]
