"""Decision, Review, Phrase repositories."""

from __future__ import annotations

import uuid

from sqlalchemy import desc, select

from ..db.models import Decision, PhraseSample, PhraseTemplate, Review
from .base import BaseRepository


class DecisionRepository(BaseRepository[Decision]):
    model = Decision

    async def create(
        self,
        job_id: uuid.UUID,
        label: str,
        risk_score: float,
        quality_score: float,
        model_version: str,
        model_checksum: str,
        evidence: list[dict],
        phrase_instances: list[dict],
    ) -> Decision:
        d = Decision(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            job_id=job_id,
            label=label,
            risk_score=risk_score,
            quality_score=quality_score,
            model_version=model_version,
            model_checksum=model_checksum,
            evidence=evidence,
            phrase_instances=phrase_instances,
        )
        self.session.add(d)
        await self.session.flush()
        return d

    async def list_for_job(self, job_id: uuid.UUID) -> list[Decision]:
        stmt = select(Decision).where(
            Decision.job_id == job_id,
            Decision.tenant_id == self.tenant_id,
        ).order_by(desc(Decision.created_at))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class ReviewRepository(BaseRepository[Review]):
    model = Review

    async def create(
        self,
        decision_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        verdict: str,
        reason: str,
        confidence: float | None = None,
    ) -> Review:
        r = Review(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            decision_id=decision_id,
            reviewer_id=reviewer_id,
            verdict=verdict,
            reason=reason,
            confidence=confidence,
        )
        self.session.add(r)
        await self.session.flush()
        return r

    async def list_for_decision(self, decision_id: uuid.UUID) -> list[Review]:
        stmt = select(Review).where(
            Review.decision_id == decision_id,
            Review.tenant_id == self.tenant_id,
        ).order_by(desc(Review.created_at))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_filtered(
        self,
        verdict: str | None = None,
        reviewer_id: uuid.UUID | None = None,
        decision_id: uuid.UUID | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Review], str | None]:
        stmt = select(Review).where(Review.tenant_id == self.tenant_id)
        if verdict:
            stmt = stmt.where(Review.verdict == verdict)
        if reviewer_id:
            stmt = stmt.where(Review.reviewer_id == reviewer_id)
        if decision_id:
            stmt = stmt.where(Review.decision_id == decision_id)
        return await self.paginate(stmt, cursor, limit)


