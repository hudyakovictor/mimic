# Local development

## Toolchain
Python 3.11+, uv, Node 22+, pnpm, Docker Desktop/Colima. Apple Silicon is the primary target.

```bash
uv sync --all-extras
pnpm --dir apps/admin install
cp .env.example .env
docker compose -f infra/docker-compose.yml up -d postgres redis minio
uvicorn services.api.app.main:app --reload --port 8080
pnpm --dir apps/admin dev
```

The API composition root is intentionally a stub until repositories/migrations are implemented. Health endpoint and pure landmark unit tests are runnable independently.
