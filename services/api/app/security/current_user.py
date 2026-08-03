"""Current user dependency (separated to avoid circular imports)."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..db.models import Tenant, User
from ..errors import UnauthorizedError
from .jwt_service import JwtService, get_jwt_service
from .tenant_context import TenantContext


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    jwt_service: JwtService = Depends(get_jwt_service),
) -> User:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Missing bearer token")
    token = auth_header.removeprefix("Bearer ").strip()
    try:
        claims = jwt_service.decode(token, expect_type="access")
    except UnauthorizedError:
        raise
    # Revocation check (best-effort — graceful when Redis unavailable)
    try:
        revoked = await jwt_service.is_revoked(claims.get("jti", ""))
    except Exception:
        revoked = False
    if revoked:
        raise UnauthorizedError("Token revoked")

    try:
        user_id = uuid.UUID(claims["sub"])
        tenant_id = uuid.UUID(claims["tid"])
    except (KeyError, TypeError, ValueError) as exc:
        raise UnauthorizedError("Token has invalid subject claims") from exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active or user.tenant_id != tenant_id:
        raise UnauthorizedError("User not found or inactive")

    TenantContext.set(tenant_id)
    request.state.tenant_id = tenant_id
    request.state.actor_id = user_id
    request.state.user = user

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_current_tenant(
    user: CurrentUserDep, db: AsyncSession = Depends(get_db)
) -> Tenant:
    tenant = await db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise UnauthorizedError("Tenant not found")
    return tenant


CurrentTenantDep = Annotated[Tenant, Depends(get_current_tenant)]
