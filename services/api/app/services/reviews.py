"""Review service + Baseline aggregator (called on review.created.v1)."""
from __future__ import annotations

import io
import json
import uuid

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Decision, PhraseTemplate, Review, User
from ..errors import NotFoundError, ValidationFailedError
from ..events.outbox import OutboxRepository
from ..observability import PHRASE_TEMPLATES_TOTAL, get_logger
from ..repositories.decisions import (
    DecisionRepository,
    PhraseSampleRepository,
    PhraseTemplateRepository,
    ReviewRepository,
)
from ..settings import get_settings
from ..storage import BUCKET_CLIPS, BUCKET_DERIVED
from ..storage.keys import (
    phrase_landmarks_key,
    template_cov_key,
    template_curve_key,
)
from ..storage.s3_client import S3Client

log = get_logger(__name__)


class ReviewService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID, actor: User):
        self.session = session
        self.tenant_id = tenant_id
        self.actor = actor
        self.reviews = ReviewRepository(session, tenant_id)
        self.decisions = DecisionRepository(session, tenant_id)
        self.outbox = OutboxRepository(session)

    async def create(
        self,
        decision_id: uuid.UUID,
        verdict: str,
        reason: str,
        confidence: float | None = None,
    ) -> Review:
        if verdict not in ("CONFIRMED_GENUINE", "CONFIRMED_SUSPICIOUS", "UNDECIDABLE"):
            raise ValidationFailedError(f"Invalid verdict: {verdict}")
        if len(reason) < 10:
            raise ValidationFailedError("Reason must be at least 10 characters")
        # Verify decision exists in tenant
        decision = await self.decisions.get(decision_id)
        if decision is None:
            raise NotFoundError("Decision not found")
        r = await self.reviews.create(
            decision_id=decision_id,
            reviewer_id=self.actor.id,
            verdict=verdict,
            reason=reason,
            confidence=confidence,
        )
        await self.outbox.create(
            event_name="review.created.v1",
            payload={
                "review_id": str(r.id),
                "decision_id": str(decision_id),
                "verdict": verdict,
                "reviewer_id": str(self.actor.id),
            },
            tenant_id=self.tenant_id,
        )
        log.info(
            "review.create",
            review_id=str(r.id),
            decision_id=str(decision_id),
            verdict=verdict,
            reviewer_id=str(self.actor.id),
        )
        return r

    async def list(
        self,
        verdict: str | None = None,
        reviewer_id: uuid.UUID | None = None,
        decision_id: uuid.UUID | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Review], str | None]:
        return await self.reviews.list_filtered(verdict, reviewer_id, decision_id, cursor, limit)

    async def get(self, review_id: uuid.UUID) -> Review:
        r = await self.reviews.get(review_id)
        if r is None:
            raise NotFoundError("Review not found")
        return r


