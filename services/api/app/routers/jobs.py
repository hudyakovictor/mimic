"""Jobs router."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas import CreateJobRequest, JobOut, JobStageOut
from ..security.rbac import Permission, require_permission
from ..services.jobs import JobService

router = APIRouter(prefix="/v1/analysis-jobs", tags=["analysis"])


def _to_job_out(detail: dict) -> JobOut:
    j = detail["job"]
    decision = detail.get("decision")
    stages = detail.get("stages", [])
    return JobOut(
        id=j.id,
        asset_id=j.asset_id,
        subject_id=j.subject_id,
        pipeline_version=j.pipeline_version,
        state=j.state,
        attempt=j.attempt,
        last_error=j.last_error,
        created_at=j.created_at,
        started_at=j.started_at,
        finished_at=j.finished_at,
        decision=(
            {
                "id": decision.id,
                "job_id": decision.job_id,
                "label": decision.label,
                "risk_score": decision.risk_score,
                "quality_score": decision.quality_score,
                "model_version": decision.model_version,
                "model_checksum": decision.model_checksum,
                "evidence": decision.evidence or [],
                "phrase_instances": decision.phrase_instances or [],
                "created_at": decision.created_at,
            }
            if decision
            else None
        ),
        stages=[
            JobStageOut(
                id=s.id,
                name=s.name,
                state=s.state,
                started_at=s.started_at,
                completed_at=s.completed_at,
                error=s.error,
                output_uri=s.output_uri,
            )
            for s in stages
        ],
    )


@router.post("", response_model=JobOut, status_code=202)
async def create_job(
    body: CreateJobRequest,
    user: Annotated[object, Depends(require_permission(Permission.JOB_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = JobService(db, user.tenant_id, user)
    job = await svc.create(
        asset_id=body.asset_id,
        claimed_person_id=body.claimed_person_id,
        pipeline_version=body.pipeline_version,
        correlation_id=body.correlation_id,
    )
    detail = await svc.get_full(job.id)
    return _to_job_out(detail)


@router.get("", response_model=list[JobOut])
async def list_jobs(
    user: Annotated[object, Depends(require_permission(Permission.JOB_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    state: str | None = Query(default=None),
    subject_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
):
    svc = JobService(db, user.tenant_id, user)
    items, _ = await svc.list(state, subject_id, cursor, limit)
    return [
        _to_job_out(await svc.get_full(j.id)) for j in items
    ]


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    user: Annotated[object, Depends(require_permission(Permission.JOB_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = JobService(db, user.tenant_id, user)
    detail = await svc.get_full(job_id)
    return _to_job_out(detail)


@router.post("/{job_id}:cancel", response_model=JobOut)
async def cancel_job(
    job_id: uuid.UUID,
    user: Annotated[object, Depends(require_permission(Permission.JOB_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = JobService(db, user.tenant_id, user)
    await svc.cancel(job_id)
    return _to_job_out(await svc.get_full(job_id))


@router.post("/{job_id}:retry", response_model=JobOut)
async def retry_job(
    job_id: uuid.UUID,
    user: Annotated[object, Depends(require_permission(Permission.JOB_RETRY))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = JobService(db, user.tenant_id, user)
    await svc.retry(job_id)
    return _to_job_out(await svc.get_full(job_id))
