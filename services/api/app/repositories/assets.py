"""Asset repository."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import attributes

from ..db.models import Asset
from .base import BaseRepository


class AssetRepository(BaseRepository[Asset]):
    model = Asset

    async def create_pending(
        self,
        source_type: str,
        object_key: str,
        mime: str,
        size_bytes: int,
        uploaded_by: uuid.UUID,
        source_url: str | None = None,
        title: str | None = None,
        extra: dict | None = None,
    ) -> Asset:
        a = Asset(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            source_type=source_type,
            source_url=source_url,
            object_key=object_key,
            mime=mime,
            size_bytes=size_bytes,
            has_audio=True,
            state="PENDING_UPLOAD",
            uploaded_by=uploaded_by,
            title=title,
            extra=extra or {},
        )
        self.session.add(a)
        await self.session.flush()
        return a

    async def mark_uploading(self, asset_id: uuid.UUID) -> None:
        a = await self.get(asset_id)
        if a is None:
            return
        attributes.flag_dirty(a, "state")
        a.state = "UPLOADING"
        await self.session.flush()

    async def mark_ready(
        self,
        asset_id: uuid.UUID,
        sha256: str,
        duration_ms: int | None,
        width: int | None,
        height: int | None,
        fps: float | None,
        has_audio: bool,
    ) -> Asset:
        a = await self.get(asset_id)
        if a is None:
            raise ValueError("Asset not found")
        a.sha256 = sha256
        a.duration_ms = duration_ms
        a.width = width
        a.height = height
        a.fps = fps
        a.has_audio = has_audio
        a.state = "READY"
        await self.session.flush()
        return a

    async def mark_failed(self, asset_id: uuid.UUID, reason: str) -> None:
        a = await self.get(asset_id)
        if a is None:
            return
        a.state = "FAILED"
        a.failure_reason = reason
        await self.session.flush()

    async def list_by_state(self, state: str, cursor=None, limit: int = 50):

        stmt = select(Asset).where(
            Asset.tenant_id == self.tenant_id,
            Asset.state == state,
        )
        return await self.paginate(stmt, cursor, limit, order_col=Asset.created_at)
