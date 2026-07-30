"""Job and stage repository."""
from __future__ import annotations

import uuid
from datetime import UTC

from sqlalchemy import select

from ..db.models import AnalysisJob, JobStage
from ..errors import ConflictError
from .base import BaseRepository


class AnalysisJobRepository(BaseRepository[AnalysisJob]):
    model = AnalysisJob

    async def create_or_get_idempotent(
        self,
        asset_id: uuid.UUID,
        subject_id: uuid.UUID,
        pipeline_version: str,
        correlation_id: uuid.UUID | None = None,
    ) -> AnalysisJob:
        """Find existing job with same (asset, subject, pipeline_version), else create.

        The unique constraint uq_jobs_idempotency enforces this; we use a
        two-step approach to avoid exception-as-control-flow.
        """
        from sqlalchemy.exc import IntegrityError

        stmt = select(AnalysisJob).where(
            AnalysisJob.tenant_id == self.tenant_id,
            AnalysisJob.asset_id == asset_id,
            AnalysisJob.subject_id == subject_id,
            AnalysisJob.pipeline_version == pipeline_version,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        job = AnalysisJob(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            asset_id=asset_id,
            subject_id=subject_id,
            pipeline_version=pipeline_version,
            idempotency_key=f"{asset_id}:{subject_id}:{pipeline_version}",
            state="QUEUED",
            attempt=1,
            correlation_id=correlation_id,
        )
        self.session.add(job)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is None:
                raise
            return existing
        return job

    async def transition(self, job_id: uuid.UUID, from_state: str, to_state: str) -> AnalysisJob:
        job = await self.get(job_id)
        if job is None:
            from ..errors import NotFoundError

            raise NotFoundError("Job not found")
        if job.state != from_state:
            raise ConflictError(
                f"Cannot transition from {job.state} to {to_state}",
                code="invalid_state_transition",
            )
        from datetime import datetime

        if to_state == "RUNNING" and job.started_at is None:
            job.started_at = datetime.now(UTC)
        if to_state in ("SUCCEEDED", "FAILED", "INSUFFICIENT_DATA") and job.finished_at is None:
            job.finished_at = datetime.now(UTC)
        job.state = to_state
        job.version = (job.version or 1) + 1
        await self.session.flush()
        return job

    async def list_filtered(
        self,
        state: str | None = None,
        subject_id: uuid.UUID | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[AnalysisJob], str | None]:
        stmt = select(AnalysisJob).where(AnalysisJob.tenant_id == self.tenant_id)
        if state:
            stmt = stmt.where(AnalysisJob.state == state)
        if subject_id:
            stmt = stmt.where(AnalysisJob.subject_id == subject_id)
        return await self.paginate(stmt, cursor, limit)


class JobStageRepository(BaseRepository[JobStage]):
    model = JobStage

    async def start(
        self,
        job_id: uuid.UUID,
        name: str,
        attempt: int = 1,
        output_metadata: dict | None = None,
    ) -> JobStage:
        from datetime import datetime

        stage = JobStage(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            job_id=job_id,
            name=name,
            state="RUNNING",
            attempt=attempt,
            started_at=datetime.now(UTC),
            output_metadata=output_metadata or {},
        )
        self.session.add(stage)
        await self.session.flush()
        return stage

    async def complete(
        self,
        job_id: uuid.UUID,
        name: str,
        attempt: int,
        output_uri: str | None = None,
        output_metadata: dict | None = None,
    ) -> JobStage:
        from datetime import datetime

        from sqlalchemy import update

        result = await self.session.execute(
            update(JobStage)
            .where(
                JobStage.job_id == job_id,
                JobStage.name == name,
                JobStage.attempt == attempt,
            )
            .values(
                state="COMPLETED",
                completed_at=datetime.now(UTC),
                output_uri=output_uri,
                output_metadata=output_metadata or {},
            )
            .returning(JobStage)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError(f"Stage {name} attempt {attempt} not found for job {job_id}")
        return row

    async def fail(
        self,
        job_id: uuid.UUID,
        name: str,
        attempt: int,
        error: str,
    ) -> None:
        from datetime import datetime

        from sqlalchemy import update

        await self.session.execute(
            update(JobStage)
            .where(
                JobStage.job_id == job_id,
                JobStage.name == name,
                JobStage.attempt == attempt,
            )
            .values(
                state="FAILED",
                completed_at=datetime.now(UTC),
                error=error[:2000],
            )
        )

    async def list_for_job(self, job_id: uuid.UUID) -> list[JobStage]:
        stmt = (
            select(JobStage)
            .where(JobStage.job_id == job_id)
            .order_by(JobStage.started_at.asc().nulls_last())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
