# MimicGuard

**Система выявления несоответствия динамики лица заявленного человека его верифицированному motion-baseline** — для low-quality видео (webcams, телефоны, плохое освещение, сжатие). Цель — помощь ревьюеру в выявлении случаев, когда среди видео находится человек в силиконовой маске, у которого мимика отличается от baseline-человека.

> **v1 использует только семантические landmarks лица (MediaPipe Face Mesh) и их временные производные.** Это не универсальный детектор масок — это инструмент, который:
> 1. Накапливает verified-прогоны произнесённых слов;
> 2. Сравнивает новое видео с baseline-человеком по каждому слову;
> 3. Выдаёт evidence (DTW, Mahalanobis, phase delay, slope);
> 4. Позволяет ревьюеру side-by-side сравнить 2-4 прогона с overlay landmarks.

## Архитектура

```
React Admin (apps/admin)  ──►  FastAPI (services/api)  ──►  PostgreSQL
                                                              │
                                                              ▼
                              Redis Streams  ◄──────────  dramatiq worker
                                                              │
                                                              ▼
                              MinIO/S3  ◄────────────  landmarks.npz, видео
```

- **Backend:** FastAPI (Python 3.12) + SQLAlchemy 2.0 async + Alembic.
- **Worker:** dramatiq + Redis Streams.
- **ML:** MediaPipe Face Mesh (478 точек), faster-whisper (ASR), DTW + Mahalanobis (статистический baseline).
- **Frontend:** React 19.2 + Vite 8 + TypeScript + TanStack Query + Zod.
- **Storage:** S3-совместимый (MinIO в dev).

## Возможности

- Загрузка видео (файл, прямая mp4-ссылка, YouTube через yt-dlp).
- Обязательный экран выбора 1–20 полезных участков после загрузки; фрагменты запускаются параллельно.
- Длинный исходник по умолчанию удаляется только после успешной frame-accurate нарезки в analysis-safe H.264 CRF 17.
- Пайплайн из 6 стадий: validate → extract_landmarks → quality_gate → asr → align → match_baseline.
- Накопительная база слов/словосочетаний: каждое CONFIRMED_GENUINE ревью инкрементит версию шаблона (DTW + Mahalanobis по региональным фичам).
- **Canvas-overlay синхронный просмотр** 1-4 видео с overlay landmarks (MediaPipe Face Mesh skeleton + точки) — на странице сравнения анализа и на странице сравнения прогонов слова.
- RBAC (5 ролей), audit log, JWT auth, rate limiting.
- Model registry с promotion/rollback.
- Observability: Prometheus metrics, OpenTelemetry traces, structured JSON logs.
- Docker-compose для dev (Postgres + Redis + MinIO + API + worker + Prometheus + Grafana).

## Запуск

Виртуальное окружение: `.venv` (Python 3.12).

```bash
# 1. Зависимости
uv venv .venv --python 3.12
uv sync --all-extras
cd apps/admin && pnpm install && cd ../..

# 2. Переменные окружения
cp .env.example .env
# (опционально: измените JWT_SECRET, S3 keys, и т.д.)

# 3. Инфраструктура
docker compose -f infra/docker-compose.yml up -d postgres redis minio

# 4. Миграции и seed
uv run --directory services/api alembic upgrade head
uv run --directory services/api python -m scripts.seed

# 5. API
uv run --directory services/api uvicorn app.main:app --reload --port 8080

# 6. Worker (в другом терминале)
PYTHONPATH=services/api:services/worker:. uv run dramatiq worker.__main__ -p 2 -t 4

# 7. Frontend
cd apps/admin && pnpm dev   # http://localhost:5173
```

Default admin: `admin@example.com` / `change-me-now-12chars`.

## Структура проекта

```
mimic/
├── apps/
│   └── admin/                  React 19 + TS админка
│       ├── src/
│       │   ├── pages/          16 страниц (Dashboard, Analyses, Words, Phrases, ...)
│       │   ├── components/     UI компоненты
│       │   │   └── SyncPlayer  Canvas-overlay синхронный плеер
│       │   ├── api/            Typed HTTP client + Zod schemas
│       │   ├── stores/         Zustand (auth, toasts)
│       │   └── styles/         CSS (light/dark, a11y)
├── services/
│   ├── api/                    FastAPI application
│   │   ├── app/
│   │   │   ├── routers/        11 routers, ~40 endpoints
│   │   │   ├── services/       Application services (auth, jobs, assets, words, reviews, baseline aggregator)
│   │   │   ├── repositories/   SQLAlchemy repositories с tenant scoping
│   │   │   ├── db/             Models + session management
│   │   │   ├── security/       JWT, passwords, RBAC
│   │   │   ├── storage/        S3 client, key generators
│   │   │   ├── events/         Outbox + Redis publisher
│   │   │   └── observability/  Logging, metrics, tracing
│   │   └── alembic/            Migrations
│   └── worker/                 dramatiq worker
│       └── app/
│           ├── actors/         Pipeline actor (6 stages)
│           ├── landmarks/      MediaPipe Face Mesh
│           ├── asr/            faster-whisper
│           ├── phoneme/        Word-to-landmark alignment
│           ├── baseline/       DTW + Mahalanobis
│           └── video/          ffmpeg probe + decode
├── packages/
│   ├── landmark_engine/        Framework-independent domain (LandmarkFrame, NormalizedSequence, QualityAssessment)
│   └── contracts/              OpenAPI + event schemas
├── docs/                       Полная документация
│   ├── 01-14                   Vision, design, operations
│   ├── adr/                    Architectural decision records
│   ├── modules/                Спецификации каждого модуля с заглушками
│   └── 14-runbooks/            Incident runbooks
├── infra/                      Docker, Prometheus
├── scripts/                    seed.py
└── Makefile                    bootstrap, dev, test, lint, typecheck
```

## Тестирование

```bash
# Backend
uv run --directory services/api pytest -q ../..
uv run --directory services/api ruff check .
uv run --directory services/api mypy app packages

# Frontend
cd apps/admin && pnpm typecheck && pnpm lint
```

## Документация

- `docs/01-product-scope.md` — что делаем / не делаем.
- `docs/02-architecture.md` — модульный монолит + worker.
- `docs/04-landmark-pipeline.md` — пайплайн landmarks.
- `docs/modules/` — спецификации модулей (включая заглушки с подробными docstring).
- `docs/14-runbooks/` — incident runbooks.
- `docs/quality-scorecard.md` — 50-факторный scorecard.
- `docs/adr/` — architectural decision records.

## Лицензия
TBD (internal).
