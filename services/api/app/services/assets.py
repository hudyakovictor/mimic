"""Asset service: upload preparation, completion, YouTube/URL import."""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import tempfile
import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Asset, User
from ..errors import NotFoundError, ValidationFailedError
from ..observability import get_logger
from ..repositories.assets import AssetRepository
from ..storage import BUCKET_VIDEOS
from ..storage.keys import asset_key
from ..storage.s3_client import S3Client

log = get_logger(__name__)


YOUTUBE_PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_-]{11})",
    r"(?:https?://)?(?:www\.)?youtu\.be/([A-Za-z0-9_-]{11})",
    r"(?:https?://)?(?:www\.)?youtube\.com/embed/([A-Za-z0-9_-]{11})",
]


def detect_source_type(url: str) -> str:
    for pat in YOUTUBE_PATTERNS:
        if re.match(pat, url):
            return "YOUTUBE"
    if re.match(r"https?://", url):
        return "URL"
    return "UPLOAD"


def extract_youtube_id(url: str) -> str | None:
    for pat in YOUTUBE_PATTERNS:
        m = re.match(pat, url)
        if m:
            return m.group(1)
    return None


class AssetService:
    def __init__(self, session: AsyncSession, s3: S3Client, tenant_id: uuid.UUID, user: User):
        self.session = session
        self.s3 = s3
        self.tenant_id = tenant_id
        self.user = user
        self.repo = AssetRepository(session, tenant_id)

    async def prepare_upload(
        self, filename: str, mime: str, size_bytes: int, title: str | None = None
    ) -> dict:
        ext = os.path.splitext(filename)[1].lstrip(".") or "mp4"
        asset_id = uuid.uuid4()
        object_key = asset_key(self.tenant_id, asset_id, ext)
        asset = await self.repo.create_pending(
            source_type="UPLOAD",
            object_key=object_key,
            mime=mime,
            size_bytes=size_bytes,
            uploaded_by=self.user.id,
            title=title,
        )
        presigned = await self.s3.generate_presigned_put(
            bucket=BUCKET_VIDEOS,
            key=object_key,
            content_type=mime,
            content_length_range=(1, size_bytes + 1024),
        )
        return {
            "asset_id": str(asset.id),
            "upload_url": presigned["url"],
            "fields": presigned["fields"],
            "object_key": object_key,
            "expires_in": 900,
        }

    async def complete_upload(
        self,
        asset_id: uuid.UUID,
        sha256: str,
        etag: str | None,
        duration_ms: int | None,
        width: int | None,
        height: int | None,
        fps: float | None,
        has_audio: bool,
    ) -> Asset:
        asset = await self.repo.get(asset_id)
        if asset is None:
            raise NotFoundError("Asset not found")
        # Verify SHA-256
        try:
            obj = await self.s3.get_object(BUCKET_VIDEOS, asset.object_key)
        except Exception as e:
            raise ValidationFailedError(f"Cannot read object: {e}")
        actual_sha = hashlib.sha256(obj).hexdigest()
        if actual_sha != sha256:
            raise ValidationFailedError(
                f"SHA-256 mismatch: client {sha256[:12]}... vs actual {actual_sha[:12]}..."
            )
        # Validate via ffprobe (if available)
        if duration_ms is None:
            duration_ms = await self._probe_duration_ms(obj, asset.object_key)
        # Update
        await self.repo.mark_ready(
            asset_id, sha256, duration_ms, width, height, fps, has_audio
        )
        log.info(
            "asset.ready",
            asset_id=str(asset_id),
            sha256=sha256[:12],
            duration_ms=duration_ms,
            tenant_id=str(self.tenant_id),
        )
        return await self.repo.get(asset_id)

    async def import_from_url(self, url: str, title: str | None = None) -> dict:
        source_type = detect_source_type(url)
        task_id = uuid.uuid4()
        asset_id = uuid.uuid4()
        ext = "mp4"
        object_key = asset_key(self.tenant_id, asset_id, ext)
        await self.repo.create_pending(
            source_type=source_type,
            source_url=url,
            object_key=object_key,
            mime="video/mp4",
            size_bytes=0,
            uploaded_by=self.user.id,
            title=title,
        )
        # Fire-and-forget background task
        asyncio.create_task(self._download_in_background(asset_id, url, source_type))
        return {
            "task_id": str(task_id),
            "asset_id": str(asset_id),
            "state": "PENDING",
            "progress": 0.0,
            "error": None,
        }

    async def _download_in_background(
        self, asset_id: uuid.UUID, url: str, source_type: str
    ) -> None:
        try:
            if source_type == "YOUTUBE":
                await self._download_youtube(asset_id, url)
            else:
                await self._download_direct(asset_id, url)
        except Exception as e:
            log.exception("asset.import.failed", asset_id=str(asset_id), url=url)
            await self.repo.mark_failed(asset_id, str(e)[:500])

    async def _download_youtube(self, asset_id: uuid.UUID, url: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "video.mp4")
            # yt-dlp is an optional dep
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "-f",
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
                "-o",
                out_path,
                "--max-filesize",
                "1G",
                "--no-playlist",
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"yt-dlp failed: {stderr.decode()[:500]}")
            os.path.getsize(out_path)
            with open(out_path, "rb") as f:
                body = f.read()
            sha = hashlib.sha256(body).hexdigest()
            asset = await self.repo.get(asset_id)
            await self.s3.put_object(BUCKET_VIDEOS, asset.object_key, body, "video/mp4")
            # Probe (optional)
            duration_ms = await self._probe_duration_ms(body, asset.object_key)
            await self.repo.mark_ready(asset_id, sha, duration_ms, None, None, None, True)

    async def _download_direct(self, asset_id: uuid.UUID, url: str) -> None:
        async with httpx.AsyncClient(follow_redirects=True, timeout=600) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    async for chunk in resp.aiter_bytes(1024 * 1024):
                        tmp.write(chunk)
                    tmp_path = tmp.name
        try:
            os.path.getsize(tmp_path)
            with open(tmp_path, "rb") as f:
                body = f.read()
            sha = hashlib.sha256(body).hexdigest()
            asset = await self.repo.get(asset_id)
            await self.s3.put_object(BUCKET_VIDEOS, asset.object_key, body, "video/mp4")
            duration_ms = await self._probe_duration_ms(body, asset.object_key)
            await self.repo.mark_ready(asset_id, sha, duration_ms, None, None, None, True)
        finally:
            os.unlink(tmp_path)

    async def _probe_duration_ms(self, body: bytes, key: str) -> int | None:
        try:
            import json
            import subprocess

            with tempfile.NamedTemporaryFile(suffix=os.path.splitext(key)[1], delete=False) as tmp:
                tmp.write(body)
                tmp_path = tmp.name
            try:
                proc = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-print_format",
                        "json",
                        "-show_format",
                        tmp_path,
                    ],
                    capture_output=True,
                    timeout=30,
                )
                if proc.returncode != 0:
                    return None
                info = json.loads(proc.stdout)
                dur = float(info.get("format", {}).get("duration", 0))
                return int(dur * 1000) if dur else None
            finally:
                os.unlink(tmp_path)
        except Exception:
            return None

    async def get_download_url(self, asset_id: uuid.UUID) -> dict:
        asset = await self.repo.get(asset_id)
        if asset is None:
            raise NotFoundError("Asset not found")
        url = await self.s3.generate_presigned_get(BUCKET_VIDEOS, asset.object_key)
        return {"url": url, "expires_in": 300}

    async def list_assets(
        self,
        state: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Asset], str | None]:
        if state:
            return await self.repo.list_by_state(state, cursor, limit)
        from sqlalchemy import select

        stmt = select(Asset).where(Asset.tenant_id == self.tenant_id)
        return await self.repo.paginate(stmt, cursor, limit, order_col=Asset.created_at)
