# API and events

REST contract — `packages/contracts/openapi.yaml` (генерируется из Pydantic через `datamodel-code-generator`).
События — `packages/contracts/events.md`.

## Conventions
- UUIDs (v4), UTC RFC3339 timestamps, camelCase on wire.
- `Idempotency-Key` header обязателен для всех мутаций в production.
- Error body: `{ "code": string, "message": string, "correlationId": string, "fieldErrors": [{...}] }`.
- Cursor pagination (base64-encoded `cursor=eyJ...`), never offset.
- Optimistic concurrency: `version` поле в mutable entities (Subjects, Baselines, Model configs).
- Reviews создают новые записи; decisions никогда не патчатся.

## Endpoints (полный список v1)

### Auth
- `POST /v1/auth/login` — exchange credentials for JWT.
- `POST /v1/auth/refresh` — rotate access token.
- `POST /v1/auth/logout` — invalidate refresh.
- `GET  /v1/auth/me` — current user + roles.

### Assets
- `POST /v1/assets:prepareUpload` — get pre-signed S3 URL + asset_id.
- `POST /v1/assets/{asset_id}:completeUpload` — finalize, start hashing.
- `GET  /v1/assets/{asset_id}` — metadata.
- `GET  /v1/assets/{asset_id}/downloadUrl` — pre-signed read URL.
- `POST /v1/assets:importFromUrl` — start background download (YouTube/mp4).
- `GET  /v1/assets:import/{task_id}` — import progress.

### Jobs
- `POST /v1/analysis-jobs` — register a job (asset_id, claimed_person_id).
- `GET  /v1/analysis-jobs` — list with cursor + filters.
- `GET  /v1/analysis-jobs/{job_id}` — full detail.
- `POST /v1/analysis-jobs/{job_id}:cancel` — cancel if QUEUED.
- `POST /v1/analysis-jobs/{job_id}:retry` — re-enqueue FAILED.

### Subjects
- `POST   /v1/subjects` — create subject.
- `GET    /v1/subjects` — list.
- `GET    /v1/subjects/{subject_id}` — detail.
- `PATCH  /v1/subjects/{subject_id}` — update (consent_state, display_name).
- `GET    /v1/subjects/{subject_id}/baselines` — list baseline versions for subject.

### Words / Phrases (новая база)
- `GET    /v1/words` — list distinct words seen across verified decisions (с пагинацией, фильтром по языку).
- `GET    /v1/words/{word}/templates` — все версии шаблона по этому слову.
- `GET    /v1/words/{word}/samples?templateId=...` — отдельные verified-прогоны.
- `GET    /v1/words/{word}/samples/{sample_id}/landmarks` — landmarks.npz URL + summary.
- `GET    /v1/words/{word}/samples/{sample_id}/videoClipUrl` — pre-signed clip [start,end].
- `POST   /v1/words/{word}/templates:rebuild` — пересобрать шаблон (model_admin).

### Decisions
- `GET /v1/decisions/{decision_id}` — full decision + evidence timeline.
- `GET /v1/decisions/{decision_id}/landmarkClip` — синхронизированные клипы по фразам.
- `GET /v1/decisions?jobId=...` — decisions by job.

### Reviews
- `POST /v1/reviews` — записать ревью (decision_id, verdict, reason).
- `GET  /v1/reviews?verdict=...&reviewerId=...` — список.
- `GET  /v1/reviews/{review_id}` — детально.

### Models
- `GET    /v1/models` — registry.
- `GET    /v1/models/{model_id}` — checksum, schema, calibration, metrics.
- `POST   /v1/models/{model_id}:promote` — VALIDATED → SHADOW → ACTIVE.
- `POST   /v1/models/{model_id}:rollback` — switch pointer.
- `POST   /v1/models/{model_id}:retire` — ACTIVE → RETIRED.

### Audit
- `GET /v1/audit?actorId=...&action=...&from=...&to=...&cursor=...` — paginated.
- `GET /v1/audit/export?format=csv|jsonl` — bulk export (auditor only).

### System
- `GET /health/live`, `GET /health/ready`, `GET /metrics`.

## Events (outbox → Redis Streams)

| Event | Producer | Required fields | Consumer |
|---|---|---|---|
| `asset.uploaded.v1` | API | event_id, asset_id, sha256, size, mime | worker (enqueue validation) |
| `asset.imported.v1` | worker (url) | event_id, asset_id, source_url, sha256 | worker (enqueue analysis) |
| `analysis.requested.v1` | API | event_id, job_id, asset_id, claimed_person_id | worker (pipeline) |
| `job.stage.completed.v1` | worker | event_id, job_id, stage, output_ref | internal |
| `landmarks.extracted.v1` | worker | event_id, job_id, sequence_uri, schema_version, quality | next stage |
| `asr.completed.v1` | worker | event_id, job_id, transcript_uri, language | next stage |
| `decision.created.v1` | worker | event_id, decision_id, job_id, label, model_version | API read model |
| `review.created.v1` | API | event_id, review_id, decision_id, verdict, reviewer_id | baseline aggregator |
| `phrase.template.built.v1` | worker (baseline) | event_id, word, template_id, version, n_samples | API read model |
| `model.promoted.v1` | API | event_id, model_id, from_state, to_state, actor_id | audit |

Breaking change → новое имя/версия. Consumer игнорирует неизвестные optional поля и reject'ит отсутствующие required.

## Pagination
```json
{
  "items": [...],
  "nextCursor": "eyJjcmVhdGVkQXQiOiIyMDI2Li4uIiwiaWQiOiIuLi4ifQ==",
  "totalEstimate": 1234
}
```

## Cursor encoding
- Base64URL(JSON({ "createdAt": "2026-07-30T12:00:00Z", "id": "uuid" })).
- `limit` default 50, max 200.
