"""Words / Phrases router (the cumulative database)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..db.models import User
from ..dependencies import S3Dep
from ..schemas import (
    PhraseSampleOut,
    PhraseTemplateDetail,
    PhraseTemplateSummary,
    SampleUrlsResponse,
    WordSummary,
)
from ..security.rbac import Permission, require_permission
from ..services.words import WordService

router = APIRouter(prefix="/v1/words", tags=["words"])


@router.get("", response_model=list[WordSummary])
async def list_words(
    user: Annotated[User, Depends(require_permission(Permission.BASELINE_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
    language: str | None = Query(default=None),
    subject_id: uuid.UUID | None = Query(default=None, alias="subjectId"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    svc = WordService(db, s3, user.tenant_id)
    items, _ = await svc.list_words(language, cursor, limit, subject_id)
    return [
        WordSummary(
            word=x["word"],
            language=x["language"],
            subject_id=x.get("subject_id"),
            n_templates=x["n_templates"],
            n_samples=x["n_samples"],
            has_mature_baseline=bool(x.get("is_mature")),
            last_decision_label=None,
            last_updated=x.get("last_updated"),
        )
        for x in items
    ]


@router.get("/{word}/templates", response_model=list[PhraseTemplateSummary])
async def list_templates(
    word: str,
    user: Annotated[User, Depends(require_permission(Permission.BASELINE_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
    language: str = Query(default="en"),
    subject_id: uuid.UUID | None = Query(default=None, alias="subjectId"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    svc = WordService(db, s3, user.tenant_id)
    return await svc.list_templates(word, language, cursor, limit, subject_id)


@router.get("/{word}/templates/{template_id}", response_model=PhraseTemplateDetail)
async def get_template_detail(
    word: str,
    template_id: uuid.UUID,
    user: Annotated[User, Depends(require_permission(Permission.BASELINE_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
):
    svc = WordService(db, s3, user.tenant_id)
    return await svc.get_template_detail(template_id, word)


@router.get("/{word}/samples", response_model=list[PhraseSampleOut])
async def list_samples_for_word(
    word: str,
    user: Annotated[User, Depends(require_permission(Permission.BASELINE_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
    language: str = Query(default="en"),
    template_id: uuid.UUID | None = Query(default=None, alias="templateId"),
    subject_id: uuid.UUID | None = Query(default=None, alias="subjectId"),
    limit: int = Query(default=200, ge=1, le=500),
):
    svc = WordService(db, s3, user.tenant_id)
    items = await svc.list_samples_for_word(word, language, template_id, limit, subject_id)
    return [PhraseSampleOut(**x) for x in items]


@router.get("/{word}/samples/{sample_id}/urls", response_model=SampleUrlsResponse)
async def get_sample_urls(
    word: str,
    sample_id: uuid.UUID,
    user: Annotated[User, Depends(require_permission(Permission.BASELINE_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
):
    svc = WordService(db, s3, user.tenant_id)
    return await svc.get_sample_urls(sample_id, word)
