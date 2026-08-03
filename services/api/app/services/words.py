"""Words / Phrases query service.

Exposes the accumulated phrase database to the admin UI.
"""

from __future__ import annotations

import io
import uuid

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import AnalysisJob, Asset, Decision, PhraseSample
from ..errors import NotFoundError
from ..repositories.decisions import PhraseSampleRepository, PhraseTemplateRepository
from ..storage import BUCKET_CLIPS, BUCKET_DERIVED, BUCKET_VIDEOS
from ..storage.s3_client import S3Client


class WordService:
    def __init__(self, session: AsyncSession, s3: S3Client, tenant_id: uuid.UUID):
        self.session = session
        self.s3 = s3
        self.tenant_id = tenant_id
        self.templates = PhraseTemplateRepository(session, tenant_id)
        self.samples = PhraseSampleRepository(session, tenant_id)

    async def list_words(
        self,
        language: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
        subject_id: uuid.UUID | None = None,
    ) -> tuple[list[dict], str | None]:
        return await self.templates.list_distinct_words(language, cursor, limit, subject_id)

    async def list_templates(
        self,
        word: str,
        language: str,
        cursor: str | None = None,
        limit: int = 50,
        subject_id: uuid.UUID | None = None,
    ) -> list[dict]:
        items, _ = await self.templates.list_for_word(word, language, cursor, limit, subject_id)
        return [
            {
                "id": str(t.id),
                "subject_id": str(t.subject_id) if t.subject_id else None,
                "word": t.word,
                "language": t.language,
                "version": t.version,
                "n_samples": t.n_samples,
                "is_mature": t.is_mature,
                "state": t.state,
                "model_version": t.model_version,
                "created_at": t.created_at,
            }
            for t in items
        ]

    async def get_template_detail(self, template_id: uuid.UUID, expected_word: str | None = None) -> dict:
        t = await self.templates.get(template_id)
        if t is None or (expected_word is not None and t.word != expected_word):
            raise NotFoundError("Template not found")
        # Load mean curve from S3
        try:
            buf = await self.s3.get_object(BUCKET_DERIVED, t.mean_curve_object_key)
            arr = np.load(io.BytesIO(buf))
            # Downsample to 30 points for response
            if arr.shape[0] > 30:
                idx = np.linspace(0, arr.shape[0] - 1, 30).astype(int)
                mean_curve = arr[idx].tolist()
            else:
                mean_curve = arr.tolist()
        except Exception:
            mean_curve = []
        # Sample IDs
        samples, _ = await self.samples.list_for_template(template_id, limit=200)
        return {
            "id": str(t.id),
            "subject_id": str(t.subject_id) if t.subject_id else None,
            "word": t.word,
            "language": t.language,
            "version": t.version,
            "n_samples": t.n_samples,
            "is_mature": t.is_mature,
            "state": t.state,
            "model_version": t.model_version,
            "created_at": t.created_at,
            "parent_id": str(t.parent_id) if t.parent_id else None,
            "mean_curve": mean_curve,
            "regional_stats": t.regional_stats or {},
            "sample_ids": [str(s.id) for s in samples],
        }

    async def list_samples(
        self, template_id: uuid.UUID, cursor: str | None = None, limit: int = 50
    ) -> list[dict]:
        items, _ = await self.samples.list_for_template(template_id, cursor, limit)
        return [self._sample_to_dict(s) for s in items]

    async def get_sample_urls(self, sample_id: uuid.UUID, expected_word: str | None = None) -> dict:
        s = await self.samples.get(sample_id)
        if s is None or (expected_word is not None and s.word != expected_word):
            raise NotFoundError("Sample not found")
        video_url = ""
        video_in_point_ms = 0
        video_out_point_ms = max(1, s.end_ms - s.start_ms)
        if s.video_clip_object_key:
            video_url = await self.s3.generate_presigned_get(BUCKET_CLIPS, s.video_clip_object_key)
        else:
            # 80/20 retention: the analysis asset is already a selected short
            # canonical clip. Reuse it instead of duplicating one MP4 per word.
            from sqlalchemy import select

            asset_stmt = (
                select(Asset)
                .join(AnalysisJob, AnalysisJob.asset_id == Asset.id)
                .join(Decision, Decision.job_id == AnalysisJob.id)
                .where(
                    Decision.id == s.decision_id,
                    Decision.tenant_id == self.tenant_id,
                    Asset.tenant_id == self.tenant_id,
                    Asset.state == "READY",
                )
                .limit(1)
            )
            asset = (await self.session.execute(asset_stmt)).scalar_one_or_none()
            if asset is not None:
                video_url = await self.s3.generate_presigned_get(BUCKET_VIDEOS, asset.object_key)
                video_in_point_ms = s.start_ms
                video_out_point_ms = s.end_ms
        landmarks_url = ""
        if s.landmarks_object_key:
            landmarks_url = await self.s3.generate_presigned_get(BUCKET_CLIPS, s.landmarks_object_key)
        audio_url = None
        if s.audio_clip_object_key:
            audio_url = await self.s3.generate_presigned_get(BUCKET_CLIPS, s.audio_clip_object_key)
        return {
            "video_clip_url": video_url,
            "landmarks_url": landmarks_url,
            "audio_clip_url": audio_url,
            "video_in_point_ms": video_in_point_ms,
            "video_out_point_ms": video_out_point_ms,
            "expires_in": 300,
        }

    async def list_samples_for_word(
        self,
        word: str,
        language: str,
        template_id: uuid.UUID | None = None,
        limit: int = 200,
        subject_id: uuid.UUID | None = None,
    ) -> list[dict]:
        if template_id is not None:
            items, _ = await self.samples.list_for_template(template_id, limit=limit)
            return [self._sample_to_dict(s) for s in items]
        return [
            self._sample_to_dict(s)
            for s in await self.samples.list_for_word_across_versions(word, language, limit, subject_id)
        ]

    def _sample_to_dict(self, s: PhraseSample) -> dict:
        return {
            "id": str(s.id),
            "template_id": str(s.template_id),
            "decision_id": str(s.decision_id),
            "review_id": str(s.review_id),
            "word": s.word,
            "language": s.language,
            "start_ms": s.start_ms,
            "end_ms": s.end_ms,
            "confidence": s.confidence,
            "n_frames": s.n_frames,
            "mean_dtw_to_template": s.mean_dtw_to_template,
            "created_at": s.created_at,
        }
