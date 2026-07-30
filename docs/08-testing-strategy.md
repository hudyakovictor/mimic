# Testing strategy

## Test pyramid

### Unit (>= 80% coverage на packages/)
- quality.py, normalization.py
- state machine transitions (analysis job, model version, review)
- tenant scoping в repositories
- RBAC permission matrix
- evidence score aggregation
- DTW implementation
- Mahalanobis distance

### Property-based (hypothesis)
- `normalize_sequence` round-trip property
- DTW distance symmetry, triangle inequality (приблизительная)
- quality thresholds — монотонность (больше frames → выше score, при прочих равных)

### Contract
- OpenAPI examples (Schemathesis) — каждый endpoint имеет минимум 3 примера (200, 4xx, 5xx).
- Event compatibility: pydantic-based decoder test.
- Adapter protocols: `LandmarkExtractor`, `MotionScorer`, `AsrEngine`, `StorageClient`.

### Integration
- PostgreSQL: repository тесты против ephemeral schema (pytest-postgresql).
- MinIO: pre-signed upload + download round-trip.
- Redis Streams: producer + consumer + DLQ.
- Outbox: транзакционная запись + relay.
- Worker stages: end-to-end на синтетическом 10-сек видео.

### Golden video
- `tests/fixtures/golden/` — набор коротких видео (5–10 сек) с известным ground-truth landmarks.
- Адаптер должен воспроизводимо давать landmarks с tolerance ≤ 1px.
- Один golden для каждой evidence-категории (suspect motion, good, too low quality).

### Model evaluation
- Splits по `(subject, session, device)` — disjoint.
- Метрики: false acceptance rate, false rejection rate, AUC, calibration (Brier score, ECE).
- Confidence intervals через bootstrap (1000 итераций).
- Запрещено оптимизировать accuracy в ущерб calibration.

### UI
- React Testing Library: компонентные тесты на каждое состояние.
- Playwright: reviewer journey (create review с подтверждением), keyboard navigation.
- Visual regression через Percy/Chromatic (опционально).
- Lighthouse a11y в CI.

### Security
- IDOR matrix: каждый endpoint, каждый tenant — должно быть 403.
- Malicious upload tests (zip bomb, malformed MP4, oversized).
- JWT tampering, expired, wrong audience.
- Tenant-isolation в SQL: прямой SQL-инъекцией мимо ORM.

### Load
- Locust: 100 RPS на `/v1/analysis-jobs` create, проверка p95 < 400 ms.
- Worker: 50 одновременных 10-мин видео — укладываемся в 5 мин/видео на M2 Pro.

## Coverage targets
- packages/landmark_engine: ≥ 95%
- services/api: ≥ 85%
- services/worker: ≥ 80%
- apps/admin: ≥ 70% (pages, ключевые features)

## Release gates
- Нет placeholder adapter в проде: `tools/check_stubs.py` в CI.
- Все `MG-STUB` ссылки инвентаризированы.
- Model checksum/schema совпадают с проверенным.
- Migrations катятся вперёд и назад в staging.
- Accessibility WCAG AA для primary workflows.
- Никаких TODO с приоритетом P0 в коде.
