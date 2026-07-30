# Runbook: Storage quota exceeded

## Симптомы
- Алерт `StorageQuotaHigh` (tenant > 80% от лимита).
- S3 API возвращает 403 SlowDown / InsufficientStorage.

## Диагностика

```bash
# 1. Размер по тенантам
psql -c "SELECT tenant_id, sum(bytes) FROM storage_usage GROUP BY 1 ORDER BY 2 DESC LIMIT 20;"

# 2. S3 bucket size
aws s3api list-objects-v2 --bucket mimicguard-videos --query 'sum(Contents[].Size)'
```

## Митигация

1. **Operator UI → Settings → Retention** — перевести raw video в cold tier (Glacier / Infrequent Access).
2. **Почистить orphaned assets** без связанных job'ов старше 30 дней.
3. **Связаться с тенантом** — upgrade plan или удалить старые видео.
4. **Если всё равно превышение:** новые uploads получают 507 Insufficient Storage до решения.

## Предотвращение
- Per-tenant quota check в API перед prepareUpload.
- Lifecycle policy: raw video → IA через 30 дней → Glacier через 90 дней.
- Derived landmarks (landmarks.npz) — отдельный bucket с агрессивной lifecycle.
- Еженедельный отчёт по storage growth.
