# Module 29: Observability

**Путь:** `services/api/app/observability/` + `services/worker/app/observability/`

## Метрики (Prometheus)

### API
- `http_requests_total{method, path, status}` — counter
- `http_request_duration_seconds{method, path}` — histogram
- `http_requests_in_flight` — gauge
- `db_pool_in_use{role}` — gauge
- `redis_pool_in_use` — gauge
- `outbox_lag_seconds` — gauge
- `outbox_pending_total` — gauge

### Worker
- `worker_jobs_in_flight{stage}` — gauge
- `worker_stage_duration_seconds{stage, outcome}` — histogram
- `worker_retry_total{stage, reason}` — counter
- `worker_dlq_total{stage}` — counter
- `landmarks_extraction_fps` — gauge
- `quality_rejection_total{code}` — counter
- `decisions_total{label, model_version}` — counter
- `phrase_templates_total` — gauge
- `phrase_template_samples` — histogram
- `model_drift_psi{feature}` — gauge

## Structured logging
- structlog JSON renderer.
- Обязательные поля в каждой записи: `ts`, `level`, `event`, `correlation_id`, `tenant_id`, `service`.
- Biometric data НИКОГДА не логируется.

## Tracing
- OpenTelemetry SDK, OTLP exporter → Tempo/Jaeger.
- Auto-instrumentation: FastAPI, SQLAlchemy, Redis, httpx.
- Custom spans: pipeline stages.
- Sampling: head 5% + tail-based 100% on errors.

## Health endpoints
- `GET /health/live` — 200 always.
- `GET /health/ready` — checks PostgreSQL, Redis, MinIO.

## Dashboards (Grafana JSON)
- `infra/observability/dashboards/overview.json`
- `infra/observability/dashboards/pipeline.json`
- `infra/observability/dashboards/quality.json`
- `infra/observability/dashboards/models.json`

## Alert rules
- `infra/observability/alerts/job-stuck.yaml`
- `infra/observability/alerts/worker-dlq.yaml`
- `infra/observability/alerts/quality-spike.yaml`
- `infra/observability/alerts/model-drift.yaml`
- `infra/observability/alerts/outbox-lag.yaml`

## Что НЕ делается
- Никаких биометрических данных в логах/метриках/трейсах.
- Никаких персональных email/имён в логах — только IDs.
