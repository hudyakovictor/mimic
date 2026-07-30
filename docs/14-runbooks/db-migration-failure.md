# Runbook: DB migration failure

## Симптомы
- `alembic upgrade head` упал в staging или prod.
- API возвращает 500 на endpoints, использующих новые колонки.

## Диагностика

```bash
# Текущая ревизия
alembic current

# История
alembic history --verbose

# Лог конкретной миграции
psql -c "SELECT * FROM alembic_version;"
psql -c "SELECT pid, query, state FROM pg_stat_activity WHERE state='active' AND query LIKE '%alembic%';"
```

## Типовые причины
1. **Lock timeout** — долгая транзакция блокирует ALTER TABLE.
2. **Out of disk** — недостаточно места для нового индекса.
3. **Constraint violation** — данные в проде не соответствуют новому constraint.
4. **Network blip** во время миграции.

## Митигация

1. **Lock timeout:**
   ```sql
   -- Найти и остановить блокирующую транзакцию
   SELECT pg_cancel_backend(pid);
   ```
2. **Out of disk:** расширить volume, повторить.
3. **Constraint violation:** исправить данные (миграция должна это делать сама в data-migration блоке, отдельный коммит).
4. **Network blip:** перезапустить миграцию — Alembic идемпотентен по версии.

## Rollback

```bash
alembic downgrade -1
```

**Если downgrade невозможен (data loss):**
1. Остановить API.
2. Восстановить из PITR.
3. Исправить миграцию, повторить.

## Предотвращение
- Миграции идут в CI против ephemeral БД с реальным дампом prod (sanitized).
- Долгие миграции (> 1 мин) — multi-step с batched UPDATE.
- Каждая миграция имеет и upgrade, и downgrade.
- Сначала staging, потом prod; для prod — manual approval.
