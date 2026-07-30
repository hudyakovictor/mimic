# Module 12: SQLAlchemy domain models

**Путь:** `services/api/app/db/models.py` + `services/api/app/db/`
**ORM:** SQLAlchemy 2.0 (async, Mapped[…])
**Migrations:** Alembic (см. `services/api/alembic/`)

## Conventions
- Все таблицы имеют `id UUID PK`, `tenant_id UUID NOT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`.
- Mutable сущности дополнительно имеют `version INT NOT NULL DEFAULT 1` для optimistic concurrency.
- Append-only (assets, jobs, decisions, reviews, audit) — триггеры запрещают UPDATE/DELETE.
- Индексы на всех FK и на типичных filter columns.
- Все timestamps хранятся в UTC.

## Модели (полный список)

### Tenant
```python
class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[UUID]
    slug: Mapped[str]              # unique
    name: Mapped[str]
    settings: Mapped[dict]         # JSONB: retention, quota
    created_at: Mapped[datetime]
```

### User
```python
class User(Base):
    __tablename__ = "users"
    id, tenant_id, email (unique per tenant), password_hash,
    display_name, roles: Mapped[list[str]],   # ARRAY
    is_active, last_login_at, created_at, updated_at, version
```

### Subject
```python
class Subject(Base):
    __tablename__ = "subjects"
    id, tenant_id, external_id, display_name,
    consent_state: Mapped[str],   # PENDING|GRANTED|REVOKED
    retention_policy: Mapped[dict],  # JSONB
    deleted_at: Mapped[datetime | None],  # tombstone
    created_at, updated_at, version
```

### Enrollment (consent record)
```python
class Enrollment(Base):
    __tablename__ = "enrollments"
    id, subject_id, state, signed_by, evidence_uri,
    ip, user_agent, created_at
```

### Asset
```python
class Asset(Base):
    __tablename__ = "assets"
    id, tenant_id, source_type,   # UPLOAD|YOUTUBE|URL
    source_url: Mapped[str | None],
    object_key, mime, size_bytes, sha256 (unique per tenant),
    duration_ms, width, height, fps, has_audio,
    state: Mapped[str],   # PENDING_UPLOAD|UPLOADING|READY|FAILED|DELETED
    failure_reason: Mapped[str | None],
    uploaded_by, created_at, updated_at
    # append-only: state terminal, version на metadata
```
Append-only через trigger.

### AnalysisJob
```python
class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id, tenant_id, asset_id, subject_id,
    pipeline_version, idempotency_key (unique),
    state: Mapped[str],   # QUEUED|RUNNING|SUCCEEDED|FAILED|INSUFFICIENT_DATA
    attempt, last_error,
    started_at, finished_at,
    created_at, updated_at, version
    # terminal state immutable (через trigger + check в service)
```

### JobStage
```python
class JobStage(Base):
    __tablename__ = "job_stages"
    id, job_id, name,   # VALIDATE_ASSET|EXTRACT_LANDMARKS|...
    state, output_uri, error, started_at, completed_at, attempt
    unique (job_id, name, attempt)
```

### LandmarkSequence (metadata)
```python
class LandmarkSequence(Base):
    __tablename__ = "landmark_sequences"
    id, job_id, track_id, schema_version,
    frame_count, source_fps, object_key,  # .npz
    quality_score, quality_failures: Mapped[list[str]],  # ARRAY
    created_at
```

### Transcript
```python
class Transcript(Base):
    __tablename__ = "transcripts"
    id, job_id, language, model_version, words: Mapped[list],   # JSONB
    object_key (raw json),   # S3
    created_at
```

### Decision
```python
class Decision(Base):
    __tablename__ = "decisions"
    id, job_id, label,   # CONSISTENT|SUSPICIOUS|INSUFFICIENT_DATA
    risk_score, quality_score,
    model_version, model_checksum,
    evidence: Mapped[list],   # JSONB
    phrase_instances: Mapped[list],  # JSONB
    created_at
    # append-only
```

### Review
```python
class Review(Base):
    __tablename__ = "reviews"
    id, tenant_id, decision_id, reviewer_id,
    verdict,   # CONFIRMED_GENUINE|CONFIRMED_SUSPICIOUS|UNDECIDABLE
    reason, confidence,   # optional reviewer confidence 0..1
    created_at
    # append-only
```

### PhraseTemplate
```python
class PhraseTemplate(Base):
    __tablename__ = "phrase_templates"
    id, tenant_id, subject_id,   # subject_id NULL = global word template
    word, language,
    version, parent_id: Mapped[UUID | None],
    n_samples, mean_curve_object_key,   # .npz (3000, n_dims) downsampled
    covariance_diagonal: Mapped[list],   # ARRAY[float]
    regional_stats: Mapped[dict],   # JSONB: mouth_open μ±σ, jaw μ±σ, etc.
    model_version,
    created_at
    unique (subject_id, word, language, version)
    # immutable
```

### PhraseSample
```python
class PhraseSample(Base):
    __tablename__ = "phrase_samples"
    id, tenant_id, template_id, decision_id, review_id,
    video_clip_object_key, landmarks_object_key,
    audio_clip_object_key: Mapped[str | None],
    start_ms, end_ms, confidence,
    n_frames, mean_dtw_to_template: Mapped[float | None],
    created_at
    # immutable
```

### ModelVersion
```python
class ModelVersion(Base):
    __tablename__ = "model_versions"
    id, kind,   # LANDMARK_EXTRACTOR|ASR|MOTION_SCORER|CALIBRATION
    version, artifact_checksum, code_commit,
    feature_schema, training_dataset_manifest: Mapped[dict],
    evaluation_report: Mapped[dict],   # JSONB
    calibration_profile: Mapped[dict],
    intended_use, known_limitations,
    state,   # DRAFT|VALIDATED|SHADOW|ACTIVE|RETIRED
    approver_id, approved_at,
    created_at, updated_at
    unique (kind, version)
```

### AuditEvent
```python
class AuditEvent(Base):
    __tablename__ = "audit_events"
    id, tenant_id, actor_id, action,
    resource_type, resource_id,
    at, ip, user_agent, correlation_id,
    reason: Mapped[str | None], metadata: Mapped[dict],
    # append-only
```

### OutboxEvent
```python
class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id, event_name, payload: Mapped[dict],
    correlation_id, created_at,
    published_at: Mapped[datetime | None],
    attempts, last_error: Mapped[str | None]
```

## Alembic
- `services/api/alembic/env.py` — async.
- `services/api/alembic/versions/` — миграции, snake_case.
- Каждая миграция имеет и upgrade, и downgrade.
- Data migrations — отдельная revision, без auto-generated schema.

## Append-only enforcement
```sql
CREATE OR REPLACE FUNCTION deny_mutation() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'Append-only table %', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER decisions_no_update BEFORE UPDATE OR DELETE ON decisions
  FOR EACH ROW EXECUTE FUNCTION deny_mutation();
-- ...то же для jobs, reviews, audit_events, phrase_samples, phrase_templates
```
