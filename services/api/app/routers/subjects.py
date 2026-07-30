"""Subjects router."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas import (
    EnrollmentOut,
    EnrollmentRequest,
    SubjectCreate,
    SubjectOut,
    SubjectUpdate,
)
from ..security.rbac import Permission, require_permission
from ..services.subjects import SubjectService

router = APIRouter(prefix="/v1/subjects", tags=["subjects"])


@router.post("", response_model=SubjectOut)
async def create_subject(
    body: SubjectCreate,
    user: Annotated[object, Depends(require_permission(Permission.SUBJECT_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = SubjectService(db, user.tenant_id, user)
    s = await svc.create(body.external_id, body.display_name, body.consent_state)
    return SubjectOut(**await svc.get_with_stats(s.id))


@router.get("", response_model=list[SubjectOut])
async def list_subjects(
    user: Annotated[object, Depends(require_permission(Permission.SUBJECT_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = SubjectService(db, user.tenant_id, user)
    items, _ = await svc.list()
    return [SubjectOut(**await svc.get_with_stats(s.id)) for s in items]


@router.get("/{subject_id}", response_model=SubjectOut)
async def get_subject(
    subject_id: uuid.UUID,
    user: Annotated[object, Depends(require_permission(Permission.SUBJECT_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = SubjectService(db, user.tenant_id, user)
    return SubjectOut(**await svc.get_with_stats(subject_id))


@router.patch("/{subject_id}", response_model=SubjectOut)
async def update_subject(
    subject_id: uuid.UUID,
    body: SubjectUpdate,
    user: Annotated[object, Depends(require_permission(Permission.SUBJECT_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = SubjectService(db, user.tenant_id, user)
    await svc.update(
        subject_id,
        version=body.version,
        display_name=body.display_name,
        consent_state=body.consent_state,
        retention_policy=body.retention_policy,
    )
    return SubjectOut(**await svc.get_with_stats(subject_id))


@router.post("/{subject_id}/consent", response_model=EnrollmentOut)
async def record_enrollment(
    subject_id: uuid.UUID,
    body: EnrollmentRequest,
    user: Annotated[object, Depends(require_permission(Permission.SUBJECT_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = SubjectService(db, user.tenant_id, user)
    e = await svc.record_enrollment(
        subject_id, body.state, body.signed_by, body.evidence_uri
    )
    return EnrollmentOut(
        id=e.id,
        subject_id=e.subject_id,
        state=e.state,
        signed_by=e.signed_by,
        evidence_uri=e.evidence_uri,
        created_at=e.created_at,
    )
