"""Pydantic schemas for API request/response models.

MG-STUB: final — all schemas use snake_case in Python, camelCase on wire via
`alias_generator=to_camel` and `populate_by_name=True`.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Enums as Literal types for OpenAPI clarity
JobStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "INSUFFICIENT_DATA"]
DecisionLabel = Literal["CONSISTENT", "SUSPICIOUS", "INSUFFICIENT_DATA"]
ReviewVerdict = Literal["CONFIRMED_GENUINE", "CONFIRMED_SUSPICIOUS", "UNDECIDABLE"]
AssetState = Literal["PENDING_UPLOAD", "UPLOADING", "READY", "FAILED", "DELETED"]
AssetSourceType = Literal["UPLOAD", "YOUTUBE", "URL"]
ConsentState = Literal["PENDING", "GRANTED", "REVOKED"]
ModelKind = Literal["LANDMARK_EXTRACTOR", "ASR", "MOTION_SCORER", "CALIBRATION"]
ModelState = Literal["DRAFT", "VALIDATED", "SHADOW", "ACTIVE", "RETIRED"]


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


class APIModel(BaseModel):
    """Base model with camelCase wire format."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


# ----------------------------- Auth --------------------------------


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenPair(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: Optional["CurrentUser"] = None


class RefreshRequest(APIModel):
    refresh_token: str


class CurrentUser(APIModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    roles: list[str]
    tenant_id: uuid.UUID
    tenant_slug: str


# ----------------------------- Assets ------------------------------


class PrepareUploadRequest(APIModel):
    filename: str = Field(min_length=1, max_length=255)
    mime: str = Field(min_length=1, max_length=128)
    size_bytes: int = Field(gt=0, le=1_073_741_824)
    title: str | None = Field(default=None, max_length=512)
    extra: dict[str, Any] = Field(default_factory=dict)


class PrepareUploadResponse(APIModel):
    asset_id: uuid.UUID
    upload_url: str
    fields: dict[str, str]
    object_key: str
    expires_in: int


class CompleteUploadRequest(APIModel):
    sha256: str = Field(min_length=64, max_length=64)
    etag: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    fps: float | None = Field(default=None, gt=0)
    has_audio: bool = True


class ImportFromUrlRequest(APIModel):
    url: str = Field(min_length=1, max_length=2048)
    title: str | None = Field(default=None, max_length=512)


class ImportTaskStatus(APIModel):
    task_id: uuid.UUID
    asset_id: uuid.UUID | None
    state: str
    progress: float = Field(ge=0, le=1)
    error: str | None = None


class AssetOut(APIModel):
    id: uuid.UUID
    source_type: AssetSourceType
    source_url: str | None
    mime: str
    size_bytes: int
    sha256: str | None
    duration_ms: int | None
    width: int | None
    height: int | None
    fps: float | None
    has_audio: bool
    state: AssetState
    title: str | None
    failure_reason: str | None
    created_at: datetime


class DownloadUrlResponse(APIModel):
    url: str
    expires_in: int


# ----------------------------- Jobs --------------------------------


class CreateJobRequest(APIModel):
    asset_id: uuid.UUID
    claimed_person_id: uuid.UUID
    pipeline_version: str = Field(default="v1", max_length=32)
    correlation_id: uuid.UUID | None = None


class JobStageOut(APIModel):
    id: uuid.UUID
    name: str
    state: str
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    output_uri: str | None


class JobOut(APIModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    subject_id: uuid.UUID
    pipeline_version: str
    state: JobStatus
    attempt: int
    last_error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    decision: DecisionOut | None = None
    stages: list[JobStageOut] = Field(default_factory=list)


# ----------------------------- Subjects ----------------------------


class SubjectCreate(APIModel):
    external_id: str = Field(min_length=1, max_length=128)
    display_name: str = Field(default="", max_length=255)
    consent_state: ConsentState = "PENDING"


class SubjectUpdate(APIModel):
    display_name: str | None = Field(default=None, max_length=255)
    consent_state: ConsentState | None = None
    retention_policy: dict[str, Any] | None = None
    version: int  # optimistic concurrency


class SubjectOut(APIModel):
    id: uuid.UUID
    external_id: str
    display_name: str
    consent_state: ConsentState
    retention_policy: dict[str, Any]
    n_jobs: int = 0
    n_baselines: int = 0
    last_analyzed_at: datetime | None = None
    created_at: datetime
    version: int


class EnrollmentRequest(APIModel):
    state: ConsentState
    signed_by: str | None = None
    evidence_uri: str | None = None


class EnrollmentOut(APIModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    state: ConsentState
    signed_by: str | None
    evidence_uri: str | None
    created_at: datetime


# ----------------------------- Words / Phrases ---------------------


class WordSummary(APIModel):
    word: str
    language: str
    n_templates: int
    n_samples: int
    has_mature_baseline: bool
    last_decision_label: DecisionLabel | None = None
    last_updated: datetime | None = None


class PhraseTemplateSummary(APIModel):
    id: uuid.UUID
    subject_id: uuid.UUID | None
    word: str
    language: str
    version: int
    n_samples: int
    is_mature: bool
    state: str
    model_version: str
    created_at: datetime


class PhraseTemplateDetail(PhraseTemplateSummary):
    mean_curve: list[list[float]]  # 30 × n_dims downsampled
    regional_stats: dict[str, float]
    sample_ids: list[uuid.UUID]
    parent_id: uuid.UUID | None


class PhraseSampleOut(APIModel):
    id: uuid.UUID
    template_id: uuid.UUID
    decision_id: uuid.UUID
    review_id: uuid.UUID
    word: str
    language: str
    start_ms: int
    end_ms: int
    confidence: float
    n_frames: int
    mean_dtw_to_template: float | None
    video_clip_url: str | None = None
    landmarks_url: str | None = None
    audio_clip_url: str | None = None
    created_at: datetime


class SampleUrlsResponse(APIModel):
    video_clip_url: str
    landmarks_url: str
    audio_clip_url: str | None = None
    expires_in: int


# ----------------------------- Decisions ---------------------------


class EvidenceItem(APIModel):
    code: str
    contribution: float = Field(ge=-1, le=1)
    message: str
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    word: str | None = None


class PhraseInstance(APIModel):
    word: str
    language: str
    start_ms: int
    end_ms: int
    similarity: float
    confidence: float
    has_mature_baseline: bool
    evidence: list[EvidenceItem] = Field(default_factory=list)


class DecisionOut(APIModel):
    id: uuid.UUID
    job_id: uuid.UUID
    label: DecisionLabel
    risk_score: float = Field(ge=0, le=1)
    quality_score: float = Field(ge=0, le=1)
    model_version: str
    model_checksum: str
    evidence: list[EvidenceItem]
    phrase_instances: list[PhraseInstance]
    created_at: datetime


# ----------------------------- Reviews -----------------------------


class CreateReviewRequest(APIModel):
    decision_id: uuid.UUID
    verdict: ReviewVerdict
    reason: str = Field(min_length=10, max_length=2000)
    confidence: float | None = Field(default=None, ge=0, le=1)


class ReviewOut(APIModel):
    id: uuid.UUID
    decision_id: uuid.UUID
    reviewer_id: uuid.UUID
    reviewer_name: str = ""
    verdict: ReviewVerdict
    reason: str
    confidence: float | None
    created_at: datetime


# ----------------------------- Models ------------------------------


class ModelVersionOut(APIModel):
    id: uuid.UUID
    kind: ModelKind
    version: str
    artifact_checksum: str
    code_commit: str
    feature_schema: str
    state: ModelState
    intended_use: str
    known_limitations: str
    evaluation_report: dict[str, Any]
    calibration_profile: dict[str, Any]
    approver_id: uuid.UUID | None
    approved_at: datetime | None
    promoted_by: uuid.UUID | None
    promoted_at: datetime | None
    created_at: datetime


class ModelPromoteRequest(APIModel):
    to_state: ModelState
    reason: str = Field(min_length=10, max_length=2000)


# ----------------------------- Audit -------------------------------


class AuditEventOut(APIModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    at: datetime
    ip: str | None
    correlation_id: uuid.UUID | None
    reason: str | None


# ----------------------------- Dashboard ---------------------------


class DashboardMetrics(APIModel):
    pending_reviews: int
    quality_ok_ratio: float
    median_processing_seconds: float
    reviewer_agreement: float
    jobs_last_7d: list[dict[str, Any]]  # [{date, count, suspicious}]
    recent_analyses: list[JobOut]


# ----------------------------- Common ------------------------------


class Page(APIModel):
    items: list[Any]
    next_cursor: str | None
    total_estimate: int | None = None


# Resolve forward refs
JobOut.model_rebuild()
