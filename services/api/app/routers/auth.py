"""Auth router."""
from __future__ import annotations

from typing import Annotated, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import CurrentUserDep, get_jwt_service
from ..schemas import CurrentUser, LoginRequest, RefreshRequest, TokenPair
from ..security.jwt_service import JwtService
from ..services.auth import AuthService

router = APIRouter(prefix="/v1/auth", tags=["auth"])


async def _try_get_redis() -> Optional[aioredis.Redis]:
    """Return a Redis client if reachable, otherwise None (graceful degradation)."""
    try:
        from ..dependencies import get_redis

        return await get_redis()
    except Exception:
        return None


@router.post("/login", response_model=TokenPair)
async def login(
    body: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    jwt: Annotated[JwtService, Depends(get_jwt_service)],
):
    redis = await _try_get_redis()
    svc = AuthService(db, redis, jwt)
    return await svc.login(
        body.email, body.password, ip=request.client.host if request.client else None
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    jwt: Annotated[JwtService, Depends(get_jwt_service)],
):
    redis = await _try_get_redis()
    svc = AuthService(db, redis, jwt)
    return await svc.refresh(body.refresh_token)


@router.post("/logout")
async def logout(
    body: RefreshRequest,
    jwt: Annotated[JwtService, Depends(get_jwt_service)],
):
    redis = await _try_get_redis()
    svc = AuthService(None, redis, jwt)  # type: ignore[arg-type]
    try:
        await svc.logout(body.refresh_token)
    except Exception:
        pass
    return {"ok": True}


@router.get("/me", response_model=CurrentUser)
async def me(user: CurrentUserDep):
    return CurrentUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=user.roles,
        tenant_id=user.tenant_id,
        tenant_slug="",
    )
