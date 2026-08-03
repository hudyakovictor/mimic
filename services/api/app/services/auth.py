"""Auth service: login, refresh, logout, me."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Tenant, User
from ..errors import UnauthorizedError
from ..observability import get_logger
from ..security.jwt_service import JwtService
from ..security.passwords import verify_password

log = get_logger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession, redis: Optional[aioredis.Redis], jwt: JwtService):
        self.session = session
        self.redis = redis
        self.jwt = jwt

    async def login(
        self,
        email: str,
        password: str,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        # Rate limit: 5 attempts/min/IP (graceful when Redis is unavailable)
        if ip and self.redis is not None:
            try:
                key = f"auth:login_attempts:{ip}"
                count = await self.redis.incr(key)
                if count == 1:
                    await self.redis.expire(key, 60)
            except Exception as e:
                # If Redis is down, do not block login (graceful degradation)
                log.warning("auth.rate_limit_unavailable", error=str(e))
            else:
                if count > 5:
                    raise UnauthorizedError("Too many login attempts", code="rate_limited")

        # Look up user across tenants
        stmt = select(User).where(User.email == email.lower(), User.is_active.is_(True))
        result = await self.session.execute(stmt)
        candidates = list(result.scalars().all())
        if len(candidates) != 1:
            raise UnauthorizedError("Invalid credentials")
        user = candidates[0]
        if not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid credentials")

        tenant = await self.session.get(Tenant, user.tenant_id)
        if tenant is None:
            raise UnauthorizedError("Tenant not found")

        access, access_ttl = self.jwt.encode_access(user.id, user.tenant_id, user.roles)
        refresh = self.jwt.encode_refresh(user.id, user.tenant_id)
        user.last_login_at = datetime.now(timezone.utc)
        await self.session.flush()

        log.info(
            "auth.login",
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            ip=ip or "",
        )
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": access_ttl,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
                "roles": user.roles,
                "tenant_id": str(user.tenant_id),
                "tenant_slug": tenant.slug,
            },
        }

    async def refresh(self, refresh_token: str) -> dict:
        claims = self.jwt.decode(refresh_token, expect_type="refresh")
        if self.redis is not None:
            try:
                revoked = await self.jwt.is_revoked(claims.get("jti", ""))
            except Exception:
                revoked = False
            if revoked:
                raise UnauthorizedError("Refresh token revoked")
        user_id = uuid.UUID(claims["sub"])
        tenant_id = uuid.UUID(claims["tid"])
        # Rotation: revoke old (best-effort)
        if self.redis is not None:
            try:
                await self.jwt.revoke(claims["jti"], self.jwt.settings.refresh_token_ttl_seconds)
            except Exception:
                pass
        user = await self.session.get(User, user_id)
        if user is None or not user.is_active or user.tenant_id != tenant_id:
            raise UnauthorizedError("User inactive")
        access, access_ttl = self.jwt.encode_access(user.id, user.tenant_id, user.roles)
        new_refresh = self.jwt.encode_refresh(user.id, user.tenant_id)
        return {
            "access_token": access,
            "refresh_token": new_refresh,
            "token_type": "Bearer",
            "expires_in": access_ttl,
        }

    async def logout(self, refresh_token: str) -> None:
        claims = self.jwt.decode(refresh_token, expect_type="refresh")
        if self.redis is not None:
            try:
                await self.jwt.revoke(claims["jti"], self.jwt.settings.refresh_token_ttl_seconds)
            except Exception:
                pass

    async def me(self, user: User) -> dict:
        tenant = await self.session.get(Tenant, user.tenant_id)
        return {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "roles": user.roles,
            "tenant_id": str(user.tenant_id),
            "tenant_slug": tenant.slug if tenant else "",
        }
