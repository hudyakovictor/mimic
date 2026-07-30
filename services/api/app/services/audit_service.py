"""Audit service: queries and export."""
from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import User
from ..repositories.audit import AuditRepository


class AuditService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID, actor: User):
        self.session = session
        self.tenant_id = tenant_id
        self.actor = actor
        self.repo = AuditRepository(session, tenant_id)

    async def list(
        self,
        actor_id: uuid.UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[dict], str | None]:
        items, next_cursor = await self.repo.list_filtered(
            actor_id, action, resource_type, resource_id, from_dt, to_dt, cursor, limit
        )
        return (
            [
                {
                    "id": str(e.id),
                    "actor_id": str(e.actor_id) if e.actor_id else None,
                    "action": e.action,
                    "resource_type": e.resource_type,
                    "resource_id": e.resource_id,
                    "at": e.at,
                    "ip": e.ip,
                    "correlation_id": str(e.correlation_id) if e.correlation_id else None,
                    "reason": e.reason,
                }
                for e in items
            ],
            next_cursor,
        )

    async def export(
        self, fmt: str = "csv", filters: dict | None = None
    ) -> tuple[bytes, str]:
        filters = filters or {}
        items, _ = await self.repo.list_filtered(**filters, limit=10000)
        if fmt == "csv":
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["id", "at", "actor_id", "action", "resource_type", "resource_id", "ip", "reason"])
            for e in items:
                w.writerow(
                    [
                        str(e.id),
                        e.at.isoformat(),
                        str(e.actor_id or ""),
                        e.action,
                        e.resource_type,
                        e.resource_id or "",
                        e.ip or "",
                        (e.reason or "").replace("\n", " "),
                    ]
                )
            return buf.getvalue().encode("utf-8"), "export.csv"
        else:
            buf = io.StringIO()
            for e in items:
                buf.write(
                    json.dumps(
                        {
                            "id": str(e.id),
                            "at": e.at.isoformat(),
                            "actor_id": str(e.actor_id or ""),
                            "action": e.action,
                            "resource_type": e.resource_type,
                            "resource_id": e.resource_id,
                            "ip": e.ip,
                            "reason": e.reason,
                        }
                    )
                    + "\n"
                )
            return buf.getvalue().encode("utf-8"), "export.jsonl"
