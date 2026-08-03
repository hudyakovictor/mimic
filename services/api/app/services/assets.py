"""Asset service: upload preparation, completion, YouTube/URL import."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import os
import re
import socket
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Asset, User
from ..errors import ConflictError, NotFoundError, ValidationFailedError
from ..media.clips import (
    ClipSegment,
    ClipTranscodeError,
    ClipValidationError,
    probe_media,
    transcode_clip,
    validate_segments,
)
from ..observability import get_logger
from ..repositories.assets import AssetRepository
from ..settings import get_settings
from ..storage import BUCKET_VIDEOS
from ..storage.keys import asset_key, staging_asset_key
from ..storage.s3_client import S3Client

log = get_logger(__name__)
_background_import_tasks: set[asyncio.Task[None]] = set()


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


async def validate_public_media_url(url: str) -> None:
    """Reject non-HTTP and private-network import targets (basic SSRF guard)."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValidationFailedError("Only public HTTP(S) video URLs are allowed")
    if parsed.username or parsed.password:
        raise ValidationFailedError("Credentials in video URLs are not allowed")
    try:
        addresses = await asyncio.get_running_loop().getaddrinfo(
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValidationFailedError("Video host cannot be resolved") from exc
    if not addresses:
        raise ValidationFailedError("Video host cannot be resolved")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValidationFailedError("Private or local video URLs are not allowed")


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
        allowed_mimes = {"video/mp4", "video/quicktime", "video/webm", "video/x-matroska"}
        if mime.lower() not in allowed_mimes:
            raise ValidationFailedError("Unsupported video MIME type")
        if size_bytes <= 0 or size_bytes > get_settings().max_upload_bytes:
            raise ValidationFailedError("Video size is outside the configured upload limit")
        ext = re.sub(r"[^a-z0-9]", "", os.path.splitext(filename)[1].lstrip(".").lower()) or "mp4"
        if ext not in {"mp4", "mov", "webm", "mkv", "m4v"}:
            raise ValidationFailedError("Unsupported video file extension")
        asset_id = uuid.uuid4()
        object_key = staging_asset_key(self.tenant_id, asset_id, ext)
        asset = await self.repo.create_pending(
            source_type="UPLOAD",
            object_key=object_key,
            mime=mime,
            size_bytes=size_bytes,
            uploaded_by=self.user.id,
            title=title,
            asset_id=asset_id,
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
        sha256: str | None,
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
        # Verify and probe from a temporary file. Never duplicate a potentially
        # 1 GB source in API process memory.
        suffix = Path(asset.object_key).suffix or ".mp4"
        try:
            with tempfile.TemporaryDirectory(prefix="mimicguard-verify-") as tmp:
                local_path = os.path.join(tmp, f"source{suffix}")
                await self.s3.download_file(BUCKET_VIDEOS, asset.object_key, local_path)
                actual_sha = await asyncio.to_thread(_sha256_file, local_path)
                if sha256 is not None and actual_sha != sha256:
                    raise ValidationFailedError(
                        f"SHA-256 mismatch: client {sha256[:12]}... vs actual {actual_sha[:12]}..."
                    )
                try:
                    info = await probe_media(local_path)
                except ClipTranscodeError as exc:
                    raise ValidationFailedError(f"Uploaded object is not a valid video: {exc}") from exc
                if info.duration_ms > get_settings().max_video_duration_seconds * 1000:
                    raise ValidationFailedError("Video exceeds the maximum source duration")
                if not info.has_audio:
                    raise ValidationFailedError("Video must contain an audio track")
                duration_ms = info.duration_ms
                width = info.width
                height = info.height
                fps = info.fps
                has_audio = info.has_audio
        except ValidationFailedError:
            raise
        except Exception as exc:
            raise ValidationFailedError(f"Cannot verify uploaded object: {exc}") from exc
        # Update
        await self.repo.mark_ready(asset_id, actual_sha, duration_ms, width, height, fps, has_audio)
        log.info(
            "asset.ready",
            asset_id=str(asset_id),
            sha256=actual_sha[:12],
            duration_ms=duration_ms,
            tenant_id=str(self.tenant_id),
        )
        ready_asset = await self.repo.get(asset_id)
        if ready_asset is None:  # defensive: row existed at method entry
            raise NotFoundError("Asset not found after completion")
        return ready_asset

    async def create_clips(
        self,
        source_asset_id: uuid.UUID,
        intervals: list[ClipSegment],
        *,
        delete_source: bool = True,
    ) -> tuple[list[Asset], bool]:
        """Materialize selected intervals as canonical analysis assets.

        This MVP performs the transcode inside the request while using async
        subprocess and multipart S3 transfers. Deployments with long clips can
        move this exact service call to the media queue without changing the
        API contract.
        """
        source = await self.repo.get(source_asset_id)
        if source is None:
            raise NotFoundError("Source asset not found")
        if source.state != "READY":
            raise ConflictError(
                f"Source asset is {source.state}, expected READY",
                code="invalid_asset_state",
            )

        with tempfile.TemporaryDirectory(prefix="mimicguard-clips-") as tmp:
            source_suffix = Path(source.object_key).suffix or ".mp4"
            source_path = os.path.join(tmp, f"source{source_suffix}")
            await self.s3.download_file(BUCKET_VIDEOS, source.object_key, source_path)
            try:
                source_info = await probe_media(source_path)
            except ClipTranscodeError as exc:
                raise ValidationFailedError(str(exc)) from exc
            duration_ms = source.duration_ms or source_info.duration_ms
            if not source_info.has_audio:
                raise ValidationFailedError("Video must contain speech audio for word alignment")
            try:
                ordered = validate_segments(
                    intervals,
                    source_duration_ms=duration_ms,
                    max_total_ms=get_settings().max_selected_duration_seconds * 1000,
                )
            except ClipValidationError as exc:
                raise ValidationFailedError(str(exc)) from exc

            created: list[Asset] = []
            uploaded_keys: list[str] = []
            try:
                for index, interval in enumerate(ordered, start=1):
                    clip_id = uuid.uuid4()
                    object_key = asset_key(self.tenant_id, clip_id, "mp4")
                    output_path = os.path.join(tmp, f"clip-{index:02d}.mp4")
                    await transcode_clip(
                        source_path,
                        output_path,
                        interval,
                        source_fps=source_info.fps,
                        has_audio=source_info.has_audio,
                    )
                    output_info = await probe_media(output_path)
                    size_bytes = os.path.getsize(output_path)
                    digest = await asyncio.to_thread(_sha256_file, output_path)
                    title_base = source.title or "Video"
                    clip = await self.repo.create_pending(
                        source_type="CLIP",
                        source_url=source.source_url,
                        object_key=object_key,
                        mime="video/mp4",
                        size_bytes=size_bytes,
                        uploaded_by=self.user.id,
                        title=interval.label or f"{title_base} · fragment {index}",
                        asset_id=clip_id,
                        extra={
                            "parent_asset_id": str(source.id),
                            "source_start_ms": interval.start_ms,
                            "source_end_ms": interval.end_ms,
                            "codec_profile": "analysis-v1",
                            "video_codec": "h264",
                            "crf": 17,
                        },
                    )
                    await self.s3.upload_file(
                        BUCKET_VIDEOS,
                        object_key,
                        output_path,
                        "video/mp4",
                    )
                    uploaded_keys.append(object_key)
                    await self.repo.mark_ready(
                        clip.id,
                        digest,
                        output_info.duration_ms,
                        output_info.width,
                        output_info.height,
                        output_info.fps,
                        output_info.has_audio,
                        size_bytes=size_bytes,
                    )
                    created.append(clip)
            except Exception:
                # No dangling clip objects if a later interval fails. DB changes
                # roll back with the request; objects need explicit cleanup.
                for key in uploaded_keys:
                    await self.s3.delete_object(BUCKET_VIDEOS, key)
                raise

        source_deleted = False
        if delete_source:
            await self.s3.delete_object(BUCKET_VIDEOS, source.object_key)
            await self.repo.mark_deleted(
                source.id,
                reason=f"replaced_by_{len(created)}_analysis_clips",
            )
            source_deleted = True
        log.info(
            "asset.clips.created",
            source_asset_id=str(source.id),
            clip_ids=[str(clip.id) for clip in created],
            source_deleted=source_deleted,
            tenant_id=str(self.tenant_id),
        )
        return created, source_deleted

    async def import_from_url(self, url: str, title: str | None = None) -> dict:
        source_type = detect_source_type(url)
        if source_type == "UPLOAD":
            raise ValidationFailedError("Invalid video URL")
        await validate_public_media_url(url)
        task_id = uuid.uuid4()
        asset_id = uuid.uuid4()
        ext = "mp4"
        object_key = staging_asset_key(self.tenant_id, asset_id, ext)
        await self.repo.create_pending(
            source_type=source_type,
            source_url=url,
            object_key=object_key,
            mime="video/mp4",
            size_bytes=0,
            uploaded_by=self.user.id,
            title=title,
            asset_id=asset_id,
        )
        # Keep a strong task reference until completion. Production may move
        # imports to the media queue without changing this API contract.
        task = asyncio.create_task(self._download_in_background(asset_id, url, source_type))
        _background_import_tasks.add(task)
        task.add_done_callback(_background_import_tasks.discard)
        return {
            "task_id": str(task_id),
            "asset_id": str(asset_id),
            "state": "PENDING",
            "progress": 0.0,
            "error": None,
        }

    async def _download_in_background(self, asset_id: uuid.UUID, url: str, source_type: str) -> None:
        """Run an import in a transaction independent of the HTTP request."""
        from ..db.session import session_scope

        # Yield once so get_db can commit the pending Asset after the 202 response.
        await asyncio.sleep(0)
        async with session_scope() as session:
            detached = AssetService(session, self.s3, self.tenant_id, self.user)
            try:
                if source_type == "YOUTUBE":
                    await detached._download_youtube(asset_id, url)
                else:
                    await detached._download_direct(asset_id, url)
            except Exception as exc:
                log.exception("asset.import.failed", asset_id=str(asset_id), url=url)
                await detached.repo.mark_failed(asset_id, str(exc)[:500])

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
                str(get_settings().max_upload_bytes),
                "--no-playlist",
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"yt-dlp failed: {stderr.decode()[:500]}")
            size_bytes = os.path.getsize(out_path)
            sha = await asyncio.to_thread(_sha256_file, out_path)
            asset = await self.repo.get(asset_id)
            if asset is None:
                raise RuntimeError("Pending import asset disappeared")
            info = await probe_media(out_path)
            if info.duration_ms > get_settings().max_video_duration_seconds * 1000:
                raise ValidationFailedError("Video exceeds the maximum source duration")
            if not info.has_audio:
                raise ValidationFailedError("Video must contain an audio track")
            await self.s3.upload_file(BUCKET_VIDEOS, asset.object_key, out_path, "video/mp4")
            await self.repo.mark_ready(
                asset_id,
                sha,
                info.duration_ms,
                info.width,
                info.height,
                info.fps,
                info.has_audio,
                size_bytes=size_bytes,
            )

    async def _download_direct(self, asset_id: uuid.UUID, url: str) -> None:
        max_bytes = get_settings().max_upload_bytes
        current_url = url
        tmp_path: str | None = None
        try:
            async with httpx.AsyncClient(follow_redirects=False, timeout=600) as client:
                for _redirect in range(6):
                    await validate_public_media_url(current_url)
                    async with client.stream("GET", current_url) as response:
                        if response.is_redirect:
                            location = response.headers.get("location")
                            if not location:
                                raise ValidationFailedError("Video redirect has no location")
                            current_url = urljoin(current_url, location)
                            continue
                        response.raise_for_status()
                        declared_size = int(response.headers.get("content-length") or 0)
                        if declared_size > max_bytes:
                            raise ValidationFailedError("Remote video exceeds the upload limit")
                        with tempfile.NamedTemporaryFile(delete=False) as tmp:
                            tmp_path = tmp.name
                            downloaded = 0
                            async for chunk in response.aiter_bytes(1024 * 1024):
                                downloaded += len(chunk)
                                if downloaded > max_bytes:
                                    raise ValidationFailedError("Remote video exceeds the upload limit")
                                tmp.write(chunk)
                        break
                else:
                    raise ValidationFailedError("Too many redirects while importing video")
            if tmp_path is None:
                raise ValidationFailedError("Remote video returned no data")
            size_bytes = os.path.getsize(tmp_path)
            sha = await asyncio.to_thread(_sha256_file, tmp_path)
            info = await probe_media(tmp_path)
            if info.duration_ms > get_settings().max_video_duration_seconds * 1000:
                raise ValidationFailedError("Video exceeds the maximum source duration")
            if not info.has_audio:
                raise ValidationFailedError("Video must contain an audio track")
            asset = await self.repo.get(asset_id)
            if asset is None:
                raise RuntimeError("Pending import asset disappeared")
            await self.s3.upload_file(BUCKET_VIDEOS, asset.object_key, tmp_path, "video/mp4")
            await self.repo.mark_ready(
                asset_id,
                sha,
                info.duration_ms,
                info.width,
                info.height,
                info.fps,
                info.has_audio,
                size_bytes=size_bytes,
            )
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def get_download_url(self, asset_id: uuid.UUID) -> dict:
        asset = await self.repo.get(asset_id)
        if asset is None or asset.state == "DELETED":
            raise NotFoundError("Asset not found")
        if asset.state != "READY":
            raise ConflictError(
                f"Asset is {asset.state}, expected READY",
                code="invalid_asset_state",
            )
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
