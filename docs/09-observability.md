# Observability and SLO

## SLOs

| SLO | Target | Measurement |
|---|---|---|
| API availability | 99.9% monthly | uptime / total |
| p95 job registration | < 400 ms (excl. upload) | histogram |
| Accepted 10-min assets complete ≤ 5 min | 95% | counter / total |
| Operational failure after retry | < 1% | DLQ / total |
| Decision reproducibility | 100% | по чек-суммам |
| Reviewer decision time | < 2 мин p50 | UI telemetry |

## Signals

### Metrics (Prometheus, namespace `mimicguard_`)
- `api_request_duration_seconds{path, method, status}` — histogram.
- `analysis_jobs_created_total{tenant}` — counter.
- `analysis_jobs_in_state{state}` — gauge.
- `analysis_job_duration_seconds{stage}` — histogram.
- `landmarks_extraction_fps` — gauge.
- `quality_rejection_total{code}` — counter.
- `decisions_total{label, model_version}` — counter.
- `review_agreement_total{verdict, predicted_label}` — counter.
- `worker_retry_total{stage, reason}` — counter.
- `worker_dlq_total{stage}` — counter.
- `storage_bytes{tenant, kind}` — gauge.
- `outbox_lag_seconds` — gauge.
- `phrase_template_size{word}` — gauge (для drift detection).
- `model_drift_psi{feature}` — gauge (population stability index).

### Logs (structlog, JSON)
- Каждое событие: `ts`, `level`, `correlation_id`, `tenant_id`, `actor_id?`, `job_id?`, `stage?`, `event`.
- **Никогда** не логируем raw landmarks, video URL без подписи, biometric vectors.
- PII redaction: имена файлов хешируются, пути маскируются.

### Traces (OpenTelemetry)
- `api.request → outbox.publish → worker.consume → stage.* → db.commit`.
- Sampling: head 5% + tail-based по errors + 100% для INSUFFICIENT_DATA (редкое событие).
- Span attributes: `tenant_id`, `job_id`, `model_version`, без PII.

### Alerts (burn-rate windows)
- `JobStuckP95High`: 1h burn rate > 14.4 (1% budget за 1h).
- `WorkerDLQGrowing`: 5m rate > 5.
- `QualityRejectionSpike`: 5m rate > 3 × 7d avg.
- `OutboxLag`: lag > 60s в течение 5m.
- `ModelDrift`: PSI > 0.2 в течение 24h.

## Model monitoring
Раздельно:
- **Input quality drift** — доля INSUFFICIENT_DATA по каждому evidence code.
- **Feature drift** — PSI/KS-test по региональным ratios, раз в сутки.
- **Calibration drift** — Brier score / ECE на reviewed-выборке за последние 7 дней.
- **Reviewer disagreement** — inter-annotator agreement (Cohen's κ), weekly report.

## Dashboards (Grafana)
1. **Overview** — system health, SLO budget.
2. **Pipeline** — per-stage latency, retry, DLQ.
3. **Quality** — rejection by code, top subjects.
4. **Models** — drift, calibration, promotion history.
5. **Storage** — bytes per tenant, growth rate.

## Logging rules
- Access log: nginx JSON.
- App log: stdout (12-factor), собирается Promtail/Fluentd.
- Уровни: ERROR (page), WARN (digest), INFO (default), DEBUG (off в проде).
