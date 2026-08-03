"""Per-actor async session + repository helpers.

The worker shares the API package's ORM/models; we just re-export the
helpers we need so the worker code reads naturally.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_sessionmaker
from app.db.models import AnalysisJob, Asset, JobStage
from app.settings import get_settings
from app.storage import S3Client, get_s3_client

# These imports use the API package's `app` namespace. The worker
# shares the same package via PYTHONPATH=services/api (see Makefile).
_ = (AnalysisJob, Asset, JobStage)

_s3: S3Client | None = None


def get_s3() -> S3Client:
    global _s3
    if _s3 is None:
        _s3 = get_s3_client(get_settings())
    return _s3


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    sm = get_sessionmaker()
    async with sm() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def load_job(session: AsyncSession, job_id: uuid.UUID) -> AnalysisJob:
    j = await session.get(AnalysisJob, job_id)
    if j is None:
        raise ValueError(f"Job {job_id} not found")
    return j


async def load_asset(session: AsyncSession, asset_id: uuid.UUID) -> Asset:
    a = await session.get(Asset, asset_id)
    if a is None:
        raise ValueError(f"Asset {asset_id} not found")
    return a


async def start_stage(
    session: AsyncSession, job_id: uuid.UUID, name: str, attempt: int | None = None
) -> JobStage:
    job = await load_job(session, job_id)
    actual_attempt = int(attempt if attempt is not None else job.attempt)
    stage = JobStage(
        id=uuid.uuid4(),
        tenant_id=job.tenant_id,
        job_id=job_id,
        name=name,
        state="RUNNING",
        attempt=actual_attempt,
        started_at=datetime.now(UTC),
    )
    session.add(stage)
    await session.flush()
    return stage


async def complete_stage(
    session: AsyncSession,
    job_id: uuid.UUID,
    name: str,
    attempt: int,
    output_uri: str | None = None,
    output_metadata: dict | None = None,
) -> None:
    await session.execute(
        update(JobStage)
        .where(JobStage.job_id == job_id, JobStage.name == name, JobStage.attempt == attempt)
        .values(
            state="COMPLETED",
            completed_at=datetime.now(UTC),
            output_uri=output_uri,
            output_metadata=output_metadata or {},
        )
    )


async def fail_stage(
    session: AsyncSession,
    job_id: uuid.UUID,
    name: str,
    attempt: int,
    error: str,
) -> None:
    await session.execute(
        update(JobStage)
        .where(JobStage.job_id == job_id, JobStage.name == name, JobStage.attempt == attempt)
        .values(
            state="FAILED",
            completed_at=datetime.now(UTC),
            error=error[:2000],
        )
    )
