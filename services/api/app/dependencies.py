"""FastAPI dependencies.

MG-STUB: final — provides db session, current user (from JWT), tenant scoping,
S3 client, redis client, JWT service, audit context.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Optional

import redis.asyncio as aioredis
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .security.current_user import (
    CurrentTenantDep,
    CurrentUserDep,
    get_current_tenant,
    get_current_user,
)
from .security.jwt_service import JwtService, get_jwt_service
from .settings import Settings, get_settings
from .storage.s3_client import S3Client, get_s3_client

# ----------------------------- Settings / DB / S3 / Redis ------------------


def settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_dep)]


def s3_dep(settings: SettingsDep) -> S3Client:
    return get_s3_client(settings)


S3Dep = Annotated[S3Client, Depends(s3_dep)]


_redis_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            get_settings().redis_url, encoding="utf-8", decode_responses=True
        )
    return _redis_pool


RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]


# ----------------------------- Idempotency ---------------------------------


def get_idempotency_key(
    idempotency_key: Annotated[Optional[str], Header(alias="Idempotency-Key")] = None
) -> str:
    if not idempotency_key:
        return str(uuid.uuid4())
    return idempotency_key


IdempotencyKeyDep = Annotated[str, Depends(get_idempotency_key)]


__all__ = [
    "SettingsDep",
    "S3Dep",
    "RedisDep",
    "CurrentUserDep",
    "CurrentTenantDep",
    "IdempotencyKeyDep",
    "get_current_user",
    "get_current_tenant",
    "get_idempotency_key",
    "get_redis",
    "settings_dep",
    "s3_dep",
    "get_db",
    "get_jwt_service",
]
