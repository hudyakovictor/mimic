# Contracts and code generation

## OpenAPI → TypeScript types

`packages/contracts/openapi.yaml` — нормативный HTTP-контракт.

```bash
# Генерация TS-типов и Zod-схем
uv run python -m scripts.gen_types
```

Output:
- `apps/admin/src/api/generated/types.ts` — TS-типы.
- `apps/admin/src/api/generated/schemas.ts` — Zod-схемы.

## Events → TypeScript types

`packages/contracts/events.md` + `packages/contracts/events.yaml` (опционально).

```bash
uv run python -m scripts.gen_event_types
```

## Pydantic → JSON Schema

`services/api/app/schemas.py` (Pydantic) — нормативный server-side.

```bash
# FastAPI сам генерирует /openapi.json; используем для TS-генерации.
```

## Convention
- **Single source of truth:** `packages/contracts/openapi.yaml`.
- Никаких ручных правок в `generated/` — они пересоздаются CI.
- Если нужны изменения — правка в OpenAPI → регенерация.
