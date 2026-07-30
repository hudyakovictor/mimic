"""Audit repository."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select

from ..db.models import AuditEvent
from .base import BaseRepository


class AuditRepository(BaseRepository[AuditEvent]):
    model = AuditEvent

    async def create(
        self,
        action: str,
        resource_type: str,
        resource_id: str | None,
        actor_id: uuid.UUID | None,
        ip: str | None = None,
        user_agent: str | None = None,
        correlation_id: uuid.UUID | None = None,
        reason: str | None = None,
        extra: dict | None = None,
    ) -> AuditEvent:
        e = AuditEvent(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            at=datetime.utcnow(),
            ip=ip,
            user_agent=user_agent,
            correlation_id=correlation_id,
            reason=reason,
            extra=extra or {},
        )
        self.session.add(e)
        await self.session.flush()
        return e

    async def list_filtered(
        self,
        actor_id: uuid.UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[AuditEvent], str | None]:
        stmt = select(AuditEvent).where(AuditEvent.tenant_id == self.tenant_id)
        if actor_id:
            stmt = stmt.where(AuditEvent.actor_id == actor_id)
        if action:
            stmt = stmt.where(AuditEvent.action == action)
        if resource_type:
            stmt = stmt.where(AuditEvent.resource_type == resource_type)
        if resource_id:
            stmt = stmt.where(AuditEvent.resource_id == resource_id)
        if from_dt:
            stmt = stmt.where(AuditEvent.at >= from_dt)
        if to_dt:
            stmt = stmt.where(AuditEvent.at <= to_dt)
        return await self.paginate(stmt, cursor, limit, order_col=AuditEvent.at)
