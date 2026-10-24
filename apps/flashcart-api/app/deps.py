"""FastAPI dependencies: settings, database, and the authenticated user (authorization is enforced here,
server-side, for every protected route — never inferred from anything the frontend sends)."""

from dataclasses import dataclass
from typing import Annotated

import jwt
from bson import ObjectId
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.asynchronous.database import AsyncDatabase

from app.config import Settings, get_settings
from app.db import get_db
from app.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def settings_dep() -> Settings:
    return get_settings()


def db_dep(settings: Annotated[Settings, Depends(settings_dep)]) -> AsyncDatabase:
    return get_db(settings)


SettingsDep = Annotated[Settings, Depends(settings_dep)]
DbDep = Annotated[AsyncDatabase, Depends(db_dep)]


@dataclass(frozen=True)
class CurrentUser:
    id: ObjectId
    email: str
    name: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


_UNAUTH = HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})


async def current_user(
    request: Request,
    settings: SettingsDep,
    db: DbDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    if creds is None or creds.scheme.lower() != "bearer":
        raise _UNAUTH
    try:
        claims = decode_access_token(settings, creds.credentials)
        user_id = ObjectId(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise _UNAUTH from None
    # Re-read the user so role changes, deactivation and "log out everywhere" (session_version bump) apply
    # immediately instead of when the token expires.
    projection = {"email": 1, "name": 1, "role": 1, "session_version": 1, "disabled": 1}
    user = await db["users"].find_one({"_id": user_id}, projection)
    if not user or user.get("disabled") or user.get("session_version", 0) != claims.get("tv"):
        raise _UNAUTH
    request.state.user_id = str(user_id)
    return CurrentUser(id=user_id, email=user["email"], name=user.get("name", ""), role=user["role"])


async def require_admin(user: Annotated[CurrentUser, Depends(current_user)]) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


UserDep = Annotated[CurrentUser, Depends(current_user)]
AdminDep = Annotated[CurrentUser, Depends(require_admin)]


def parse_object_id(value: str, what: str = "Resource") -> ObjectId:
    if not ObjectId.is_valid(value) or len(value) != 24:
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return ObjectId(value)
