"""Subject and enrollment repositories."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from ..db.models import Enrollment, Subject
from ..errors import ConflictError, NotFoundError
from .base import BaseRepository


class SubjectRepository(BaseRepository[Subject]):
    model = Subject

    async def create(self, external_id: str, display_name: str, consent_state: str = "PENDING") -> Subject:
        s = Subject(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            external_id=external_id,
            display_name=display_name,
            consent_state=consent_state,
            retention_policy={},
        )
        self.session.add(s)
        await self.session.flush()
        return s

    async def get_by_external_id(self, external_id: str) -> Subject | None:
        stmt = select(Subject).where(
            Subject.tenant_id == self.tenant_id,
            Subject.external_id == external_id,
            Subject.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_optimistic(
        self,
        subject_id: uuid.UUID,
        version_expected: int,
        **fields,
    ) -> Subject:
        from sqlalchemy import update

        # Use SQL-level WHERE version = :v AND tenant_id = :t
        new_version = version_expected + 1
        values = dict(fields)
        values["version"] = new_version
        result = await self.session.execute(
            update(Subject)
            .where(
                Subject.id == subject_id,
                Subject.version == version_expected,
                Subject.tenant_id == self.tenant_id,
            )
            .values(**values)
        )
        if result.rowcount == 0:
            existing = await self.get(subject_id)
            if existing is None:
                raise NotFoundError("Subject not found")
            raise ConflictError(
                f"Version mismatch: expected {version_expected}, got {existing.version}",
                code="version_conflict",
            )
        await self.session.flush()
        return await self.get(subject_id)


class EnrollmentRepository(BaseRepository[Enrollment]):
    model = Enrollment

    async def create(
        self,
        subject_id: uuid.UUID,
        state: str,
        signed_by: str | None = None,
        evidence_uri: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> Enrollment:
        e = Enrollment(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            subject_id=subject_id,
            state=state,
            signed_by=signed_by,
            evidence_uri=evidence_uri,
            ip=ip,
            user_agent=user_agent,
        )
        self.session.add(e)
        await self.session.flush()
        return e
