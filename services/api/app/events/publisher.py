"""Event publisher — writes to Redis Streams.

MG-STUB: final.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from ..observability import OUTBOX_PENDING_TOTAL, get_logger
from .outbox import OutboxRepository

log = get_logger(__name__)


STREAM_NAME = "mimicguard.events"


class EventPublisher:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def publish(
        self,
        event_name: str,
        data: dict[str, Any],
        *,
        event_id: uuid.UUID | None = None,
        correlation_id: uuid.UUID | None = None,
        tenant_id: uuid.UUID | None = None,
    ) -> str:
        eid = event_id or uuid.uuid4()
        envelope = {
            "event_id": str(eid),
            "event_name": event_name,
            "event_version": 1,
            "occurred_at": datetime.now(UTC).isoformat(),
            "tenant_id": str(tenant_id) if tenant_id else "",
            "correlation_id": str(correlation_id) if correlation_id else "",
            "data": json.dumps(data, default=str),
        }
        msg_id = await self.redis.xadd(STREAM_NAME, envelope)
        log.debug("event_published", event=event_name, msg_id=msg_id)
        return msg_id

    async def publish_pending_outbox(self, session: AsyncSession, batch_size: int = 200) -> int:
        """Drain unpublished outbox events to Redis. Idempotent via event_id."""
        repo = OutboxRepository(session)
        pending = await repo.claim_unpublished(limit=batch_size)
        if not pending:
            OUTBOX_PENDING_TOTAL.set(0)
            return 0
        published = 0
        for ev in pending:
            try:
                await self.publish(
                    ev.event_name,
                    ev.payload,
                    event_id=ev.id,
                    correlation_id=ev.correlation_id,
                    tenant_id=ev.tenant_id,
                )
                await repo.mark_published(ev.id)
                published += 1
            except Exception as e:
                await repo.increment_attempts(ev.id, str(e))
                log.warning("outbox_publish_failed", event=ev.event_name, error=str(e))
        OUTBOX_PENDING_TOTAL.set(len(pending) - published)
        return published


_publisher: EventPublisher | None = None


def get_publisher(redis_client: aioredis.Redis) -> EventPublisher:
    global _publisher
    if _publisher is None:
        _publisher = EventPublisher(redis_client)
    return _publisher
