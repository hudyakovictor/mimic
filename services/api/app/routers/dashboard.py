"""Dashboard router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import CurrentUserDep
from ..schemas import DashboardMetrics
from ..services.dashboard import DashboardService

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


@router.get("/metrics", response_model=DashboardMetrics)
async def get_metrics(
    user: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = DashboardService(db, user.tenant_id)
    return await svc.metrics()
