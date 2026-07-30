"""Review service + Baseline aggregator (called on review.created.v1)."""

from __future__ import annotations

import gzip
import io
import json
import uuid

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Decision, PhraseSample, PhraseTemplate, Review, User
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
    normalized_landmarks_key,
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
        already_aggregated = await self.session.scalar(
            select(PhraseSample.id).where(PhraseSample.review_id == review_id).limit(1)
        )
        if already_aggregated is not None:
            log.info("baseline.review_already_aggregated", review_id=str(review_id))
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
        raw_landmarks = self._parse_npz(landmarks_bytes)
        try:
            normalized_bytes = await s3.get_object(
                BUCKET_DERIVED,
                normalized_landmarks_key(self.tenant_id, decision.job_id),
            )
            normalized_landmarks = np.load(io.BytesIO(normalized_bytes))
        except Exception as exc:
            log.warning("baseline.no_normalized_landmarks", job_id=str(decision.job_id), error=str(exc))
            return None
        if raw_landmarks is None or normalized_landmarks.ndim != 2:
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
                normalized_landmarks=normalized_landmarks,
                raw_landmarks=raw_landmarks,
                source_fps=lm.source_fps,
                sample_confidence=float(inst.get("confidence", 0.0)),
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
        normalized_landmarks: np.ndarray,
        raw_landmarks: np.ndarray,
        source_fps: float,
        sample_confidence: float,
        review_id: uuid.UUID,
        decision_id: uuid.UUID,
        settings,
        s3: S3Client,
    ) -> PhraseTemplate | None:
        # Do not let uncertain ASR labels poison a word-specific baseline.
        if sample_confidence < 0.65:
            return None
        # Templates use the same normalized 33-dimensional schema as scoring.
        # Raw 478-point frames are retained only for reviewer overlay.
        sliced = self._slice_landmarks_by_time(normalized_landmarks, start_ms, end_ms, source_fps)
        raw_sliced = self._slice_landmarks_by_time(raw_landmarks, start_ms, end_ms, source_fps)
        if sliced is None or raw_sliced is None or len(sliced) < 10:
            return None
        n_frames = len(sliced)
        features = self._extract_features(sliced)
        latest = await self.templates.get_latest_active(word, language, subject_id)
        sample_curve = self._resample(sliced, 30).astype(np.float32)
        if sample_curve.ndim != 2 or sample_curve.shape[1] == 0:
            return None

        old_n = 0
        old_curve: np.ndarray | None = None
        old_cov: np.ndarray | None = None
        if latest is not None:
            try:
                old_curve = np.load(
                    io.BytesIO(await s3.get_object(BUCKET_DERIVED, latest.mean_curve_object_key))
                ).astype(np.float32)
                old_cov = np.load(
                    io.BytesIO(await s3.get_object(BUCKET_DERIVED, latest.cov_diag_object_key))
                ).astype(np.float32)
                if old_curve.shape != sample_curve.shape or old_cov.shape != sample_curve.shape:
                    raise ValueError("feature schema shape changed")
                old_n = max(0, int(latest.n_samples))
            except Exception as exc:
                log.warning(
                    "baseline.previous_template_unreadable", template_id=str(latest.id), error=str(exc)
                )
                old_curve = None
                old_cov = None
                old_n = 0

        max_n = settings.phrase_template_max_samples
        new_n = min(old_n + 1, max_n)
        if old_curve is None or old_cov is None or old_n == 0:
            mean_curve = sample_curve
            cov_diag = np.zeros_like(sample_curve)
        else:
            # Online population mean/variance (Welford). Once MAX_N is reached,
            # alpha=1/MAX_N becomes a bounded rolling approximation.
            effective_old_n = min(old_n, max_n - 1) if old_n < max_n else max_n - 1
            effective_new_n = max(1, effective_old_n + 1)
            delta = sample_curve - old_curve
            mean_curve = old_curve + delta / effective_new_n
            cov_diag = (effective_old_n * old_cov + delta * (sample_curve - mean_curve)) / effective_new_n
            cov_diag = np.maximum(cov_diag, 1e-8)

        regional_stats: dict[str, float] = {}
        for name, feature_index in (
            ("mouth_open", 0),
            ("mouth_ratio", 2),
            ("lip_asym", 3),
            ("jaw_open", 4),
        ):
            value = float(features[feature_index])
            previous_mu = float((latest.regional_stats if latest else {}).get(f"{name}_mu", value))
            previous_sigma = float((latest.regional_stats if latest else {}).get(f"{name}_sigma", 0.0))
            if old_n <= 0:
                mu, variance = value, 0.0
            else:
                weight = max(1, min(old_n + 1, max_n))
                mu = previous_mu + (value - previous_mu) / weight
                variance = ((weight - 1) * previous_sigma**2 + (value - previous_mu) * (value - mu)) / weight
            regional_stats[f"{name}_mu"] = float(mu)
            regional_stats[f"{name}_sigma"] = float(max(variance, 0.0) ** 0.5 + 1e-6)
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
        # Create the template before its FK-bound sample. IDs are chosen up
        # front so object keys and database rows remain reproducible.
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
            model_version="statistical-v2",
            is_mature=is_mature,
            template_id=new_id,
        )
        sample_id = uuid.uuid4()
        sample_key = phrase_landmarks_key(self.tenant_id, sample_id)
        await s3.put_object(
            BUCKET_CLIPS,
            sample_key,
            gzip.compress(
                self._serialize_landmarks(raw_sliced, source_fps),
                compresslevel=6,
            ),
            "application/gzip",
        )
        await self.samples.create(
            template_id=tpl.id,
            decision_id=decision_id,
            review_id=review_id,
            word=word,
            language=language,
            start_ms=start_ms,
            end_ms=end_ms,
            video_clip_object_key="",
            landmarks_object_key=sample_key,
            audio_clip_object_key=None,
            confidence=max(0.0, min(1.0, sample_confidence)),
            n_frames=n_frames,
            mean_dtw_to_template=None,
            sample_id=sample_id,
        )
        return tpl

    @staticmethod
    def _parse_npz(blob: bytes) -> np.ndarray | None:
        """Parse landmarks.npz written by worker. Format:
        header (json string terminated by newline),
        then binary float32 array of shape (T, 478, 3) for mediapipe,
        or (T, 33) for normalized.
        """
        try:
            if blob.startswith(b"\x1f\x8b"):
                blob = gzip.decompress(blob)
            # Find newline
            nl = blob.find(b"\n")
            if nl < 0:
                return None
            header = json.loads(blob[:nl].decode())
            shape = tuple(header["shape"])
            dtype = np.dtype(header.get("dtype", "float32"))
            value_count = int(np.prod(shape))
            arr = np.frombuffer(blob, dtype=dtype, count=value_count, offset=nl + 1).reshape(shape)
            return arr.copy()
        except Exception as e:
            log.warning("baseline.parse_npz_failed", error=str(e))
            return None

    @staticmethod
    def _slice_landmarks_by_time(
        landmarks: np.ndarray,
        start_ms: int,
        end_ms: int,
        source_fps: float = 30.0,
    ) -> np.ndarray | None:
        """Slice normalized or raw landmarks using the measured source cadence."""
        if landmarks.ndim not in (2, 3):
            return None
        frame_count = landmarks.shape[0]
        fps = max(1e-3, source_fps)
        start_index = int(start_ms / 1000 * fps)
        end_index = int(np.ceil(end_ms / 1000 * fps))
        start_index = max(0, min(frame_count, start_index))
        end_index = max(start_index + 1, min(frame_count, end_index))
        return landmarks[start_index:end_index]

    @staticmethod
    def _serialize_landmarks(raw_landmarks: np.ndarray, source_fps: float) -> bytes:
        """Serialize a phrase overlay in the same MGML format as the worker."""
        frames = raw_landmarks.astype(np.float32, copy=False)
        frame_count = frames.shape[0]
        meta = np.zeros((frame_count, 4), dtype=np.float32)
        meta[:, 0] = np.arange(frame_count, dtype=np.float32) * 1000 / max(source_fps, 1e-3)
        meta[:, 1] = 1.0
        header = json.dumps(
            {
                "shape": list(frames.shape),
                "dtype": "float32",
                "schema": "mediapipe-v1",
                "fps": float(source_fps),
                "meta_shape": list(meta.shape),
            },
            separators=(",", ":"),
        ).encode()
        return header + b"\n" + frames.tobytes() + meta.tobytes()

    @staticmethod
    def _resample(arr: np.ndarray, target_len: int) -> np.ndarray:
        """Linear interpolation resample to fixed length."""
        from scipy.interpolate import interp1d

        frame_count = arr.shape[0]
        if frame_count == target_len:
            return arr
        x_old = np.linspace(0, 1, frame_count)
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
        # (33 dims only; cheek_upper_r would be at 36 in 11-point x 3 + offset)
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
