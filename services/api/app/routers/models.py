"""Models router."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas import ModelPromoteRequest, ModelVersionOut
from ..security.rbac import Permission, require_permission
from ..services.models_service import ModelService

router = APIRouter(prefix="/v1/models", tags=["models"])


@router.get("", response_model=list[ModelVersionOut])
async def list_models(
    user: Annotated[object, Depends(require_permission(Permission.MODEL_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    kind: str | None = Query(default=None),
    state: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    svc = ModelService(db, user.tenant_id, user)
    items, _ = await svc.list(kind, state, cursor, limit)
    return [ModelVersionOut(**m) for m in items]


@router.get("/{model_id}", response_model=ModelVersionOut)
async def get_model(
    model_id: uuid.UUID,
    user: Annotated[object, Depends(require_permission(Permission.MODEL_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = ModelService(db, user.tenant_id, user)
    return ModelVersionOut(**await svc.get(model_id))


@router.post("/{model_id}:promote", response_model=ModelVersionOut)
async def promote_model(
    model_id: uuid.UUID,
    body: ModelPromoteRequest,
    user: Annotated[object, Depends(require_permission(Permission.MODEL_PROMOTE))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = ModelService(db, user.tenant_id, user)
    m = await svc.promote(model_id, body.to_state, body.reason)
    return ModelVersionOut(**m)
