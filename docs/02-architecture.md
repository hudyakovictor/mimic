# Architecture

## Стиль
Модульный монолит для control plane + изолированный асинхронный worker для CPU-heavy задач. Это 80/20 решение: простые транзакционные границы без связывания HTTP с инференсом.

```
┌─────────────────┐
│  React Admin    │ (apps/admin)
└────────┬────────┘
         │ HTTPS / JSON
┌────────▼────────┐
│  FastAPI API    │ (services/api) — control plane
│  ─────────────  │
│  routers        │  /v1/assets, /v1/jobs, /v1/subjects,
│  services       │  /v1/decisions, /v1/reviews,
│  repositories   │  /v1/models, /v1/audit, /v1/words
│  outbox         │
└─┬──────┬──────┬─┘
  │      │      │
  ▼      ▼      ▼
[PostgreSQL] [MinIO] [Redis]
                  │
                  │ Streams (XADD)
                  ▼
         ┌────────────────────┐
         │  Worker (dramatiq) │
         │  ────────────────  │
         │  video.ingest      │
         │  landmarks.extract │
         │  quality.gate      │
         │  asr.transcribe    │
         │  phoneme.align     │
         │  baseline.match    │
         │  decision.create   │
         └────────────────────┘
```

## Module boundaries
- **Control plane:** auth, RBAC, jobs, subjects, baselines, decisions, reviews, models, audit, read-models.
- **Worker:** media validation, extraction, quality, normalization, ASR, alignment, scoring, decision persistence.
- **Packages (`packages/`):** framework-independent domain-типы и детерминированные трансформации.
- **Adapters:** MediaPipe, faster-whisper, S3, Redis, prom-client, structlog.
- **Admin:** typed API client, React Query, Zod-валидация ответов; никаких ML-расчётов в браузере (кроме визуализации уже посчитанных данных).

## Data ownership
- **PostgreSQL** владеет метаданными и lifecycle. Каждая таблица имеет `tenant_id`, `created_at`, `version` (для optimistic concurrency).
- **MinIO/S3** владеет raw video, derived features (landmarks.npz), шаблонами baseline. Object key = `{tenant}/{subject}/{type}/{uuid}.{ext}`.
- **Модели и калибровка** — immutable objects в отдельном бакете `mimicguard-models/`.
- **Браузер** по умолчанию не получает raw feature arrays — только агрегаты и timeline-точки.

## Reliability
- **Идемпотентность:** job-key = `(asset_sha256, claimed_person_id, pipeline_version)`. Повторный POST = no-op.
- **Stage persistence:** каждый stage пишет результат в `job_stages` ПЕРЕД тем как подтвердить queue message. Retry переиспользует immutable outputs.
- **DLQ:** после 5 retry job уходит в dead-letter queue, оператор видит её в админке.
- **Outbox:** события пишутся в ту же транзакцию, что и доменные изменения; relay публикует их в Redis Streams.

## Scaling
- Workers масштабируются независимо по queue depth.
- Object paths партиционированы по tenant и subject.
- В v1 — один PostgreSQL; read replicas добавляются только при превышении нагрузки.
- Frontend — статический build, CDN-friendly.

## Security boundary
- Все API endpoints за JWT (OIDC в production; HS256 в dev).
- RBAC enforcement в репозиториях через SQLAlchemy event listener (tenant_id filter + role check).
- Raw video доступ только операторам/ревьюерам с правом `video:read`, факт просмотра пишется в audit log.
- Decision и review — append-only. UPDATE/DELETE запрещены на уровне БД (revoke privileges + check constraint + audit trigger).