class PhraseTemplateRepository(BaseRepository[PhraseTemplate]):
    model = PhraseTemplate

    async def get_latest_active(
        self, word: str, language: str, subject_id: uuid.UUID | None
    ) -> PhraseTemplate | None:
        stmt = (
            select(PhraseTemplate)
            .where(
                PhraseTemplate.tenant_id == self.tenant_id,
                PhraseTemplate.word == word,
                PhraseTemplate.language == language,
                PhraseTemplate.subject_id == subject_id,
                PhraseTemplate.state == "ACTIVE",
            )
            .order_by(desc(PhraseTemplate.version))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_word(
        self,
        word: str,
        language: str,
        cursor: str | None = None,
        limit: int = 50,
        subject_id: uuid.UUID | None = None,
    ) -> tuple[list[PhraseTemplate], str | None]:
        stmt = select(PhraseTemplate).where(
            PhraseTemplate.tenant_id == self.tenant_id,
            PhraseTemplate.word == word,
            PhraseTemplate.language == language,
        )
        if subject_id is not None:
            stmt = stmt.where(PhraseTemplate.subject_id == subject_id)
        return await self.paginate(stmt, cursor, limit)

    async def list_distinct_words(
        self,
        language: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
        subject_id: uuid.UUID | None = None,
    ) -> tuple[list[dict], str | None]:
        from sqlalchemy import Integer, cast, func

        stmt = (
            select(
                PhraseTemplate.word,
                PhraseTemplate.language,
                PhraseTemplate.subject_id,
                func.count(PhraseTemplate.id).label("n_templates"),
                func.max(PhraseTemplate.n_samples).label("n_samples"),
                func.max(PhraseTemplate.created_at).label("last_updated"),
                func.max(cast(PhraseTemplate.is_mature, Integer)).label("is_mature"),
            )
            .where(PhraseTemplate.tenant_id == self.tenant_id)
            .group_by(PhraseTemplate.word, PhraseTemplate.language, PhraseTemplate.subject_id)
        )
        if language:
            stmt = stmt.where(PhraseTemplate.language == language)
        if subject_id is not None:
            stmt = stmt.where(PhraseTemplate.subject_id == subject_id)
        # cursor by last_updated+word
        if cursor:
            from .base import decode_cursor

            c = decode_cursor(cursor)
            stmt = stmt.having(
                (func.max(PhraseTemplate.created_at) < c["created_at"])
                | ((func.max(PhraseTemplate.created_at) == c["created_at"]) & (PhraseTemplate.word < c["id"]))
            )
        stmt = stmt.order_by(func.max(PhraseTemplate.created_at).desc(), PhraseTemplate.word.desc()).limit(
            limit + 1
        )
        result = await self.session.execute(stmt)
        rows = list(result.all())
        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            from .base import encode_cursor

            last = rows[-1]
            next_cursor = encode_cursor(last.last_updated, last.word)
        return [
            {
                "word": r.word,
                "language": r.language,
                "subject_id": r.subject_id,
                "n_templates": int(r.n_templates or 0),
                "n_samples": int(r.n_samples or 0),
                "last_updated": r.last_updated,
                "is_mature": bool(r.is_mature),
            }
            for r in rows
        ], next_cursor

    async def create_version(
        self,
        word: str,
        language: str,
        subject_id: uuid.UUID | None,
        version: int,
        parent_id: uuid.UUID | None,
        n_samples: int,
        mean_curve_object_key: str,
        cov_diag_object_key: str,
        regional_stats: dict,
        model_version: str,
        is_mature: bool,
        template_id: uuid.UUID | None = None,
    ) -> PhraseTemplate:
        t = PhraseTemplate(
            id=template_id or uuid.uuid4(),
            tenant_id=self.tenant_id,
            subject_id=subject_id,
            word=word,
            language=language,
            version=version,
            parent_id=parent_id,
            n_samples=n_samples,
            mean_curve_object_key=mean_curve_object_key,
            cov_diag_object_key=cov_diag_object_key,
            regional_stats=regional_stats,
            model_version=model_version,
            is_mature=is_mature,
            state="ACTIVE",
        )
        self.session.add(t)
        await self.session.flush()
        return t

    async def get(self, template_id: uuid.UUID) -> PhraseTemplate | None:
        result = await self.session.execute(
            select(PhraseTemplate).where(
                PhraseTemplate.id == template_id,
                PhraseTemplate.tenant_id == self.tenant_id,
            )
        )
        return result.scalar_one_or_none()


class PhraseSampleRepository(BaseRepository[PhraseSample]):
    model = PhraseSample

    async def create(
        self,
        template_id: uuid.UUID,
        decision_id: uuid.UUID,
        review_id: uuid.UUID,
        word: str,
        language: str,
        start_ms: int,
        end_ms: int,
        video_clip_object_key: str,
        landmarks_object_key: str,
        audio_clip_object_key: str | None,
        confidence: float,
        n_frames: int,
        mean_dtw_to_template: float | None,
        sample_id: uuid.UUID | None = None,
    ) -> PhraseSample:
        s = PhraseSample(
            id=sample_id or uuid.uuid4(),
            tenant_id=self.tenant_id,
            template_id=template_id,
            decision_id=decision_id,
            review_id=review_id,
            word=word,
            language=language,
            start_ms=start_ms,
            end_ms=end_ms,
            video_clip_object_key=video_clip_object_key,
            landmarks_object_key=landmarks_object_key,
            audio_clip_object_key=audio_clip_object_key,
            confidence=confidence,
            n_frames=n_frames,
            mean_dtw_to_template=mean_dtw_to_template,
        )
        self.session.add(s)
        await self.session.flush()
        return s

    async def list_for_template(
        self, template_id: uuid.UUID, cursor: str | None = None, limit: int = 50
    ) -> tuple[list[PhraseSample], str | None]:
        stmt = select(PhraseSample).where(
            PhraseSample.tenant_id == self.tenant_id,
            PhraseSample.template_id == template_id,
        )
        return await self.paginate(stmt, cursor, limit)

    async def get(self, sample_id: uuid.UUID) -> PhraseSample | None:
        result = await self.session.execute(
            select(PhraseSample).where(
                PhraseSample.id == sample_id,
                PhraseSample.tenant_id == self.tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_word_across_versions(
        self,
        word: str,
        language: str,
        limit: int = 200,
        subject_id: uuid.UUID | None = None,
    ) -> list[PhraseSample]:
        stmt = select(PhraseSample)
        if subject_id is not None:
            stmt = stmt.join(PhraseTemplate, PhraseTemplate.id == PhraseSample.template_id)
        stmt = (
            stmt.where(
                PhraseSample.tenant_id == self.tenant_id,
                PhraseSample.word == word,
                PhraseSample.language == language,
                *((PhraseTemplate.subject_id == subject_id,) if subject_id is not None else ()),
            )
            .order_by(desc(PhraseSample.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
