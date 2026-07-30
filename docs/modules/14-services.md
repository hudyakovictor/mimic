# Module 14: Application services

**Путь:** `services/api/app/services/`
**Назначение:** use-cases, оркестрация между repositories, внешними системами и events. Содержат бизнес-правила.

## Conventions
- Pure async, no FastAPI deps (только repository, settings, event publisher).
- Не возвращают HTTP-ответы — только доменные объекты или `Result` (success/raise ApiError).
- Все мутации пишут audit event в той же транзакции.
- Idempotency: проверка перед мутацией.

## Файлы

### `auth.py`
```python
"""
MG-STUB: реализовать:
- AuthService.login(email, password, ip, user_agent) -> {access, refresh, user}
    - bcrypt verify
    - 5 attempts/min throttling (Redis counter)
    - create access JWT (15 мин) + refresh (24 ч, rotation_id в Redis)
    - audit: 'auth.login.success' / 'auth.login.failed'
- AuthService.refresh(refresh_token) -> {access, refresh}
    - rotation: old refresh deleted, new one issued
- AuthService.logout(refresh_token): добавить в Redis blacklist с TTL = refresh TTL.
- AuthService.me(user_id) -> User
"""
```

### `assets.py`
```python
"""
MG-STUB: реализовать:
- AssetService.prepare_upload(filename, mime, size, ...) -> {asset_id, upload_url, fields}
    - create asset row state=PENDING_UPLOAD
    - boto3 generate_presigned_url(PutObject, Conditions=[content-length-range])
- AssetService.complete_upload(asset_id, sha256, etag, duration_ms, ...):
    - validate sha256 matches, size matches
    - probe с ffmpeg, валидация codec/duration
    - mark state=READY
    - emit asset.uploaded.v1 в outbox
- AssetService.import_from_url(url, uploaded_by) -> {task_id}
    - YouTube: extract video_id, поставить background download task (yt-dlp)
    - Прямая mp4: download с retry, валидация, complete_upload
    - Track import progress
- AssetService.get_download_url(asset_id, current_user) -> {url}
    - audit: 'asset.download'
    - check permission video:read
"""
```

### `analysis_jobs.py`
```python
"""
MG-STUB: реализовать:
- AnalysisJobService.create(asset_id, claimed_person_id, pipeline_version, current_user) -> Job
    - проверка asset.state=READY, subject.consent_state=GRANTED
    - check idempotency: (asset.sha256, claimed_person_id, pipeline_version)
    - create job state=QUEUED
    - outbox: analysis.requested.v1
    - audit: 'job.create'
- AnalysisJobService.cancel(job_id) -> Job
    - только если state=QUEUED; иначе 409
    - outbox: job.cancelled.v1
- AnalysisJobService.retry(job_id) -> Job
    - только если state=FAILED
    - new attempt, increment
- AnalysisJobService.list(filters, cursor, limit) -> tuple[list[Job], cursor]
"""
```

### `reviews.py`
```python
"""
MG-STUB: реализовать:
- ReviewService.create(decision_id, verdict, reason, confidence, current_user) -> Review
    - reviewer_id из JWT, не из body
    - валидация reason (10..2000 chars)
    - create review (append-only)
    - outbox: review.created.v1
    - audit: 'review.create'
"""
```

### `words.py`
```python
"""
MG-STUB: реализовать:
- WordService.list_distinct(filters) -> list[{word, language, n_templates, n_samples}]
- WordService.list_templates(word, language) -> list[PhraseTemplate]
- WordService.get_template(template_id) -> PhraseTemplate
- WordService.list_samples(template_id, cursor) -> list[PhraseSample]
- WordService.get_sample_landmarks_url(sample_id) -> pre-signed URL
- WordService.get_sample_video_url(sample_id) -> pre-signed URL
"""
```

### `baseline_aggregator.py`
```python
"""
MG-STUB: реализовать (вызывается через consumer review.created.v1):
- aggregate_on_review(review):
    Если verdict=CONFIRMED_GENUINE:
        decision = get(decision.phrase_instances)
        для каждого phrase_instance (word, landmarks_slice, [start,end]):
            latest_template = get_latest(subject_id, word, language)
            if latest_template is None or latest_template.n_samples < MAX_N:
                добавить sample в новый template (version = latest+1 или 1)
            else:
                добавить sample к существующему template (новая версия)
            rebuild mean_curve, covariance_diagonal, regional_stats
    Если verdict != CONFIRMED_GENUINE:
        sample НЕ добавляется. Можно положить в quarantine dataset для будущего review.

Атомарность: всё в одной транзакции, или через outbox+retry.

Statistics (numpy):
    mean_curve = mean(samples)        # shape (n_samples, 30) → (T, 30)
    downsample to fixed length 30 через simple uniform sampling
    covariance_diagonal = var(samples) over time axis  → shape (30,)
    regional_stats = {mouth_open: (μ, σ), ...} из региональных ratios
"""
```

### `audit.py`
```python
"""
MG-STUB: реализовать:
- AuditService.log(action, resource_type, resource_id, actor_id, tenant_id, request_metadata, reason=None)
    пишет в ту же транзакцию что и доменное действие
- AuditService.list(filters, cursor, limit)
- AuditService.export(filters, format, actor_id) -> job_id
    создаёт background job, результат в S3 с expiry 7 дней
    audit: 'audit.export'
"""
```
