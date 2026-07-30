# Module 30: Periodic scheduler

**Путь:** `services/scheduler/`
**Библиотека:** APScheduler 3.x (in-process) или отдельный worker с cron.

## Задачи

### 1. `recalculate_storage_usage` (every 6h)
- `SELECT tenant_id, sum(size_bytes) FROM assets GROUP BY tenant_id`
- Записать в `storage_usage` table.

### 2. `expire_pending_uploads` (every 1h)
- `UPDATE assets SET state='FAILED' WHERE state='PENDING_UPLOAD' AND created_at < NOW() - INTERVAL '24 hours'`

### 3. `enforce_retention_policies` (daily at 03:00 UTC)
- Для каждой tenant: применить retention policy.
- Удалить raw video старше retention_days.
- Лог audit 'retention.enforce'.

### 4. `cleanup_dlq` (hourly)
- Старые DLQ сообщения (старше 7 дней) → переместить в `dlq_archive` table для анализа.

### 5. `drift_detection` (daily at 04:00 UTC)
- Для каждой ACTIVE model:
  - вычислить PSI по 5 фичам на reviewed-выборке за последние 7 дней.
  - записать в `model_drift` table.
  - если PSI > 0.2 — emit event + alert.

### 6. `calibration_check` (weekly, Sunday 05:00 UTC)
- Brier score + ECE на reviewed-выборке за 7 дней.
- записать в `model_metrics` table.

### 7. `reviewer_agreement_report` (weekly, Monday 06:00 UTC)
- Cohen's κ по всем reviewer pairs за 7 дней.
- Записать в `reviewer_metrics`.

### 8. `audit_export_archival` (monthly)
- Audit events старше 90 дней → сжать в `audit_archive` (S3 + Glacier).
