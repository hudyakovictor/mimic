"""Assets router: upload prep, complete, import, list."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import S3Dep
from ..schemas import (
    AssetOut,
    CompleteUploadRequest,
    DownloadUrlResponse,
    ImportFromUrlRequest,
    ImportTaskStatus,
    PrepareUploadRequest,
    PrepareUploadResponse,
)
from ..security.rbac import Permission, require_permission
from ..services.assets import AssetService

router = APIRouter(prefix="/v1/assets", tags=["assets"])


@router.post(":prepareUpload", response_model=PrepareUploadResponse)
async def prepare_upload(
    body: PrepareUploadRequest,
    user: Annotated[object, Depends(require_permission(Permission.ASSET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
):
    svc = AssetService(db, s3, user.tenant_id, user)
    return await svc.prepare_upload(body.filename, body.mime, body.size_bytes, body.title)


@router.post("/{asset_id}:completeUpload", response_model=AssetOut)
async def complete_upload(
    asset_id: uuid.UUID,
    body: CompleteUploadRequest,
    user: Annotated[object, Depends(require_permission(Permission.ASSET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
):
    svc = AssetService(db, s3, user.tenant_id, user)
    asset = await svc.complete_upload(
        asset_id,
        body.sha256,
        body.etag,
        body.duration_ms,
        body.width,
        body.height,
        body.fps,
        body.has_audio,
    )
    return AssetOut(
        id=asset.id,
        source_type=asset.source_type,
        source_url=asset.source_url,
        mime=asset.mime,
        size_bytes=asset.size_bytes,
        sha256=asset.sha256,
        duration_ms=asset.duration_ms,
        width=asset.width,
        height=asset.height,
        fps=asset.fps,
        has_audio=asset.has_audio,
        state=asset.state,
        title=asset.title,
        failure_reason=asset.failure_reason,
        created_at=asset.created_at,
    )


@router.post(":importFromUrl", response_model=ImportTaskStatus)
async def import_from_url(
    body: ImportFromUrlRequest,
    user: Annotated[object, Depends(require_permission(Permission.ASSET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
):
    svc = AssetService(db, s3, user.tenant_id, user)
    return await svc.import_from_url(body.url, body.title)


@router.get("", response_model=list[AssetOut])
async def list_assets(
    user: Annotated[object, Depends(require_permission(Permission.ASSET_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
    state: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
):
    svc = AssetService(db, s3, user.tenant_id, user)
    items, _ = await svc.list_assets(state, cursor, limit)
    return [
        AssetOut(
            id=a.id,
            source_type=a.source_type,
            source_url=a.source_url,
            mime=a.mime,
            size_bytes=a.size_bytes,
            sha256=a.sha256,
            duration_ms=a.duration_ms,
            width=a.width,
            height=a.height,
            fps=a.fps,
            has_audio=a.has_audio,
            state=a.state,
            title=a.title,
            failure_reason=a.failure_reason,
            created_at=a.created_at,
        )
        for a in items
    ]


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: uuid.UUID,
    user: Annotated[object, Depends(require_permission(Permission.ASSET_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
):
    AssetService(db, s3, user.tenant_id, user)
    from ..repositories.assets import AssetRepository

    a = await AssetRepository(db, user.tenant_id).get(asset_id)
    if a is None:
        from ..errors import NotFoundError

        raise NotFoundError("Asset not found")
    return AssetOut(
        id=a.id,
        source_type=a.source_type,
        source_url=a.source_url,
        mime=a.mime,
        size_bytes=a.size_bytes,
        sha256=a.sha256,
        duration_ms=a.duration_ms,
        width=a.width,
        height=a.height,
        fps=a.fps,
        has_audio=a.has_audio,
        state=a.state,
        title=a.title,
        failure_reason=a.failure_reason,
        created_at=a.created_at,
    )


@router.get("/{asset_id}/downloadUrl", response_model=DownloadUrlResponse)
async def get_download_url(
    asset_id: uuid.UUID,
    user: Annotated[object, Depends(require_permission(Permission.ASSET_DOWNLOAD))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
):
    svc = AssetService(db, s3, user.tenant_id, user)
    return await svc.get_download_url(asset_id)
