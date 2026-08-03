# Local development

## Toolchain
- **Python** 3.11+ (3.12 LTS)
- **uv** для dependency management
- **Node.js** 22 LTS
- **pnpm** 9+
- **Docker Desktop / OrbStack / Colima** (Apple Silicon native)
- **ffmpeg** 6+ (`brew install ffmpeg`)
- **MediaPipe Tasks model** — `face_landmarker.task` (скачивается автоматически при первом запуске)

## Apple Silicon notes
- MediaPipe имеет native arm64 wheel — без Rosetta.
- faster-whisper использует CTranslate2 + Metal (по умолчанию CPU small model, GPU optional).
- OpenCV — `opencv-python-headless` для экономии (без Qt).

## Quickstart

```bash
git clone <repo>
cd mimic

# Backend
uv sync --all-extras
cp .env.example .env
# отредактируйте .env (JWT_SECRET, S3 keys, etc)

# Запуск инфраструктуры
docker compose -f infra/docker-compose.yml up -d postgres redis minio

# Миграции
uv run alembic upgrade head

# Seed
uv run python -m scripts.seed

# API
uv run uvicorn services.api.app.main:app --reload --port 8080

# Worker (в другом терминале)
PYTHONPATH=services/api:services/worker:. uv run dramatiq worker.__main__ -p 1 -t 4

# Frontend
pnpm --dir apps/admin install
pnpm --dir apps/admin dev  # http://localhost:5173
```

## Тесты

```bash
# Backend
uv run pytest -q
uv run ruff check .
uv run mypy services packages

# Frontend
pnpm --dir apps/admin lint
pnpm --dir apps/admin typecheck
pnpm --dir apps/admin test
pnpm --dir apps/admin e2e  # playwright
```

## Генерация типов

```bash
# Из OpenAPI → TypeScript
uv run python -m scripts.gen_types
```

## Полезные команды

```bash
# Очистить DLQ
uv run python -m scripts.drain_dlq --stage extract_landmarks

# Загрузить golden fixture
uv run python -m scripts.load_golden tests/fixtures/golden/interview_5s.mp4

# Просмотреть логи worker
docker compose -f infra/docker-compose.yml logs -f worker

# Войти в psql
docker compose -f infra/docker-compose.yml exec postgres psql -U mimicguard mimicguard
```
