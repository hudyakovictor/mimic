# ADR 0001: Modular monolith control plane

**Status:** Accepted.

## Context
Нужно с чего-то начать production-ready проект, не уходя в микросервисный ад с distributed transactions. У нас тяжёлый CPU-bound worker (MediaPipe + faster-whisper), который нужно изолировать от HTTP.

## Decision
Один FastAPI deployment со строгими модулями (routers, services, repositories) + отдельный worker pool. Модули можно вынести в отдельные сервисы позже, если потребуется (workload, team ownership, security).

## Consequences
**Плюсы:** простые транзакции, один деплоймент, легко отлаживать, нет distributed tracing overhead.
**Минусы:** single point of failure для API; масштабирование all-or-nothing; требует дисциплины в module boundaries.

## Notes
- Module boundary — это import boundary: routers не импортируют друг друга; services не импортируют routers.
- DB connection pool: max 20 per pod, max 100 total.
- Если API растёт > 100 RPS — read replicas, не выделение модулей.
