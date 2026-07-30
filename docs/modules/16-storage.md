# Module 16: Object storage

**Путь:** `services/api/app/storage/` + `services/worker/app/storage/`
**Backend:** S3-совместимый (MinIO в dev, AWS S3/GCS/Azure в prod)

## Файлы

### `s3_client.py`
```python
"""
MG-STUB: реализовать:
- S3Client:
    - __init__(endpoint, access_key, secret_key, region='us-east-1')
    - get_presigned_put(key, content_type, content_length_range, ttl=900) -> {url, fields}
    - get_presigned_get(key, ttl=300) -> url
    - put_object(key, body, content_type) -> etag
    - get_object(key) -> bytes
    - head_object(key) -> metadata
    - delete_object(key)
    - generate_upload_id() -> uuid
    - complete_multipart_upload(upload_id, parts) -> etag
"""
```

### `buckets.py`
```python
"""
MG-STUB: реализовать константы и инициализацию:
- BUCKETS:
    - mimicguard-videos:    raw video (lifecycle: 30d→IA, 90d→Glacier)
    - mimicguard-derived:   landmarks.npz, transcripts.json
    - mimicguard-clips:     вырезанные клипы слов (warmer, 365d)
    - mimicguard-models:    model artifacts (immutable, KMS)
    - mimicguard-audit:     audit exports (WORM)
- init_buckets(s3): создать если нет, выставить lifecycle policies, CORS.
"""
```

### `keys.py`
```python
"""
MG-STUB: реализовать генерацию object keys:
- asset_key(tenant_id, asset_id, ext) -> f"{tenant_id}/videos/{asset_id}.{ext}"
- landmarks_key(tenant_id, job_id) -> f"{tenant_id}/derived/{job_id}/landmarks.npz"
- transcript_key(tenant_id, job_id) -> f"{tenant_id}/derived/{job_id}/transcript.json"
- clip_key(tenant_id, sample_id) -> f"{tenant_id}/clips/{sample_id}.mp4"
- model_key(model_id, version) -> f"{model_id}/{version}/model.onnx"
- audit_export_key(tenant_id, export_id) -> f"{tenant_id}/{export_id}.csv"
"""
```

### `lifecycle.py`
```python
"""
MG-STUB: реализовать:
- apply_lifecycle_policies(s3):
    - mimicguard-videos: Transition to STANDARD_IA after 30d, GLACIER after 90d, Expire after 365d.
    - mimicguard-derived: STANDARD_IA after 90d, Expire after 730d.
    - mimicguard-clips: STANDARD_IA after 90d, Expire after 730d.
    - mimicguard-models: нет lifecycle (immutable).
    - mimicguard-audit: WORM с Object Lock 7 лет.
"""
```

## Upload flow
1. Client → `POST /v1/assets:prepareUpload` → pre-signed URL.
2. Client → PUT напрямую в S3.
3. Client → `POST /v1/assets/{id}:completeUpload` с sha256, etag.
4. Server → ffprobe для validation, mark state=READY, emit event.

## Multipart
- Файлы > 100 MB — multipart upload.
- Part size: 10 MB.
- max parts: 1000 (≈ 10 GB max).
