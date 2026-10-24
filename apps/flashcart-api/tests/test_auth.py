"""Authentication, session and token-handling integration tests."""

from datetime import UTC, datetime, timedelta

import jwt

from tests.conftest import PASSWORD, build_client, make_settings, signup

CSRF = {"X-Requested-With": "flashcart"}


async def test_signup_login_me(client):
    user = await signup(client, "Asha@Example.com")
    r = await client.get("/api/v1/auth/me", headers=user["headers"])
    assert r.status_code == 200
    assert r.json() == {"id": user["id"], "email": "asha@example.com", "name": "Test User", "role": "customer"}
    r = await client.post("/api/v1/auth/login", json={"email": "asha@example.com", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["access_token"]
    assert r.headers["cache-control"] == "no-store"


async def test_refresh_cookie_flags(client):
    r = await client.post("/api/v1/auth/signup", json={"email": "c@example.com", "name": "C", "password": PASSWORD})
    cookie = r.headers["set-cookie"]
    assert "fc_refresh=" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert "Path=/api/v1/auth" in cookie


async def test_duplicate_email_conflict(client):
    await signup(client, "dup@example.com")
    r = await client.post("/api/v1/auth/signup", json={"email": "DUP@example.com", "name": "x", "password": PASSWORD})
    assert r.status_code == 409


async def test_weak_password_rejected(client):
    r = await client.post("/api/v1/auth/signup", json={"email": "w@example.com", "name": "w", "password": "Qz9!x"})
    assert r.status_code == 422
    assert "Qz9!x" not in r.text  # validation errors never echo submitted values
    r = await client.post("/api/v1/auth/signup",
                          json={"email": "w@example.com", "name": "w", "password": "alllowercaseletters"})
    assert r.status_code == 422 and "alllowercaseletters" not in r.text


async def test_cannot_self_assign_admin_role(client):
    r = await client.post("/api/v1/auth/signup",
                          json={"email": "evil@example.com", "name": "e", "password": PASSWORD, "role": "admin"})
    assert r.status_code == 422


async def test_login_failure_is_generic(client):
    await signup(client, "known@example.com")
    wrong_pw = await client.post("/api/v1/auth/login", json={"email": "known@example.com", "password": "Nope12345!"})
    no_user = await client.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "Nope12345!"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()  # no user enumeration


async def test_login_rejects_operator_injection(client):
    r = await client.post("/api/v1/auth/login", json={"email": {"$ne": None}, "password": {"$ne": None}})
    assert r.status_code == 422


async def test_protected_route_requires_valid_token(client, settings):
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})).status_code == 401
    forged = jwt.encode({"sub": "64b000000000000000000000", "role": "admin", "aud": "flashcart-web",
                         "iss": "flashcart-api", "iat": datetime.now(UTC),
                         "exp": datetime.now(UTC) + timedelta(hours=1)},
                        "attacker-secret-attacker-secret-attacker", algorithm="HS256")
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})).status_code == 401
    expired = jwt.encode({"sub": "64b000000000000000000000", "aud": "flashcart-web", "iss": "flashcart-api",
                          "iat": datetime.now(UTC) - timedelta(hours=2), "exp": datetime.now(UTC) - timedelta(hours=1)},
                         settings.jwt_secret.get_secret_value(), algorithm="HS256")
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})).status_code == 401


async def test_refresh_rotates_and_detects_reuse(client, db):
    await signup(client, "rot@example.com")
    first_cookie = client.cookies.get("fc_refresh")
    r = await client.post("/api/v1/auth/refresh", headers=CSRF)
    assert r.status_code == 200
    second_cookie = client.cookies.get("fc_refresh")
    assert second_cookie and second_cookie != first_cookie

    # Simulate an attacker replaying the old token after the grace window.
    await db["refresh_tokens"].update_many({"used_at": {"$ne": None}},
                                           {"$set": {"used_at": datetime.now(UTC) - timedelta(minutes=5)}})
    client.cookies.set("fc_refresh", first_cookie, path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh", headers=CSRF)).status_code == 401
    # The whole family is now revoked: even the legitimate newest token stops working.
    client.cookies.set("fc_refresh", second_cookie, path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh", headers=CSRF)).status_code == 401
    assert await db["audit_log"].count_documents({"action": "auth.refresh_reuse_detected"}) == 1


async def test_refresh_requires_csrf_header(client):
    await signup(client)
    assert (await client.post("/api/v1/auth/refresh")).status_code == 403


async def test_logout_revokes_refresh_token(client):
    await signup(client)
    assert (await client.post("/api/v1/auth/logout", headers=CSRF)).status_code == 204
    assert (await client.post("/api/v1/auth/refresh", headers=CSRF)).status_code == 401


async def test_logout_all_invalidates_access_tokens(client):
    user = await signup(client)
    assert (await client.post("/api/v1/auth/logout-all", headers=user["headers"])).status_code == 204
    assert (await client.get("/api/v1/auth/me", headers=user["headers"])).status_code == 401


async def test_login_rate_limited(db):
    strict = make_settings(auth_rate_limit_per_minute=3)
    async with build_client(strict) as c:
        codes = [(await c.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "Wrong123!"}))
                 .status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]
