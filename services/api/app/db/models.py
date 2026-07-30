"""All SQLAlchemy models for the API.

MG-STUB: final. Schema decisions:
- Every table has a GUID primary key.
- Every tenant-owned table has tenant_id + created_at + updated_at.
- Mutable entities (Subject, ModelVersion) have version.
- Append-only tables (assets, jobs, decisions, reviews, audit, phrase_*) have no version;
  UPDATE/DELETE is blocked by PostgreSQL triggers in migrations.
- PostgreSQL JSONB is used for flexible payloads (evidence, phrase_instances, settings).
  On SQLite (dev), JSON is stored as TEXT.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import GUID, Base, TenantScopedMixin, TimestampedMixin, VersionedMixin


def _detect_postgres() -> bool:
    """Best-effort: detect PostgreSQL at class-definition time.

    Falls back to False (SQLite-friendly types) if settings cannot be read.
    """
    try:
        from ..settings import get_settings

        url = get_settings().database_url
        return url.startswith("postgresql")
    except Exception:
        return False


class _SQLiteArray(TypeDecorator):
    """SQLite-compatible ARRAY emulation. Stores Python lists as JSON text."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        import json as _json

        return _json.dumps(list(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        import json as _json

        try:
            parsed = _json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []


def _JSON() -> Any:
    if _detect_postgres():
        from sqlalchemy.dialects.postgresql import JSONB

        return JSONB
    return JSON


def _ARRAY(elem):  # type: ignore[no-untyped-def]
    if _detect_postgres():
        from sqlalchemy.dialects.postgresql import ARRAY

        return ARRAY(elem)
    return _SQLiteArray()


# ----------------------------- Tenancy / Auth --------------------------


class Tenant(Base, TimestampedMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    settings: Mapped[dict] = mapped_column(_JSON(), nullable=False, default=dict)


class User(Base, TenantScopedMixin, TimestampedMixin, VersionedMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    roles: Mapped[list[str]] = mapped_column(_ARRAY(String), nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ----------------------------- Subjects / Enrollment ------------------


class Subject(Base, TenantScopedMixin, TimestampedMixin, VersionedMixin):
    __tablename__ = "subjects"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    consent_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"
    )  # PENDING|GRANTED|REVOKED
    retention_policy: Mapped[dict] = mapped_column(_JSON(), nullable=False, default=dict)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uq_subjects_tenant_external"),
    )


class Enrollment(Base, TenantScopedMixin, TimestampedMixin):
    __tablename__ = "enrollments"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    signed_by: Mapped[str | None] = mapped_column(String(255))
    evidence_uri: Mapped[str | None] = mapped_column(String(512))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))


# ----------------------------- Assets ----------------------------------


class Asset(Base, TenantScopedMixin, TimestampedMixin):
    """Immutable metadata for an uploaded media asset. Append-only."""

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # UPLOAD|YOUTUBE|URL
    source_url: Mapped[str | None] = mapped_column(String(1024))
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    fps: Mapped[float | None] = mapped_column(Float)
    has_audio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING_UPLOAD")
    failure_reason: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512))
    extra: Mapped[dict] = mapped_column(_JSON(), nullable=False, default=dict)

    __table_args__ = (
        Index("ix_assets_state", "state"),
        Index("ix_assets_created_at", "created_at"),
    )


# ----------------------------- Jobs / Stages --------------------------


class AnalysisJob(Base, TenantScopedMixin, TimestampedMixin, VersionedMixin):
    __tablename__ = "analysis_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("assets.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("subjects.id"), nullable=False, index=True
    )
    pipeline_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="QUEUED"
    )  # QUEUED|RUNNING|SUCCEEDED|FAILED|INSUFFICIENT_DATA
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(GUID())

    __table_args__ = (
        UniqueConstraint(
            "asset_id", "subject_id", "pipeline_version", name="uq_jobs_idempotency"
        ),
        Index("ix_jobs_state", "state"),
    )


class JobStage(Base, TenantScopedMixin, TimestampedMixin):
    __tablename__ = "job_stages"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    output_uri: Mapped[str | None] = mapped_column(String(512))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    output_metadata: Mapped[dict] = mapped_column(_JSON(), nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("job_id", "name", "attempt", name="uq_job_stages_unique"),
    )


# ----------------------------- Derived -------------------------------


