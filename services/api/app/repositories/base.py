"""Repository base with pagination + tenant scoping helpers.

MG-STUB: final.
"""
from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.base import Base

T = TypeVar("T", bound=Base)


def encode_cursor(created_at: Any, id: uuid.UUID) -> str:
    payload = json.dumps({"created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at), "id": str(id)})
    return base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()


def decode_cursor(cursor: str) -> dict[str, Any]:
    pad = "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode(cursor + pad)
    return json.loads(raw)


class BaseRepository(Generic[T]):
    model: type[T]

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def get(self, id: uuid.UUID) -> T | None:
        """Fetch a single row by id, scoped to the current tenant.

        All entities that use BaseRepository inherit from TenantScopedMixin,
        so the tenant_id column always exists. We apply it here to enforce
        tenant isolation at the repository layer (defence in depth).
        """
        from sqlalchemy import select

        if not hasattr(self.model, "tenant_id"):
            return await self.session.get(self.model, id)
        result = await self.session.execute(
            select(self.model).where(
                getattr(self.model, "id") == id,
                getattr(self.model, "tenant_id") == self.tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 200) -> Sequence[T]:
        stmt = select(self.model).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def paginate(
        self,
        base_stmt,
        cursor: str | None,
        limit: int = 50,
        order_col: Any = None,
    ) -> tuple[list[T], str | None]:
        """Cursor pagination helper.

        Order: created_at desc, id desc.
        """
        from sqlalchemy import and_, desc

        order_col = order_col or getattr(self.model, "created_at", None)
        if order_col is None:
            raise ValueError("Model has no created_at; specify order_col")

        stmt = base_stmt.order_by(desc(order_col), desc(self.model.id)).limit(limit + 1)

        if cursor:
            try:
                c = decode_cursor(cursor)
                c_created = c["created_at"]
                c_id = c["id"]
                stmt = stmt.where(
                    and_(
                        order_col < c_created,
                        self.model.id < uuid.UUID(c_id),
                    )
                )
            except Exception as e:
                from ..errors import ValidationFailedError

                raise ValidationFailedError(f"Invalid cursor: {e}") from e

        result = await self.session.execute(stmt)
        items = list(result.scalars().unique().all())
        next_cursor: str | None = None
        if len(items) > limit:
            items = items[:limit]
            last = items[-1]
            next_cursor = encode_cursor(last.created_at, last.id)
        return items, next_cursor

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)
