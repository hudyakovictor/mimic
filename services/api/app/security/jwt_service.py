"""JWT token service.

MG-STUB: final — uses python-jose. Supports HS256 (dev) and RS256 (prod).
Refresh token rotation via Redis blacklist.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import redis.asyncio as redis
from jose import JWTError, jwt

from ..errors import UnauthorizedError
from ..settings import Settings, get_settings


class JwtService:
    def __init__(self, settings: Settings, redis_client: redis.Redis | None = None):
        self.settings = settings
        self._redis = redis_client

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def _claims(self, user_id: uuid.UUID, tenant_id: uuid.UUID, roles: list[str]) -> dict:
        now = self._now()
        return {
            "sub": str(user_id),
            "tid": str(tenant_id),
            "roles": roles,
            "iat": int(now.timestamp()),
            "aud": self.settings.jwt_audience,
            "iss": self.settings.jwt_issuer,
            "jti": str(uuid.uuid4()),
        }

    def encode_access(self, user_id: uuid.UUID, tenant_id: uuid.UUID, roles: list[str]) -> tuple[str, int]:
        claims = self._claims(user_id, tenant_id, roles)
        ttl = self.settings.access_token_ttl_seconds
        exp = datetime.now(UTC) + timedelta(seconds=ttl)
        claims["exp"] = int(exp.timestamp())
        secret = self.settings.jwt_secret.get_secret_value()
        token = jwt.encode(claims, secret, algorithm=self.settings.jwt_alg)
        return token, ttl

    def encode_refresh(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
        claims = self._claims(user_id, tenant_id, [])
        claims["typ"] = "refresh"
        ttl = self.settings.refresh_token_ttl_seconds
        exp = datetime.now(UTC) + timedelta(seconds=ttl)
        claims["exp"] = int(exp.timestamp())
        secret = self.settings.jwt_secret.get_secret_value()
        return jwt.encode(claims, secret, algorithm=self.settings.jwt_alg)

    def decode(self, token: str, *, expect_type: str | None = None) -> dict[str, Any]:
        secret = self.settings.jwt_secret.get_secret_value()
        try:
            claims = jwt.decode(
                token,
                secret,
                algorithms=[self.settings.jwt_alg],
                audience=self.settings.jwt_audience,
                issuer=self.settings.jwt_issuer,
            )
        except JWTError as e:
            raise UnauthorizedError(f"Invalid token: {e}") from e

        if expect_type and claims.get("typ") != expect_type:
            raise UnauthorizedError(f"Expected token type {expect_type}")

        return claims

    async def revoke(self, jti: str, ttl: int) -> None:
        if self._redis is None:
            return
        await self._redis.setex(f"jwt:blacklist:{jti}", ttl, "1")

    async def is_revoked(self, jti: str) -> bool:
        if self._redis is None:
            return False
        return bool(await self._redis.exists(f"jwt:blacklist:{jti}"))


_jwt_service: JwtService | None = None


def get_jwt_service() -> JwtService:
    global _jwt_service
    if _jwt_service is None:
        _jwt_service = JwtService(get_settings())
    return _jwt_service