class LandmarkSequence(Base, TenantScopedMixin, TimestampedMixin):
    __tablename__ = "landmark_sequences"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    track_id: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    frame_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_fps: Mapped[float] = mapped_column(Float, nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quality_failures: Mapped[list[str]] = mapped_column(_ARRAY(String), nullable=False, default=list)


class Transcript(Base, TenantScopedMixin, TimestampedMixin):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    words: Mapped[list[dict]] = mapped_column(_JSON(), nullable=False, default=list)
    object_key: Mapped[str | None] = mapped_column(String(512))
    mean_word_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


# ----------------------------- Decisions / Reviews --------------------


class Decision(Base, TenantScopedMixin, TimestampedMixin):
    """Append-only: model result + evidence + phrase instances."""

    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # CONSISTENT|SUSPICIOUS|INSUFFICIENT_DATA
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_checksum: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    evidence: Mapped[list[dict]] = mapped_column(_JSON(), nullable=False, default=list)
    phrase_instances: Mapped[list[dict]] = mapped_column(_JSON(), nullable=False, default=list)


class Review(Base, TenantScopedMixin, TimestampedMixin):
    """Append-only human review."""

    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    decision_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("decisions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    # CONFIRMED_GENUINE|CONFIRMED_SUSPICIOUS|UNDECIDABLE
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)


# ----------------------------- Phrase templates / samples ------------


class PhraseTemplate(Base, TenantScopedMixin, TimestampedMixin):
    """Aggregated baseline for a (subject|global, word, language). Immutable: new version per update."""

    __tablename__ = "phrase_templates"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("subjects.id", ondelete="SET NULL"), index=True
    )
    word: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    n_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mean_curve_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    cov_diag_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    regional_stats: Mapped[dict] = mapped_column(_JSON(), nullable=False, default=dict)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    is_mature: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    # DRAFT|ACTIVE|RETIRED

    __table_args__ = (
        Index("ix_phrase_templates_word_lang", "word", "language"),
        Index("ix_phrase_templates_subject_word", "subject_id", "word", "language"),
    )


class PhraseSample(Base, TenantScopedMixin, TimestampedMixin):
    """One verified occurrence of a word. Immutable."""

    __tablename__ = "phrase_samples"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("phrase_templates.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("decisions.id", ondelete="RESTRICT"), nullable=False
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("reviews.id", ondelete="RESTRICT"), nullable=False
    )
    word: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    video_clip_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    landmarks_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    audio_clip_object_key: Mapped[str | None] = mapped_column(String(512))
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    n_frames: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mean_dtw_to_template: Mapped[float | None] = mapped_column(Float)


# ----------------------------- Model registry ------------------------


class ModelVersion(Base, TimestampedMixin, VersionedMixin):
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    # LANDMARK_EXTRACTOR|ASR|MOTION_SCORER|CALIBRATION
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    artifact_checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    code_commit: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    feature_schema: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    training_dataset_manifest: Mapped[dict] = mapped_column(_JSON(), nullable=False, default=dict)
    evaluation_report: Mapped[dict] = mapped_column(_JSON(), nullable=False, default=dict)
    calibration_profile: Mapped[dict] = mapped_column(_JSON(), nullable=False, default=dict)
    intended_use: Mapped[str] = mapped_column(Text, nullable=False, default="")
    known_limitations: Mapped[str] = mapped_column(Text, nullable=False, default="")
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    # DRAFT|VALIDATED|SHADOW|ACTIVE|RETIRED
    approver_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promoted_by: Mapped[uuid.UUID | None] = mapped_column(GUID())
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promotion_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("kind", "version", name="uq_model_kind_version"),
        Index("ix_models_state", "state"),
    )


# ----------------------------- Audit / Outbox ------------------------


class AuditEvent(Base, TenantScopedMixin, TimestampedMixin):
    """Append-only security/accounting record."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), index=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict] = mapped_column(_JSON(), nullable=False, default=dict)


class OutboxEvent(Base, TimestampedMixin):
    """Transactional outbox: written in same TX as domain change, then published."""

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    event_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(_JSON(), nullable=False)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        # Partial index for unpublished events. On PostgreSQL the WHERE clause
        # makes the index smaller; on SQLite we fall back to a regular index.
        Index("ix_outbox_unpublished", "created_at"),
    )
