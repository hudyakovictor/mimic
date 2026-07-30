"""Event publisher — writes to Redis Streams.

MG-STUB: final.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any, cast

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
        envelope: dict[str, str | int | float] = {
            "event_id": str(eid),
            "event_name": event_name,
            "event_version": 1,
            "occurred_at": datetime.now(UTC).isoformat(),
            "tenant_id": str(tenant_id) if tenant_id else "",
            "correlation_id": str(correlation_id) if correlation_id else "",
            "data": json.dumps(data, default=str),
        }
        msg_id = await self.redis.xadd(STREAM_NAME, cast(Any, envelope))
        log.debug("event_published", event_name=event_name, msg_id=msg_id)
        return msg_id

    async def _dispatch_outbox_event(self, session: AsyncSession, event) -> None:
        """Dispatch commands locally; publish informational events to Streams."""
        if event.event_name == "analysis.requested.v1":
            import dramatiq
            from dramatiq.brokers.redis import RedisBroker

            from ..settings import get_settings

            broker = RedisBroker(url=get_settings().redis_broker_url)
            message: dramatiq.Message[Any] = dramatiq.Message(
                queue_name="analysis.pipeline",
                actor_name="run_pipeline",
                args=(event.payload["job_id"], str(event.correlation_id) if event.correlation_id else None),
                kwargs={},
                options={},
                message_id=str(event.id),
            )
            await asyncio.to_thread(broker.enqueue, message)
            return
        if event.event_name == "review.created.v1" and event.payload.get("verdict") == "CONFIRMED_GENUINE":
            from ..services.reviews import BaselineAggregator
            from ..storage.s3_client import get_s3_client

            tenant_id = event.tenant_id
            if tenant_id is not None:
                await BaselineAggregator(
                    session,
                    get_s3_client(),
                    tenant_id,
                ).on_review_confirmed_genuine(uuid.UUID(event.payload["review_id"]))
            return
        await self.publish(
            event.event_name,
            event.payload,
            event_id=event.id,
            correlation_id=event.correlation_id,
            tenant_id=event.tenant_id,
        )

    async def publish_pending_outbox(self, session: AsyncSession, batch_size: int = 200) -> int:
        """Drain unpublished outbox events to workers/Redis with event-id dedupe."""
        repo = OutboxRepository(session)
        pending = await repo.claim_unpublished(limit=batch_size)
        if not pending:
            OUTBOX_PENDING_TOTAL.set(0)
            return 0
        published = 0
        for ev in pending:
            try:
                await self._dispatch_outbox_event(session, ev)
                await repo.mark_published(ev.id)
                published += 1
            except Exception as e:
                await repo.increment_attempts(ev.id, str(e))
                log.warning(
                    "outbox_publish_failed",
                    event_name=ev.event_name,
                    error=str(e),
                )
        OUTBOX_PENDING_TOTAL.set(len(pending) - published)
        return published


_publisher: EventPublisher | None = None


def get_publisher(redis_client: aioredis.Redis) -> EventPublisher:
    global _publisher
    if _publisher is None:
        _publisher = EventPublisher(redis_client)
    return _publisher
