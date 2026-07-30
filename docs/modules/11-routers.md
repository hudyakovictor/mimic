# Module 11: API routers

**Путь:** `services/api/app/routers/`
**Правило:** routers не содержат бизнес-логики, только валидация входа, вызов service, форматирование ответа. Никаких SQL/Redis/S3 напрямую.

## Общий контракт
- Все endpoints под `/v1/`.
- Идемпотентность: мутации принимают `Idempotency-Key` header.
- Cursor pagination: `?cursor=...&limit=...`.
- Ошибки через `ApiError` (см. `app/errors.py`).
- Audit: `current_user.id` + `tenant_id` доступны через Depends.

## Файлы

### `auth.py`
```python
"""
MG-STUB: реализовать:
- POST /v1/auth/login: принимает {email, password}; проверяет через pwd_context;
  эмитит access (15 мин) + refresh (24 ч) JWT; пишет refresh в httpOnly cookie
  (production) или возвращает в body (dev).
- POST /v1/auth/refresh: ротация refresh, новый access.
- POST /v1/auth/logout: invalidate refresh в Redis blacklist.
- GET /v1/auth/me: возврат текущего user.

Throttling: 5 попыток логина в минуту с одного IP — fail2ban-like.
"""
```

### `assets.py`
```python
"""
MG-STUB: реализовать:
- POST /v1/assets:prepareUpload: {filename, mime, size, duration_hint?}.
    Генерирует asset_id, S3 pre-signed PUT URL (TTL 15 мин, content-length-binding).
    Пишет assets row со state=PENDING_UPLOAD.
    Audit: 'asset.upload.prepare'.
- POST /v1/assets/{id}:completeUpload: {sha256, etag, duration_ms, mime, width, height, has_audio}.
    Переводит в state=READY, триггерит event asset.uploaded.v1.
- GET /v1/assets/{id}: метаданные, без raw URL.
- GET /v1/assets/{id}/downloadUrl: pre-signed GET URL (TTL 5 мин, audit: 'asset.download').
- POST /v1/assets:importFromUrl: {url}.
    Для YouTube: extract video id, поставить background task yt-dlp → S3.
    Для прямой mp4: скачать, валидировать, положить в S3, completeUpload.
    Возвращает {task_id}. Polling через GET /v1/assets:import/{task_id}.
- GET /v1/assets: список с cursor pagination, фильтр по state, source_type, created_after.

Validation: size ≤ MAX_UPLOAD_BYTES, duration ≤ MAX_VIDEO_DURATION_S.
"""
```

### `analysis_jobs.py`
```python
"""
MG-STUB: реализовать:
- POST /v1/analysis-jobs: {asset_id, claimed_person_id, pipeline_version='v1', correlation_id?}.
    Idempotency: ключ (asset_sha256, claimed_person_id, pipeline_version).
    Проверить asset.state=READY, subject.consent_state=GRANTED.
    Создать job state=QUEUED, outbox event analysis.requested.v1.
- GET /v1/analysis-jobs?state=&subjectId=&cursor=&limit=: список.
- GET /v1/analysis-jobs/{id}: детально + последний decision + stages.
- POST /v1/analysis-jobs/{id}:cancel: только если state=QUEUED, иначе 409.
- POST /v1/analysis-jobs/{id}:retry: только если state=FAILED или INSUFFICIENT_DATA_WITH_RETRY.
    Создаёт новую попытку, инкрементит attempt, переводит в QUEUED.
"""
```

### `subjects.py`
```python
"""
MG-STUB: реализовать:
- POST /v1/subjects: {external_id, display_name, consent_state=PENDING}.
- GET /v1/subjects: список.
- GET /v1/subjects/{id}: детально с количеством baselines, last_analyzed_at.
- PATCH /v1/subjects/{id}: обновление display_name, consent_state, retention_policy.
    Optimistic concurrency по version.
- GET /v1/subjects/{id}/baselines: список PhraseTemplate для этого subject.
- POST /v1/subjects/{id}/consent: {state, signature, evidence_uri}: запись Enrollment.
"""
```

