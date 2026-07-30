"""SQLAlchemy declarative base + shared mixins.

MG-STUB: final — provides Base, TenantScopedMixin, TimestampedMixin, VersionedMixin.
All models must inherit from Base.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent GUID, uses native UUID on PostgreSQL, CHAR(36) elsewhere."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PgUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Any) -> Any | None:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value) if isinstance(value, uuid.UUID) else str(uuid.UUID(str(value)))

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Project-wide declarative base."""

    type_annotation_map = {uuid.UUID: GUID()}


class TenantScopedMixin:
    """Adds a tenant_id column to a model. Required for all tenant-owned entities."""

    @declared_attr
    def tenant_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805
        from sqlalchemy import ForeignKey

        return mapped_column(
            GUID(),
            ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )


class TimestampedMixin:
    """Adds created_at and updated_at."""

    @declared_attr
    def created_at(cls) -> Mapped[datetime]:  # noqa: N805
        return mapped_column(
            DateTime(timezone=True), nullable=False, server_default=func.now()
        )

    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:  # noqa: N805
        return mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )


class VersionedMixin:
    """Optimistic concurrency control."""

    @declared_attr
    def version(cls) -> Mapped[int]:  # noqa: N805
        return mapped_column(Integer, nullable=False, default=1)
