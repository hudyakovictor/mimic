"""Transactional outbox repository.

MG-STUB: final — write events in the same DB transaction as the domain change.
A separate relay process publishes them to Redis Streams.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OutboxEvent


class OutboxRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        event_name: str,
        payload: dict[str, Any],
        correlation_id: uuid.UUID | None = None,
        tenant_id: uuid.UUID | None = None,
    ) -> OutboxEvent:
        ev = OutboxEvent(
            id=uuid.uuid4(),
            event_name=event_name,
            payload=payload,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.session.add(ev)
        await self.session.flush()
        return ev

    async def claim_unpublished(self, limit: int = 200) -> list[OutboxEvent]:
        """Select FOR UPDATE SKIP LOCKED. Caller must be inside a transaction."""
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_published(self, ev_id: uuid.UUID) -> None:
        await self.session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == ev_id)
            .values(published_at=datetime.now(UTC), last_error=None)
        )

    async def increment_attempts(self, ev_id: uuid.UUID, error: str) -> None:
        await self.session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == ev_id)
            .values(attempts=OutboxEvent.attempts + 1, last_error=error[:1000])
        )
