"""Authentication: signup, login, refresh-token rotation, logout.

CSRF (#44): the refresh cookie is HttpOnly + SameSite=Strict + scoped to /api/v1/auth, and every
cookie-authenticated endpoint also requires the custom header `X-Requested-With: flashcart`. Browsers cannot
add custom headers to cross-site requests without a CORS preflight, which our CORS policy rejects.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response
from pymongo.errors import DuplicateKeyError

from app.deps import DbDep, SettingsDep, UserDep
from app.ratelimit import client_ip, enforce_db_limit
from app.schemas import LoginIn, SignupIn, TokenOut, UserOut
from app.security import (
    create_access_token,
    hash_password,
    hash_token,
    needs_rehash,
    new_refresh_token,
    verify_password,
)
from app.services.audit import audit

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

REFRESH_COOKIE = "fc_refresh"
COOKIE_PATH = "/api/v1/auth"
# A refresh token re-presented within this window after rotation is treated as a benign race (two tabs
# refreshing at once) and simply rejected; later reuse is treated as theft and revokes the whole family.
REUSE_GRACE = timedelta(seconds=10)


def _require_csrf_header(x_requested_with: str | None) -> None:
    if x_requested_with != "flashcart":
        raise HTTPException(status_code=403, detail="Missing CSRF header")


def _user_out(user: dict) -> UserOut:
    return UserOut(id=str(user["_id"]), email=user["email"], name=user.get("name", ""), role=user["role"])


async def _issue_tokens(
    request: Request, response: Response, settings, db, user: dict, family: str | None = None
) -> TokenOut:
    raw, digest = new_refresh_token()
    now = datetime.now(UTC)
    await db["refresh_tokens"].insert_one(
        {
            "jti": digest,
            "user_id": user["_id"],
            "family": family or ObjectId().binary.hex(),
            "created_at": now,
            "expires_at": now + timedelta(days=settings.refresh_token_days),
            "used_at": None,
            "revoked": False,
            "ip": client_ip(request),
        }
    )
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )
    access = create_access_token(
        settings, user_id=str(user["_id"]), role=user["role"], session_version=user.get("session_version", 0)
    )
    response.headers["Cache-Control"] = "no-store"
    return TokenOut(access_token=access, expires_in=settings.access_token_minutes * 60, user=_user_out(user))


@router.post("/signup", response_model=TokenOut, status_code=201)
async def signup(body: SignupIn, request: Request, response: Response, settings: SettingsDep, db: DbDep):
    ip = client_ip(request)
    await enforce_db_limit(db, bucket="signup", key=ip, limit=settings.auth_rate_limit_per_minute)
    user = {
        "email": body.email.lower(),
        "name": body.name,
        "password_hash": hash_password(body.password),
        "role": "customer",  # role is never taken from the request
        "session_version": 0,
        "created_at": datetime.now(UTC),
    }
    try:
        result = await db["users"].insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="An account with this email already exists") from None
    user["_id"] = result.inserted_id
    await audit(db, "user.signup", actor_id=user["_id"], ip=ip)
    return await _issue_tokens(request, response, settings, db, user)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, response: Response, settings: SettingsDep, db: DbDep):
    ip = client_ip(request)
    email = body.email.lower()
    await enforce_db_limit(db, bucket="login-ip", key=ip, limit=settings.auth_rate_limit_per_minute)
    await enforce_db_limit(db, bucket="login-email", key=email, limit=settings.auth_rate_limit_per_minute)
    user = await db["users"].find_one({"email": email})
    if not verify_password(user["password_hash"] if user else None, body.password) or user.get("disabled"):
        await audit(db, "auth.login_failed", actor_id=user["_id"] if user else None, ip=ip,
                    details={"email_hash": hash_token(email)[:16]})
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if needs_rehash(user["password_hash"]):
        await db["users"].update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(body.password)}})
    await audit(db, "auth.login", actor_id=user["_id"], ip=ip)
    return await _issue_tokens(request, response, settings, db, user)


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    request: Request,
    response: Response,
    settings: SettingsDep,
    db: DbDep,
    fc_refresh: Annotated[str | None, Cookie()] = None,
    x_requested_with: Annotated[str | None, Header()] = None,
):
    _require_csrf_header(x_requested_with)
    if not fc_refresh or len(fc_refresh) > 200:
        raise HTTPException(status_code=401, detail="Not authenticated")
    now = datetime.now(UTC)
    digest = hash_token(fc_refresh)
    # Atomic claim: only one concurrent request can consume a given refresh token (race conditions, #14).
    token = await db["refresh_tokens"].find_one_and_update(
        {"jti": digest, "used_at": None, "revoked": False, "expires_at": {"$gt": now}},
        {"$set": {"used_at": now}},
    )
    if token is None:
        existing = await db["refresh_tokens"].find_one({"jti": digest})
        if existing and existing.get("used_at"):
            used_at = existing["used_at"]
            if now - used_at > REUSE_GRACE:
                await db["refresh_tokens"].update_many({"family": existing["family"]}, {"$set": {"revoked": True}})
                await audit(db, "auth.refresh_reuse_detected", actor_id=existing["user_id"], ip=client_ip(request))
        response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
        raise HTTPException(status_code=401, detail="Session expired")
    user = await db["users"].find_one({"_id": token["user_id"]})
    if not user or user.get("disabled"):
        raise HTTPException(status_code=401, detail="Session expired")
    return await _issue_tokens(request, response, settings, db, user, family=token["family"])


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    db: DbDep,
    fc_refresh: Annotated[str | None, Cookie()] = None,
    x_requested_with: Annotated[str | None, Header()] = None,
):
    _require_csrf_header(x_requested_with)
    if fc_refresh and len(fc_refresh) <= 200:
        token = await db["refresh_tokens"].find_one({"jti": hash_token(fc_refresh)})
        if token:
            await db["refresh_tokens"].update_many({"family": token["family"]}, {"$set": {"revoked": True}})
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
    response.status_code = 204
    return response


@router.post("/logout-all", status_code=204)
async def logout_all(user: UserDep, request: Request, response: Response, db: DbDep):
    """Invalidates every session: bumps session_version (kills access tokens) and revokes refresh tokens."""
    await db["users"].update_one({"_id": user.id}, {"$inc": {"session_version": 1}})
    await db["refresh_tokens"].update_many({"user_id": user.id}, {"$set": {"revoked": True}})
    await audit(db, "auth.logout_all", actor_id=user.id, ip=client_ip(request))
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
async def me(user: UserDep):
    return UserOut(id=str(user.id), email=user.email, name=user.name, role=user.role)  # type: ignore[arg-type]
