"""Audit router."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas import AuditEventOut
from ..security.rbac import Permission, require_permission
from ..services.audit_service import AuditService

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventOut])
async def list_audit(
    user: Annotated[object, Depends(require_permission(Permission.AUDIT_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    actor_id: uuid.UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    from_dt: datetime | None = Query(default=None),
    to_dt: datetime | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    svc = AuditService(db, user.tenant_id, user)
    items, _ = await svc.list(
        actor_id, action, resource_type, resource_id, from_dt, to_dt, cursor, limit
    )
    return [AuditEventOut(**x) for x in items]


@router.get("/export")
async def export_audit(
    user: Annotated[object, Depends(require_permission(Permission.AUDIT_EXPORT))],
    db: Annotated[AsyncSession, Depends(get_db)],
    format: str = Query(default="csv", pattern="^(csv|jsonl)$"),
):
    svc = AuditService(db, user.tenant_id, user)
    body, filename = await svc.export(format)
    return Response(
        content=body,
        media_type="text/csv" if format == "csv" else "application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
