"""Subject service."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import AnalysisJob, Enrollment, PhraseTemplate, Subject, User
from ..errors import NotFoundError
from ..events.outbox import OutboxRepository
from ..repositories.subjects import EnrollmentRepository, SubjectRepository


class SubjectService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID, actor: User):
        self.session = session
        self.tenant_id = tenant_id
        self.actor = actor
        self.repo = SubjectRepository(session, tenant_id)
        self.enrollments = EnrollmentRepository(session, tenant_id)
        self.outbox = OutboxRepository(session)

    async def create(
        self, external_id: str, display_name: str, consent_state: str = "PENDING"
    ) -> Subject:
        existing = await self.repo.get_by_external_id(external_id)
        if existing is not None:
            return existing
        s = await self.repo.create(external_id, display_name, consent_state)
        await self.session.flush()
        await self.outbox.create(
            event_name="subject.created.v1",
            payload={"subject_id": str(s.id), "external_id": external_id},
            tenant_id=self.tenant_id,
        )
        # Explicit commit so subsequent requests see the new subject.
        await self.session.commit()
        return s

    async def get(self, subject_id: uuid.UUID) -> Subject:
        s = await self.repo.get(subject_id)
        if s is None or s.deleted_at is not None:
            raise NotFoundError("Subject not found")
        return s

    async def get_with_stats(self, subject_id: uuid.UUID) -> dict:
        s = await self.get(subject_id)
        n_jobs = await self.session.scalar(
            select(func.count(AnalysisJob.id)).where(AnalysisJob.subject_id == subject_id)
        )
        n_baselines = await self.session.scalar(
            select(func.count(PhraseTemplate.id)).where(
                PhraseTemplate.subject_id == subject_id,
                PhraseTemplate.state == "ACTIVE",
            )
        )
        last = await self.session.scalar(
            select(func.max(AnalysisJob.created_at)).where(AnalysisJob.subject_id == subject_id)
        )
        return {
            "id": s.id,
            "external_id": s.external_id,
            "display_name": s.display_name,
            "consent_state": s.consent_state,
            "retention_policy": s.retention_policy or {},
            "n_jobs": int(n_jobs or 0),
            "n_baselines": int(n_baselines or 0),
            "last_analyzed_at": last,
            "created_at": s.created_at,
            "version": s.version,
        }

    async def list(
        self, cursor: str | None = None, limit: int = 50
    ) -> tuple[list[Subject], str | None]:
        from sqlalchemy import select

        stmt = select(Subject).where(
            Subject.tenant_id == self.tenant_id, Subject.deleted_at.is_(None)
        )
        return await self.repo.paginate(stmt, cursor, limit)

    async def update(
        self,
        subject_id: uuid.UUID,
        version: int,
        display_name: str | None = None,
        consent_state: str | None = None,
        retention_policy: dict | None = None,
    ) -> Subject:
        fields = {}
        if display_name is not None:
            fields["display_name"] = display_name
        if consent_state is not None:
            fields["consent_state"] = consent_state
        if retention_policy is not None:
            fields["retention_policy"] = retention_policy
        if not fields:
            return await self.get(subject_id)
        s = await self.repo.update_optimistic(subject_id, version, **fields)
        await self.session.commit()  # ensure commit before return
        if consent_state is not None:
            await self.outbox.create(
                event_name="subject.consent.v1",
                payload={"subject_id": str(s.id), "state": consent_state},
                tenant_id=self.tenant_id,
            )
        return s

    async def record_enrollment(
        self,
        subject_id: uuid.UUID,
        state: str,
        signed_by: str | None = None,
        evidence_uri: str | None = None,
    ) -> Enrollment:
        # Verify subject belongs to this tenant (defence in depth)
        s = await self.get(subject_id)
        if s is None:
            from ..errors import NotFoundError

            raise NotFoundError("Subject not found")
        e = await self.enrollments.create(
            subject_id=subject_id, state=state, signed_by=signed_by, evidence_uri=evidence_uri
        )
        await self.session.commit()
        # Update consent
        s = await self.repo.get(subject_id)
        if s is not None and s.consent_state != state:
            s.consent_state = state
            s.version = (s.version or 1) + 1
            await self.session.flush()
        return e
