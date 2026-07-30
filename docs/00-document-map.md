# Documentation map

> Документация разделена на 4 слоя: **vision** (что и зачем), **design** (как устроено), **operations** (как запускать/поддерживать) и **module specs** (полное описание каждого модуля с заглушками функций).

## Vision
- `01-product-scope.md` — что делаем, чего не делаем, метрики успеха
- `quality-scorecard.md` — 50-факторный чек-лист архитектуры

## Design
- `02-architecture.md` — модульный монолит + изолированный worker
- `03-domain-model.md` — сущности, инварианты, стейт-машина
- `04-landmark-pipeline.md` — пайплайн landmarks, evidence-коды
- `05-api-and-events.md` — REST и события
- `06-admin-console.md` — информационная архитектура админки
- `07-security-and-privacy.md` — биометрия, RBAC, retention
- `10-ml-governance.md` — версионирование моделей, drift, rollback
- `adr/0001-modular-monolith.md` — почему модульный монолит
- `adr/0002-landmarks-only.md` — почему только landmarks
- `adr/0003-statistical-baseline.md` — почему DTW + Mahalanobis для v1
- `adr/0004-canvas-overlay-comparator.md` — почему canvas-overlay для визуального сравнения
- `adr/0005-transactional-outbox.md` — почему outbox вместо двухфазного коммита

## Operations
- `08-testing-strategy.md` — пирамида тестов, golden-видео
- `09-observability.md` — SLO, метрики, логи, трейсы
- `11-local-development.md` — запуск на Apple Silicon / Linux
- `12-implementation-roadmap.md` — порядок реализации
- `13-deployment.md` — production deployment
- `14-runbooks/` — incident runbooks
  - `worker-stuck.md`
  - `model-drift.md`
  - `storage-quota.md`
  - `db-migration-failure.md`
  - `auth-outage.md`

## Module specs (полные описания заглушек)
> Каждый модуль имеет точное описание функции, её сигнатуру, контракт ввода-вывода, expected exceptions, и подсказки для финальной реализации. Программист, получивший только каркас, может реализовать каждый модуль **без дополнительных уточнений**.

### Backend (Python)
- `modules/10-api.md` — FastAPI composition root, middlewares, exceptions
- `modules/11-routers.md` — все REST endpoints с примерами
- `modules/12-domain.md` — сущности SQLAlchemy, value objects
- `modules/13-repositories.md` — паттерны доступа к данным
- `modules/14-services.md` — application services, use-cases
- `modules/15-security.md` — JWT, RBAC, audit
- `modules/16-storage.md` — S3-совместимое хранилище (MinIO)
- `modules/17-events.md` — outbox + Redis Streams
- `modules/20-worker.md` — worker orchestration, retry, DLQ
- `modules/21-video-ingest.md` — загрузка, валидация, YouTube import
- `modules/22-landmark-extractor.md` — MediaPipe Face Mesh adapter
- `modules/23-normalization.md` — pose/3D нормализация
- `modules/24-quality.md` — quality gates
- `modules/25-asr.md` — faster-whisper транскрипция
- `modules/26-phoneme-aligner.md` — выравнивание слов на таймлайн
- `modules/27-baseline-store.md` — DTW + Mahalanobis, хранение шаблонов
- `modules/28-decision-engine.md` — финальное решение и evidence
- `modules/29-observability.md` — Prometheus, OpenTelemetry, structured logs
- `modules/30-scheduler.md` — периодические задачи

### Frontend (React)
- `modules/40-frontend-architecture.md` — слои, state management
- `modules/41-api-client.md` — typed client, React Query, Zod
- `modules/42-pages.md` — каждая страница: цели, состояния, доступ
- `modules/43-comparator.md` — canvas-overlay для синхронного воспроизведения

## Other
- `contracts.md` — как генерируются типы из OpenAPI
