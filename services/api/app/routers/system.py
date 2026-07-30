"""System endpoints: health, metrics, info."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..observability import render_metrics
from ..settings import get_settings

router = APIRouter(tags=["system"])


@router.get("/health/live")
async def live():
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as e:
        return Response(
            content=f'{{"status":"not_ready","error":"{e}"}}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json",
        )


@router.get("/metrics")
async def metrics():
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)


@router.get("/info")
async def info():
    s = get_settings()
    return {
        "service": s.service_name,
        "env": s.env,
        "version": "0.1.0",
    }
