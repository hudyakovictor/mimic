# Implementation roadmap

Итерации идут последовательно. **Definition of Done** для каждой итерации.

## Iteration 1 — Operational spine (Week 1)
- Alembic миграции + сидинг.
- Репозитории с tenant scoping.
- Outbox + relay.
- Upload lifecycle (presigned + complete).
- JWT auth + RBAC.
- Job queue + worker skeleton.
- Admin list/detail states с React Query.
- `tools/check_stubs.py` в CI.
- Health/ready endpoints, prometheus metrics.
- docker-compose для dev.

**DoD:** можно загрузить видео, создать job, видеть status без ML. Никаких fake-scorer.

## Iteration 2 — Deterministic landmarks (Week 2)
- Golden fixtures в `tests/fixtures/golden/`.
- MediaPipe Face Mesh adapter (полный, с tracking).
- Quality dashboard.
- Нормализация + 3D head-pose correction.
- Normalized feature storage в S3.
- Reproducibility report.

**DoD:** landmarks из golden видео воспроизводимы ≤ 1px tolerance; quality метрики в UI.

## Iteration 3 — ASR + baseline + scoring (Week 3)
- faster-whisper adapter.
- Word-level alignment.
- PhraseInstance extraction.
- DTW + Mahalanobis distance.
- PhraseTemplate aggregation (атомарно при CONFIRMED_GENUINE).
- Decision + evidence pipeline.
- Reviewer workflow.
- Words/Phrases pages в админке.

**DoD:** end-to-end pipeline на golden видео; слова накапливаются; ревьюер может подтвердить/отвергнуть.

## Iteration 4 — Visual comparator (Week 4)
- SyncPlayer компонент с canvas-overlay.
- `requestVideoFrameCallback` оптимизация.
- PhraseComparePage: до 4 прогонов side-by-side.
- Drawing landmarks поверх video (model-view matrix).
- Keyboard shortcuts.
- Запись baseline клипов в S3 при confirmed.

**DoD:** ревьюер может одновременно смотреть 4 verified-прогона слова с overlay и слышать/видеть.

## Iteration 5 — Hardening (Week 5)
- Полный audit log.
- Model registry с promotion/rollback.
- Drift monitoring (PSI, calibration).
- Alembic downgrade paths.
- Load tests (Locust).
- Security tests (IDOR matrix, malicious upload).
- A11y pass.
- Runbooks.

**DoD:** release-ready v1.0.0; все 50 scorecard факторов ≥ 1.

## Definition of Done (универсальный)
- Code + tests + migration + OpenAPI update + observability (metrics/logs) + security review + runbook + rollback + data-retention impact.
- Demo-реализация не может быть promoted.
- Все stub-функции либо реализованы, либо явно `raise NotImplementedError("MG-STUB: …")` с docstring-инструкцией.
