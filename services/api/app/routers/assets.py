"""Assets router: upload prep, complete, import, list."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..db.models import User
from ..dependencies import S3Dep
from ..schemas import (
    AssetOut,
    CompleteUploadRequest,
    CreateClipsRequest,
    CreateClipsResponse,
    DownloadUrlResponse,
    ImportFromUrlRequest,
    ImportTaskStatus,
    PrepareUploadRequest,
    PrepareUploadResponse,
)
from ..security.rbac import Permission, require_permission
from ..services.assets import AssetService

router = APIRouter(prefix="/v1/assets", tags=["assets"])


def _to_asset_out(asset) -> AssetOut:
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
        extra=asset.extra or {},
        created_at=asset.created_at,
    )


@router.post(":prepareUpload", response_model=PrepareUploadResponse)
async def prepare_upload(
    body: PrepareUploadRequest,
    user: Annotated[User, Depends(require_permission(Permission.ASSET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
):
    svc = AssetService(db, s3, user.tenant_id, user)
    return await svc.prepare_upload(body.filename, body.mime, body.size_bytes, body.title)


@router.post("/{asset_id}:completeUpload", response_model=AssetOut)
async def complete_upload(
    asset_id: uuid.UUID,
    body: CompleteUploadRequest,
    user: Annotated[User, Depends(require_permission(Permission.ASSET_WRITE))],
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
    return _to_asset_out(asset)


@router.post("/{asset_id}:createClips", response_model=CreateClipsResponse)
async def create_clips(
    asset_id: uuid.UUID,
    body: CreateClipsRequest,
    user: Annotated[User, Depends(require_permission(Permission.ASSET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
):
    """Cut selected intervals and optionally erase the long source object."""
    from ..media.clips import ClipSegment

    service = AssetService(db, s3, user.tenant_id, user)
    clips, source_deleted = await service.create_clips(
        asset_id,
        [
            ClipSegment(start_ms=item.start_ms, end_ms=item.end_ms, label=item.label)
            for item in body.intervals
        ],
        delete_source=body.delete_source,
    )
    return CreateClipsResponse(
        clips=[_to_asset_out(clip) for clip in clips],
        source_deleted=source_deleted,
        total_duration_ms=sum((clip.duration_ms or 0) for clip in clips),
    )


@router.post(":importFromUrl", response_model=ImportTaskStatus)
async def import_from_url(
    body: ImportFromUrlRequest,
    user: Annotated[User, Depends(require_permission(Permission.ASSET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
):
    svc = AssetService(db, s3, user.tenant_id, user)
    return await svc.import_from_url(body.url, body.title)


@router.get("", response_model=list[AssetOut])
async def list_assets(
    user: Annotated[User, Depends(require_permission(Permission.ASSET_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
    state: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
):
    svc = AssetService(db, s3, user.tenant_id, user)
    items, _ = await svc.list_assets(state, cursor, limit)
    return [_to_asset_out(asset) for asset in items]


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: uuid.UUID,
    user: Annotated[User, Depends(require_permission(Permission.ASSET_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
):
    AssetService(db, s3, user.tenant_id, user)
    from ..repositories.assets import AssetRepository

    a = await AssetRepository(db, user.tenant_id).get(asset_id)
    if a is None:
        from ..errors import NotFoundError

        raise NotFoundError("Asset not found")
    return _to_asset_out(a)


@router.get("/{asset_id}/downloadUrl", response_model=DownloadUrlResponse)
async def get_download_url(
    asset_id: uuid.UUID,
    user: Annotated[User, Depends(require_permission(Permission.ASSET_DOWNLOAD))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
):
    svc = AssetService(db, s3, user.tenant_id, user)
    return await svc.get_download_url(asset_id)
