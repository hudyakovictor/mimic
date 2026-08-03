"""Reviews router."""

from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..db.models import User
from ..dependencies import S3Dep
from ..observability import get_logger
from ..schemas import CreateReviewRequest, ReviewOut, ReviewVerdict
from ..security.rbac import Permission, require_permission
from ..services.reviews import BaselineAggregator, ReviewService

log = get_logger(__name__)
router = APIRouter(prefix="/v1/reviews", tags=["reviews"])


@router.post("", response_model=ReviewOut, status_code=201)
async def create_review(
    body: CreateReviewRequest,
    user: Annotated[User, Depends(require_permission(Permission.REVIEW_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: S3Dep,
):
    svc = ReviewService(db, user.tenant_id, user)
    r = await svc.create(body.decision_id, body.verdict, body.reason, body.confidence)
    if r.verdict == "CONFIRMED_GENUINE":
        try:
            async with db.begin_nested():
                await BaselineAggregator(db, s3, user.tenant_id).on_review_confirmed_genuine(r.id)
        except Exception as exc:
            # The append-only review remains authoritative; the outbox event can
            # rebuild a failed baseline without asking the reviewer to resubmit.
            log.exception("baseline.inline_aggregation_failed", review_id=str(r.id), error=str(exc))
    return ReviewOut(
        id=r.id,
        decision_id=r.decision_id,
        reviewer_id=r.reviewer_id,
        reviewer_name=user.display_name,
        verdict=cast(ReviewVerdict, r.verdict),
        reason=r.reason,
        confidence=r.confidence,
        created_at=r.created_at,
    )


@router.get("", response_model=list[ReviewOut])
async def list_reviews(
    user: Annotated[User, Depends(require_permission(Permission.DECISION_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    verdict: str | None = Query(default=None),
    reviewer_id: uuid.UUID | None = Query(default=None),
    decision_id: uuid.UUID | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    svc = ReviewService(db, user.tenant_id, user)
    items, _ = await svc.list(verdict, reviewer_id, decision_id, cursor, limit)
    return [
        ReviewOut(
            id=r.id,
            decision_id=r.decision_id,
            reviewer_id=r.reviewer_id,
            reviewer_name="",
            verdict=cast(ReviewVerdict, r.verdict),
            reason=r.reason,
            confidence=r.confidence,
            created_at=r.created_at,
        )
        for r in items
    ]


@router.get("/{review_id}", response_model=ReviewOut)
async def get_review(
    review_id: uuid.UUID,
    user: Annotated[User, Depends(require_permission(Permission.DECISION_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = ReviewService(db, user.tenant_id, user)
    r = await svc.get(review_id)
    return ReviewOut(
        id=r.id,
        decision_id=r.decision_id,
        reviewer_id=r.reviewer_id,
        reviewer_name="",
        verdict=cast(ReviewVerdict, r.verdict),
        reason=r.reason,
        confidence=r.confidence,
        created_at=r.created_at,
    )