### `words.py` (новая база)
```python
"""
MG-STUB: реализовать:
- GET /v1/words?language=&min_samples=&cursor=&limit=:
    Возвращает distinct words, имеющие ≥1 PhraseTemplate.
    Поля: word, language, total_samples, total_templates, latest_template_id, latest_score_p50.
- GET /v1/words/{word}/templates?cursor=&limit=:
    Список версий шаблона для слова (по subject_id или global).
    Поля: id, version, n_samples, language, created_at, model_version.
- GET /v1/words/{word}/templates/{template_id}:
    Детально: mean curve (downsample до 30 points), covariance diagonal,
    региональные ratios μ±σ, sample_ids.
- GET /v1/words/{word}/samples?templateId=&cursor=&limit=:
    Отдельные verified-прогоны: sample_id, video_clip_url, decision_id, landmarks_summary,
    reviewer_id, created_at.
- GET /v1/words/{word}/samples/{sample_id}/landmarks:
    Pre-signed URL на landmarks.npz + summary stats.
- GET /v1/words/{word}/samples/{sample_id}/videoClipUrl:
    Pre-signed URL на вырезанный клип [start, end] (mp4).
- POST /v1/words/{word}/templates:rebuild:
    Model_admin only. Пересобрать шаблон из всех CONFIRMED_GENUINE по этому слову.
    Audit: 'word.template.rebuild'.

Поддерживается multi-language (word нормализуется: lower, strip punctuation).
"""
```

### `decisions.py`
```python
"""
MG-STUB: реализовать:
- GET /v1/decisions/{id}: full decision + evidence timeline + phrase instances.
- GET /v1/decisions?jobId=&label=&modelVersion=&cursor=&limit=.
- GET /v1/decisions/{id}/landmarkClip: pre-signed URLs на landmarks.npz + audio.
"""
```

### `reviews.py`
```python
"""
MG-STUB: реализовать:
- POST /v1/reviews: {decision_id, verdict, reason, confidence?}.
    reviewer_id из JWT, НЕ из body.
    Verdict ∈ {CONFIRMED_GENUINE, CONFIRMED_SUSPICIOUS, UNDECIDABLE}.
    reason minLength 10, maxLength 2000.
    Audit: 'review.create'.
    Side effect (асинхронно через event review.created.v1): если verdict=CONFIRMED_GENUINE,
    baseline aggregator создаёт/обновляет PhraseTemplate.
- GET /v1/reviews?verdict=&reviewerId=&decisionId=&cursor=&limit=.
- GET /v1/reviews/{id}.
"""
```

### `models_registry.py`
```python
"""
MG-STUB: реализовать:
- GET /v1/models: список ModelVersion.
- GET /v1/models/{id}: checksum, schema, calibration, metrics, intended_use, known_limitations, approver.
- POST /v1/models/{id}:promote: {to_state, reason}.
    VALIDATED→SHADOW, SHADOW→ACTIVE, ACTIVE→RETIRED. RBAC: model_admin.
    При promote ACTIVE: предыдущий ACTIVE уходит в RETIRED.
- POST /v1/models/{id}:rollback: switch pointer на previous ACTIVE.
- POST /v1/models/{id}:retire.
- POST /v1/models: register новый draft (multipart upload артефакта в models bucket).

Audit: каждое действие с reason.
"""
```

### `audit.py`
```python
"""
MG-STUB: реализовать:
- GET /v1/audit?actorId=&action=&resourceType=&resourceId=&from=&to=&cursor=&limit=.
    RBAC: auditor + system_admin.
    Никогда не отдавать PII/biometric поля; только метаданные + actor.
- GET /v1/audit/export?format=csv|jsonl&...: bulk export.
    Создаёт job, результат в S3 с pre-signed URL, audit: 'audit.export'.
"""
```

### `health.py`
```python
"""
- GET /health/live: всегда 200, кроме shutdown.
- GET /health/ready: проверяет PostgreSQL, Redis, MinIO.
- GET /metrics: prometheus client output.
"""
```