class BaselineAggregator:
    """Consumes review.created.v1 events and updates PhraseTemplate atomically.

    Implementation note: invoked as part of the API write path via an outbox
    consumer, but the algorithm is here for clarity and testability.
    """

    def __init__(
        self,
        session: AsyncSession,
        s3: S3Client,
        tenant_id: uuid.UUID,
    ):
        self.session = session
        self.s3 = s3
        self.tenant_id = tenant_id
        self.templates = PhraseTemplateRepository(session, tenant_id)
        self.samples = PhraseSampleRepository(session, tenant_id)

    async def on_review_confirmed_genuine(
        self, review_id: uuid.UUID, s3: S3Client | None = None
    ) -> PhraseTemplate | None:
        """Update PhraseTemplate for every PhraseInstance in the decision."""
        s3 = s3 or self.s3
        settings = get_settings()

        review = await self.session.get(Review, review_id)
        if review is None or review.verdict != "CONFIRMED_GENUINE":
            return None
        decision = await self.session.get(Decision, review.decision_id)
        if decision is None:
            return None
        # Load landmarks
        from ..db.models import AnalysisJob, LandmarkSequence

        job = await self.session.get(AnalysisJob, decision.job_id)
        if job is None:
            return None
        lms = await self.session.execute(
            select(LandmarkSequence).where(LandmarkSequence.job_id == decision.job_id)
        )
        lm = lms.scalar_one_or_none()
        if lm is None:
            log.warning("baseline.no_landmarks", job_id=str(decision.job_id))
            return None
        landmarks_bytes = await s3.get_object(BUCKET_DERIVED, lm.object_key)
        landmarks = self._parse_npz(landmarks_bytes)
        if landmarks is None:
            return None
        # Update templates per word
        phrase_instances = decision.phrase_instances or []
        new_templates: list[PhraseTemplate] = []
        for inst in phrase_instances:
            word = inst.get("word", "").lower()
            if not word:
                continue
            language = inst.get("language", "en")
            tpl = await self._update_template_for_word(
                word=word,
                language=language,
                subject_id=job.subject_id,
                start_ms=int(inst.get("start_ms", 0)),
                end_ms=int(inst.get("end_ms", 0)),
                landmarks=landmarks,
                review_id=review_id,
                decision_id=decision.id,
                settings=settings,
                s3=s3,
            )
            if tpl is not None:
                new_templates.append(tpl)
        PHRASE_TEMPLATES_TOTAL.set(await self._count_active_templates())
        return new_templates[-1] if new_templates else None

    async def _count_active_templates(self) -> int:
        from sqlalchemy import func

        return int(
            await self.session.scalar(
                select(func.count(PhraseTemplate.id)).where(
                    PhraseTemplate.tenant_id == self.tenant_id,
                    PhraseTemplate.state == "ACTIVE",
                )
            )
            or 0
        )

    async def _update_template_for_word(
        self,
        *,
        word: str,
        language: str,
        subject_id: uuid.UUID | None,
        start_ms: int,
        end_ms: int,
        landmarks: np.ndarray,
        review_id: uuid.UUID,
        decision_id: uuid.UUID,
        settings,
        s3: S3Client,
    ) -> PhraseTemplate | None:
        # Slice landmarks by time
        sliced = self._slice_landmarks_by_time(landmarks, start_ms, end_ms)
        if sliced is None or len(sliced) < 10:
            return None
        n_frames = len(sliced)
        # Extract features (regional)
        features = self._extract_features(sliced)
        # Find existing active template
        latest = await self.templates.get_latest_active(word, language, subject_id)
        all_samples: list[np.ndarray] = []
        all_features: list[np.ndarray] = []
        if latest is not None:
            try:
                old_curve = np.load(io.BytesIO(await s3.get_object(BUCKET_DERIVED, latest.mean_curve_object_key)))
                all_samples.append(old_curve)
                all_features.append(np.array(list(latest.regional_stats.values())))
            except Exception:
                pass
        all_samples.append(sliced)
        all_features.append(features)
        # Resample all to fixed length 30 frames
        target_len = 30
        resampled = [self._resample(s, target_len) for s in all_samples]
        # Cap at MAX_N
        max_n = settings.phrase_template_max_samples
        if len(resampled) > max_n:
            resampled = resampled[-max_n:]
        new_n = len(resampled)
        # Build mean curve
        stack = np.stack(resampled, axis=0)  # (N, T, D)
        if stack.shape[2] == 0:
            return None
        mean_curve = stack.mean(axis=0)
        cov_diag = stack.var(axis=0)
        # Regional stats from features
        f_stack = np.stack(all_features, axis=0)
        regional_stats = {
            "mouth_open_mu": float(f_stack[:, 0].mean()),
            "mouth_open_sigma": float(f_stack[:, 0].std() + 1e-6),
            "mouth_ratio_mu": float(f_stack[:, 2].mean()),
            "mouth_ratio_sigma": float(f_stack[:, 2].std() + 1e-6),
            "lip_asym_mu": float(f_stack[:, 3].mean()),
            "lip_asym_sigma": float(f_stack[:, 3].std() + 1e-6),
            "jaw_open_mu": float(f_stack[:, 4].mean()),
            "jaw_open_sigma": float(f_stack[:, 4].std() + 1e-6),
        }
        # Persist artifacts
        new_id = uuid.uuid4()
        curve_key = template_curve_key(self.tenant_id, new_id)
        cov_key = template_cov_key(self.tenant_id, new_id)
        curve_buf = io.BytesIO()
        np.save(curve_buf, mean_curve)
        cov_buf = io.BytesIO()
        np.save(cov_buf, cov_diag)
        await s3.put_object(BUCKET_DERIVED, curve_key, curve_buf.getvalue(), "application/octet-stream")
        await s3.put_object(BUCKET_DERIVED, cov_key, cov_buf.getvalue(), "application/octet-stream")
        # PhraseSample
        sample_key = phrase_landmarks_key(self.tenant_id, new_id)
        await s3.put_object(
            BUCKET_CLIPS, sample_key, sliced.astype(np.float32).tobytes(), "application/octet-stream"
        )
        sample = await self.samples.create(
            template_id=new_id,  # will be overwritten
            decision_id=decision_id,
            review_id=review_id,
            word=word,
            language=language,
            start_ms=start_ms,
            end_ms=end_ms,
            video_clip_object_key="",
            landmarks_object_key=sample_key,
            audio_clip_object_key=None,
            confidence=0.0,
            n_frames=n_frames,
            mean_dtw_to_template=None,
        )
        # PhraseTemplate
        is_mature = new_n >= settings.phrase_baseline_mature_samples
        tpl = await self.templates.create_version(
            word=word,
            language=language,
            subject_id=subject_id,
            version=(latest.version + 1) if latest else 1,
            parent_id=latest.id if latest else None,
            n_samples=new_n,
            mean_curve_object_key=curve_key,
            cov_diag_object_key=cov_key,
            regional_stats=regional_stats,
            model_version="statistical-v1",
            is_mature=is_mature,
        )
        # Fix sample template_id to real tpl.id
        sample.template_id = tpl.id
        await self.session.flush()
        return tpl

    @staticmethod
    def _parse_npz(blob: bytes) -> np.ndarray | None:
        """Parse landmarks.npz written by worker. Format:
        header (json string terminated by newline),
        then binary float32 array of shape (T, 478, 3) for mediapipe,
        or (T, 33) for normalized.
        """
        try:
            # Find newline
            nl = blob.find(b"\n")
            if nl < 0:
                return None
            header = json.loads(blob[:nl].decode())
            shape = tuple(header["shape"])
            dtype = np.dtype(header.get("dtype", "float32"))
            arr = np.frombuffer(blob[nl + 1 :], dtype=dtype).reshape(shape)
            return arr
        except Exception as e:
            log.warning("baseline.parse_npz_failed", error=str(e))
            return None

    @staticmethod
    def _slice_landmarks_by_time(
        landmarks: np.ndarray, start_ms: int, end_ms: int
    ) -> np.ndarray | None:
        """Slice by frame index. landmarks is (T, D) or (T, N, 3).

        For now we assume uniform 30 fps and slicing by approximate index.
        Caller can later provide a time-indexed array.
        """
        if landmarks.ndim == 2:
            T = landmarks.shape[0]
            i0 = int(start_ms / 1000 * 30)
            i1 = int(end_ms / 1000 * 30)
            i0 = max(0, min(T, i0))
            i1 = max(i0 + 1, min(T, i1))
            return landmarks[i0:i1]
        elif landmarks.ndim == 3:
            T = landmarks.shape[0]
            i0 = int(start_ms / 1000 * 30)
            i1 = int(end_ms / 1000 * 30)
            i0 = max(0, min(T, i0))
            i1 = max(i0 + 1, min(T, i1))
            return landmarks[i0:i1].reshape(i1 - i0, -1)
        return None

    @staticmethod
    def _resample(arr: np.ndarray, target_len: int) -> np.ndarray:
        """Linear interpolation resample to fixed length."""
        from scipy.interpolate import interp1d

        T = arr.shape[0]
        if T == target_len:
            return arr
        x_old = np.linspace(0, 1, T)
        x_new = np.linspace(0, 1, target_len)
        if arr.ndim == 1:
            return np.interp(x_new, x_old, arr)
        out = np.zeros((target_len, arr.shape[1]))
        for d in range(arr.shape[1]):
            f = interp1d(x_old, arr[:, d], kind="linear")
            out[:, d] = f(x_new)
        return out

    @staticmethod
    def _extract_features(arr: np.ndarray) -> np.ndarray:
        """Extract 8 motion features from a landmarks slice.
        arr is (T, D). We use 33-dim normalized features if available,
        else approximate from raw landmarks.
        """
        if arr.shape[1] < 33:
            # Pad with zeros
            arr = np.pad(arr, ((0, 0), (0, 33 - arr.shape[1])))
        # Indexes into 33-dim vector (motion-v1)
        # 0: mouth_outer_l_x, 1: _y
        # 6: mouth_outer_r_x, 7: _y
        # 9: mouth_inner_top_y
        # 15: mouth_inner_bottom_y
        # 21: chin_y
        # 24: jaw_l_x, 25: _y
        # 27: jaw_r_x, 28: _y
        # 31: cheek_upper_l_y
        # 37: cheek_upper_r_y
        # (we only have 33 dims; cheek_upper_r is at 36 in 11-point × 3 + offset, but for simplicity)
        if arr.shape[1] >= 33:
            v = arr
        else:
            v = np.zeros((arr.shape[0], 33))
            v[:, : arr.shape[1]] = arr
        # 0: mouth_open
        mouth_open = np.abs(v[:, 15] - v[:, 9])
        # 1: mouth_width
        mouth_width = np.abs(v[:, 6] - v[:, 0])
        # 2: mouth_ratio
        mouth_ratio = mouth_open / (mouth_width + 1e-6)
        # 3: lip_asym
        lip_asym = v[:, 1] - v[:, 7]
        # 4: jaw_open
        jaw_open = np.abs(v[:, 25] - v[:, 28])
        # 5: cheek_raise (avg)
        cheek_raise = (v[:, 31] + (v[:, 36] if v.shape[1] > 36 else v[:, 31])) / 2
        # 6: d_mouth_open
        d_mouth_open = np.gradient(mouth_open) if arr.shape[0] > 1 else np.zeros_like(mouth_open)
        # 7: dd_mouth_open
        dd_mouth_open = np.gradient(d_mouth_open) if arr.shape[0] > 1 else np.zeros_like(mouth_open)
        return np.array(
            [
                mouth_open.mean(),
                mouth_width.mean(),
                mouth_ratio.mean(),
                lip_asym.mean(),
                jaw_open.mean(),
                cheek_raise.mean(),
                d_mouth_open.mean(),
                dd_mouth_open.mean(),
            ]
        )
