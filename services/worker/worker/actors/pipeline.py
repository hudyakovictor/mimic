"""Main pipeline actor — orchestrates the 6 stages for one job.

MG-STUB: final.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import io
import json
import os
import tempfile
import time
import uuid
from datetime import UTC, datetime

import dramatiq
import numpy as np
from app.db.models import (
    AnalysisJob,
    Decision,
    LandmarkSequence,
    PhraseTemplate,
    Transcript,
)
from app.settings import get_settings
from app.storage import BUCKET_DERIVED, BUCKET_VIDEOS
from app.storage.keys import audio_key, landmarks_key, normalized_landmarks_key, transcript_key
from sqlalchemy import select, update

from packages.landmark_engine.domain import HeadPose, LandmarkFrame, Point3D
from packages.landmark_engine.domain import LandmarkSequence as LMSequence
from packages.landmark_engine.quality import assess_quality
from worker.actors.db import complete_stage, get_s3, load_asset, load_job, session_scope, start_stage
from worker.asr.transcribe import WhisperEngine
from worker.baseline.match import match as baseline_match
from worker.landmarks.extract import (
    extract_landmarks_from_frames,
    normalize_landmarks,
    write_landmarks_npz,
)
from worker.phoneme.align import align_words_to_landmarks
from worker.video.probe import (
    decode_video_bgr24,
    extract_audio_pcm,
    ffprobe,
    read_wav_float32,
)

SCORER_VERSION = "statistical-v2"
SCORER_CHECKSUM = hashlib.sha256(
    b"motion-features-v2|dtw-window-5|regional-mahalanobis-v2|fusion-0.7-0.3"
).hexdigest()


@dramatiq.actor(queue_name="analysis.pipeline", max_retries=3, time_limit=900_000)
def run_pipeline(job_id: str, correlation_id: str | None = None) -> dict:
    """Entry point for analysis.requested.v1 events."""
    return asyncio.run(_run_pipeline(uuid.UUID(job_id), correlation_id))


class _StageCtx:
    """Lightweight per-stage handle. stage_completion is persisted via a
    fresh session because the stage row is committed in start_stage already.
    """

    def __init__(self, job_id: uuid.UUID, name: str, attempt: int):
        self.job_id = job_id
        self.name = name
        self.attempt = attempt

    async def complete(
        self,
        output_uri: str | None = None,
        output_metadata: dict | None = None,
    ) -> None:
        async with session_scope() as session:
            await complete_stage(session, self.job_id, self.name, self.attempt, output_uri, output_metadata)

    async def fail(self, error: str) -> None:
        from .db import fail_stage

        async with session_scope() as session:
            await fail_stage(session, self.job_id, self.name, self.attempt, error)


async def _run_stage(job_id: uuid.UUID, name: str, attempt: int = 1) -> _StageCtx:
    async with session_scope() as session:
        await start_stage(session, job_id, name, attempt)
    return _StageCtx(job_id, name, attempt)


async def _mark_job_running(job_id: uuid.UUID) -> None:
    async with session_scope() as session:
        await session.execute(
            update(AnalysisJob)
            .where(AnalysisJob.id == job_id)
            .values(state="RUNNING", started_at=datetime.now(UTC))
        )


async def _mark_job_succeeded(job_id: uuid.UUID) -> None:
    async with session_scope() as session:
        await session.execute(
            update(AnalysisJob)
            .where(AnalysisJob.id == job_id)
            .values(state="SUCCEEDED", finished_at=datetime.now(UTC))
        )


async def _mark_insufficient_data(job_id: uuid.UUID, reason: str) -> None:
    async with session_scope() as session:
        await session.execute(
            update(AnalysisJob)
            .where(AnalysisJob.id == job_id)
            .values(
                state="INSUFFICIENT_DATA",
                finished_at=datetime.now(UTC),
                last_error=reason[:500],
            )
        )


async def _persist_landmark_sequence(
    job_id: uuid.UUID,
    tenant_id: uuid.UUID,
    track_id: str,
    schema_version: str,
    frame_count: int,
    fps: float,
    object_key: str,
    quality_score: float,
    quality_failures: list[str],
) -> None:
    async with session_scope() as session:
        session.add(
            LandmarkSequence(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                job_id=job_id,
                track_id=track_id,
                schema_version=schema_version,
                frame_count=frame_count,
                source_fps=fps,
                object_key=object_key,
                quality_score=quality_score,
                quality_failures=list(quality_failures),
            )
        )


async def _persist_transcript(
    job_id: uuid.UUID,
    tenant_id: uuid.UUID,
    language: str,
    model_version: str,
    words: list[dict],
    object_key: str,
    mean_confidence: float,
) -> None:
    async with session_scope() as session:
        session.add(
            Transcript(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                job_id=job_id,
                language=language,
                model_version=model_version,
                words=words,
                object_key=object_key,
                mean_word_confidence=mean_confidence,
            )
        )


async def _persist_decision(
    job_id: uuid.UUID,
    tenant_id: uuid.UUID,
    label: str,
    risk_score: float,
    quality_score: float,
    model_version: str,
    evidence: list[dict],
    phrase_instances: list[dict],
) -> None:
    async with session_scope() as session:
        session.add(
            Decision(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                job_id=job_id,
                label=label,
                risk_score=risk_score,
                quality_score=quality_score,
                model_version=model_version,
                model_checksum="",
                evidence=evidence,
                phrase_instances=phrase_instances,
            )
        )


def _build_landmark_sequence(face_frames, fps: float) -> LMSequence:
    frames = []
    for ff in face_frames:
        if ff.confidence <= 0.3:
            continue
        points = {
            i: Point3D(float(ff.points_2d[i, 0]), float(ff.points_2d[i, 1]), float(ff.points_2d[i, 2]))
            for i in range(ff.points_2d.shape[0])
        }
        frames.append(
            LandmarkFrame(
                timestamp_ms=ff.timestamp_ms,
                points=points,
                confidence=ff.confidence,
                head_pose=HeadPose(yaw=ff.yaw, pitch=ff.pitch, roll=0.0),
            )
        )
    return LMSequence(track_id="t1", schema_version="mediapipe-v1", frames=tuple(frames), source_fps=fps)


async def _run_pipeline(job_id: uuid.UUID, correlation_id: str | None) -> dict:
    settings = get_settings()
    s3 = get_s3()
    t0 = time.perf_counter()

    with tempfile.TemporaryDirectory() as tmp:
        video_path = os.path.join(tmp, "video.mp4")
        audio_path = os.path.join(tmp, "audio.wav")
        landmarks_path = os.path.join(tmp, "landmarks.mgml")
        normalized_path = os.path.join(tmp, "normalized.npy")

        # Load job + asset
        async with session_scope() as session:
            job = await load_job(session, job_id)
            asset = await load_asset(session, job.asset_id)
            tenant_id = job.tenant_id
            object_key = asset.object_key
            if job.state != "QUEUED":
                return {"state": job.state, "deduplicated": True}
            transition = await session.execute(
                update(AnalysisJob)
                .where(
                    AnalysisJob.id == job_id,
                    AnalysisJob.state == "QUEUED",
                )
                .values(state="RUNNING", started_at=datetime.now(UTC))
            )
            if getattr(transition, "rowcount", 0) != 1:
                return {"state": "RUNNING", "deduplicated": True}

        # 1. Validate asset
        stage = await _run_stage(job_id, "VALIDATE_ASSET")
        await s3.download_file(BUCKET_VIDEOS, object_key, video_path)
        info = await ffprobe(video_path)
        await stage.complete(output_metadata={"duration_ms": info.duration_ms, "fps": info.fps})

        # 2. Extract audio
        stage = await _run_stage(job_id, "EXTRACT_AUDIO")
        await extract_audio_pcm(video_path, audio_path)
        await s3.upload_file(
            BUCKET_DERIVED,
            audio_key(tenant_id, job_id),
            audio_path,
            "audio/wav",
        )
        await stage.complete()

        # 3. Extract landmarks
        stage = await _run_stage(job_id, "EXTRACT_LANDMARKS")
        frames = decode_video_bgr24(video_path)
        face_frames = extract_landmarks_from_frames(
            frames, info.fps, settings.mediapipe_min_confidence
        )
        if not face_frames:
            await stage.fail("NO_FRAMES")
            await _mark_insufficient_data(job_id, "NO_FRAMES")
            return {"state": "INSUFFICIENT_DATA"}
        if not any(ff.confidence > 0.5 for ff in face_frames):
            await stage.fail("NO_FACE_DETECTED")
            await _mark_insufficient_data(job_id, "NO_FACE_DETECTED")
            return {"state": "INSUFFICIENT_DATA"}

        seq = _build_landmark_sequence(face_frames, info.fps)
        qa = assess_quality(seq)
        if not qa.accepted or qa.score < settings.quality_min_score:
            failures = ",".join(qa.failures) if qa.failures else "LOW_SCORE"
            await stage.fail(f"QUALITY_FAIL:{failures}")
            await _mark_insufficient_data(job_id, f"QUALITY_FAIL:{failures}")
            return {"state": "INSUFFICIENT_DATA", "quality": qa.score}

        write_landmarks_npz(face_frames, landmarks_path, info.fps)
        with open(landmarks_path, "rb") as f:
            compressed_landmarks = gzip.compress(f.read(), compresslevel=6)
        await s3.put_object(
            BUCKET_DERIVED,
            landmarks_key(tenant_id, job_id),
            compressed_landmarks,
            "application/gzip",
        )
        norm = normalize_landmarks(face_frames)
        np.save(normalized_path, norm)
        with open(normalized_path, "rb") as f:
            await s3.put_object(
                BUCKET_DERIVED,
                normalized_landmarks_key(tenant_id, job_id),
                f.read(),
                "application/octet-stream",
            )
        await _persist_landmark_sequence(
            job_id=job_id,
            tenant_id=tenant_id,
            track_id="t1",
            schema_version="mediapipe-v1",
            frame_count=len(face_frames),
            fps=info.fps,
            object_key=landmarks_key(tenant_id, job_id),
            quality_score=qa.score,
            quality_failures=list(qa.failures),
        )
        await stage.complete(output_metadata={"n_frames": len(face_frames), "quality_score": qa.score})

        # 4. ASR
        stage = await _run_stage(job_id, "ASR_TRANSCRIBE")
        asr = WhisperEngine(
            model_size=settings.asr_model_size,
            device=settings.asr_device,
            compute_type=settings.asr_compute_type,
        )
        transcript = asr.transcribe(audio_path)
        if not transcript.words:
            await stage.fail("NO_SPEECH")
            await _mark_insufficient_data(job_id, "NO_SPEECH")
            return {"state": "INSUFFICIENT_DATA"}
        words_json = [
            {
                "start_ms": w.start_ms,
                "end_ms": w.end_ms,
                "text": w.text,
                "confidence": w.confidence,
            }
            for w in transcript.words
        ]
        transcript_obj = {
            "language": transcript.language,
            "language_probability": transcript.language_probability,
            "text": transcript.text,
            "words": words_json,
        }
        t_key = transcript_key(tenant_id, job_id)
        await s3.put_object(BUCKET_DERIVED, t_key, json.dumps(transcript_obj).encode(), "application/json")
        await _persist_transcript(
            job_id=job_id,
            tenant_id=tenant_id,
            language=transcript.language,
            model_version=f"faster-whisper-{settings.asr_model_size}",
            words=words_json,
            object_key=t_key,
            mean_confidence=transcript.mean_confidence,
        )
        await stage.complete(
            output_metadata={
                "n_words": len(words_json),
                "language": transcript.language,
                "mean_confidence": transcript.mean_confidence,
            }
        )

        # 5+6. Align + Match
        stage = await _run_stage(job_id, "ALIGN_AND_MATCH")
        audio_np, sr = read_wav_float32(audio_path)
        phrase_instances = align_words_to_landmarks(
            words_json, norm, audio_np, audio_sample_rate=sr, fps=info.fps, language=transcript.language
        )

        phrase_decision_rows: list[dict] = []
        evidence_acc: list[dict] = []
        risk_scores: list[float] = []

        async with session_scope() as session:
            for inst in phrase_instances:
                tpl_q = (
                    select(PhraseTemplate)
                    .where(
                        PhraseTemplate.tenant_id == tenant_id,
                        PhraseTemplate.word == inst.word,
                        PhraseTemplate.language == inst.language,
                        PhraseTemplate.subject_id == job.subject_id,
                        PhraseTemplate.state == "ACTIVE",
                    )
                    .order_by(PhraseTemplate.version.desc())
                    .limit(1)
                )
                tpl = (await session.execute(tpl_q)).scalar_one_or_none()
                if tpl is None or tpl.n_samples < settings.phrase_baseline_min_samples:
                    sample_count = tpl.n_samples if tpl is not None else 0
                    evidence_acc.append(
                        {
                            "code": "INSUFFICIENT_BASELINE",
                            "contribution": 0.0,
                            "message": (
                                f"Baseline for '{inst.word}' has {sample_count}/"
                                f"{settings.phrase_baseline_min_samples} verified samples"
                            ),
                            "word": inst.word,
                            "start_ms": inst.start_ms,
                            "end_ms": inst.end_ms,
                        }
                    )
                    phrase_decision_rows.append(
                        {
                            "word": inst.word,
                            "language": inst.language,
                            "start_ms": inst.start_ms,
                            "end_ms": inst.end_ms,
                            "similarity": 0.5,
                            "confidence": inst.confidence,
                            "has_mature_baseline": False,
                            "evidence": [],
                        }
                    )
                    risk_scores.append(0.5)
                    continue
                try:
                    curve_bytes = await s3.get_object(BUCKET_DERIVED, tpl.mean_curve_object_key)
                    template_mean = np.load(io.BytesIO(curve_bytes))
                except Exception:
                    template_mean = inst.landmarks_slice
                m = baseline_match(inst.landmarks_slice, template_mean, tpl.regional_stats or {})
                phrase_decision_rows.append(
                    {
                        "word": inst.word,
                        "language": inst.language,
                        "start_ms": inst.start_ms,
                        "end_ms": inst.end_ms,
                        "similarity": float(m.similarity),
                        "confidence": inst.confidence,
                        "has_mature_baseline": bool(tpl.is_mature),
                        "evidence": [
                            {**e, "word": inst.word, "start_ms": inst.start_ms, "end_ms": inst.end_ms}
                            for e in m.evidence
                        ],
                    }
                )
                evidence_acc.extend(
                    {**e, "word": inst.word, "start_ms": inst.start_ms, "end_ms": inst.end_ms}
                    for e in m.evidence
                )
                risk_scores.append(1.0 - m.similarity)

            risk_score = float(np.mean(risk_scores)) if risk_scores else 0.5
            if risk_score < settings.decision_risk_consistent_max:
                label = "CONSISTENT"
            elif risk_score >= settings.decision_risk_suspicious_min:
                label = "SUSPICIOUS"
            else:
                label = "INSUFFICIENT_DATA"
            evidence_acc.sort(key=lambda x: -abs(x.get("contribution", 0)))
            top_evidence = evidence_acc[:10]
            session.add(
                Decision(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    job_id=job_id,
                    label=label,
                    risk_score=risk_score,
                    quality_score=qa.score,
                    model_version=SCORER_VERSION,
                    model_checksum=SCORER_CHECKSUM,
                    evidence=top_evidence,
                    phrase_instances=phrase_decision_rows,
                )
            )
            await session.execute(
                update(AnalysisJob)
                .where(AnalysisJob.id == job_id)
                .values(state="SUCCEEDED", finished_at=datetime.now(UTC))
            )
        await stage.complete(output_metadata={"n_phrases": len(phrase_decision_rows), "label": label})

    elapsed = time.perf_counter() - t0
    return {"state": "SUCCEEDED", "elapsed_seconds": elapsed}
