"""Analysis job service."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import AnalysisJob, LandmarkSequence, User
from ..errors import ConflictError, NotFoundError, ValidationFailedError
from ..events.outbox import OutboxRepository
from ..observability import get_logger
from ..repositories.assets import AssetRepository
from ..repositories.jobs import AnalysisJobRepository, JobStageRepository
from ..repositories.subjects import SubjectRepository
from ..storage import BUCKET_DERIVED, BUCKET_VIDEOS
from ..storage.s3_client import S3Client

log = get_logger(__name__)


class JobService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID, actor: User):
        self.session = session
        self.tenant_id = tenant_id
        self.actor = actor
        self.jobs = AnalysisJobRepository(session, tenant_id)
        self.stages = JobStageRepository(session, tenant_id)
        self.subjects = SubjectRepository(session, tenant_id)
        self.assets = AssetRepository(session, tenant_id)
        self.outbox = OutboxRepository(session)

    async def create(
        self,
        asset_id: uuid.UUID,
        claimed_person_id: uuid.UUID,
        pipeline_version: str = "v1",
        correlation_id: uuid.UUID | None = None,
    ) -> AnalysisJob:
        # Validate asset
        asset = await self.assets.get(asset_id)
        if asset is None or asset.state != "READY":
            raise ValidationFailedError("Asset is not READY")
        if asset.size_bytes <= 0:
            raise ValidationFailedError("Asset has no data")
        if not asset.has_audio:
            raise ValidationFailedError("Asset has no audio for speech alignment")
        # Validate subject + consent
        subject = await self.subjects.get(claimed_person_id)
        if subject is None or subject.deleted_at is not None:
            raise NotFoundError("Subject not found")
        if subject.consent_state != "GRANTED":
            raise ValidationFailedError(f"Subject consent is {subject.consent_state}, not GRANTED")

        job = await self.jobs.create_or_get_idempotent(
            asset_id=asset_id,
            subject_id=claimed_person_id,
            pipeline_version=pipeline_version,
            correlation_id=correlation_id,
        )
        if job.state == "QUEUED":
            # Publish event for worker
            await self.outbox.create(
                event_name="analysis.requested.v1",
                payload={
                    "job_id": str(job.id),
                    "asset_id": str(asset_id),
                    "subject_id": str(claimed_person_id),
                    "tenant_id": str(self.tenant_id),
                    "pipeline_version": pipeline_version,
                    "object_key": asset.object_key,
                    "asset_sha256": asset.sha256,
                },
                correlation_id=correlation_id,
                tenant_id=self.tenant_id,
            )
            log.info(
                "job.create",
                job_id=str(job.id),
                asset_id=str(asset_id),
                subject_id=str(claimed_person_id),
                actor_id=str(self.actor.id),
            )
        return job

    async def get(self, job_id: uuid.UUID) -> AnalysisJob | None:
        return await self.jobs.get(job_id)

    async def get_full(self, job_id: uuid.UUID) -> dict:
        """Return job with stages + latest decision."""
        job = await self.jobs.get(job_id)
        if job is None:
            raise NotFoundError("Job not found")
        stages = await self.stages.list_for_job(job_id)
        from sqlalchemy import desc

        from ..db.models import Decision

        dec_stmt = (
            select(Decision).where(Decision.job_id == job_id).order_by(desc(Decision.created_at)).limit(1)
        )
        result = await self.session.execute(dec_stmt)
        decision = result.scalar_one_or_none()
        return {"job": job, "stages": stages, "decision": decision}

    async def get_artifacts(self, job_id: uuid.UUID, s3: S3Client) -> dict:
        job = await self.jobs.get(job_id)
        if job is None:
            raise NotFoundError("Job not found")
        asset = await self.assets.get(job.asset_id)
        if asset is None or asset.state != "READY":
            raise NotFoundError("Analysis video is not available")
        landmark_stmt = (
            select(LandmarkSequence)
            .where(
                LandmarkSequence.job_id == job_id,
                LandmarkSequence.tenant_id == self.tenant_id,
            )
            .order_by(LandmarkSequence.created_at.desc())
            .limit(1)
        )
        landmarks = (await self.session.execute(landmark_stmt)).scalar_one_or_none()
        return {
            "video_url": await s3.generate_presigned_get(BUCKET_VIDEOS, asset.object_key),
            "landmarks_url": (
                await s3.generate_presigned_get(BUCKET_DERIVED, landmarks.object_key) if landmarks else None
            ),
            "duration_ms": int(asset.duration_ms or 0),
            "fps": float(landmarks.source_fps if landmarks else asset.fps or 30.0),
            "expires_in": 300,
        }

    async def cancel(self, job_id: uuid.UUID) -> AnalysisJob:
        job = await self.jobs.get(job_id)
        if job is None:
            raise NotFoundError("Job not found")
        if job.state not in ("QUEUED",):
            raise ConflictError(
                f"Cannot cancel job in state {job.state}",
                code="invalid_state",
            )
        return await self.jobs.transition(job_id, "QUEUED", "FAILED")

    async def retry(self, job_id: uuid.UUID) -> AnalysisJob:
        job = await self.jobs.get(job_id)
        if job is None:
            raise NotFoundError("Job not found")
        if job.state not in ("FAILED", "INSUFFICIENT_DATA"):
            raise ConflictError(
                f"Cannot retry job in state {job.state}",
                code="invalid_state",
            )
        job.state = "QUEUED"
        job.attempt = (job.attempt or 1) + 1
        job.last_error = None
        job.finished_at = None
        job.started_at = None
        job.version = (job.version or 1) + 1
        await self.session.flush()
        # Re-publish event
        asset = await self.assets.get(job.asset_id)
        await self.outbox.create(
            event_name="analysis.requested.v1",
            payload={
                "job_id": str(job.id),
                "asset_id": str(job.asset_id),
                "subject_id": str(job.subject_id),
                "tenant_id": str(self.tenant_id),
                "pipeline_version": job.pipeline_version,
                "object_key": asset.object_key if asset else "",
                "attempt": job.attempt,
            },
            tenant_id=self.tenant_id,
        )
        return job

    async def list(
        self,
        state: str | None = None,
        subject_id: uuid.UUID | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[AnalysisJob], str | None]:
        return await self.jobs.list_filtered(state, subject_id, cursor, limit)
