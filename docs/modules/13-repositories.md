# Module 13: Repositories

**Путь:** `services/api/app/repositories/`
**Назначение:** Data access layer с tenant scoping.

## Conventions
- Каждый repository — класс с `__init__(self, session: AsyncSession)`.
- Все query methods принимают `tenant_id` явно (не из контекста) для тестируемости.
- SQLAlchemy `select()` + `result.scalars().all()`.
- `tenant_id` filter добавляется в `before_compile` event listener.
- N+1 избегаем через `selectinload` / `joinedload`.

## Файлы

### `base.py`
```python
"""
MG-STUB: реализовать:
- BaseRepository[T] generic class:
    - get(id, tenant_id) -> T | None
    - list(filters, cursor, limit, tenant_id) -> tuple[list[T], next_cursor | None]
    - create(entity) -> T
    - update(id, tenant_id, version_expected, **fields) -> T
        - optimistic concurrency: WHERE version = :v
        - если 0 rows: raise ConflictError
    - delete_soft(id, tenant_id) -> T   # для subject tombstone
- PaginationCursor: encode/decode (base64url JSON {created_at, id}).
"""
```

### `users.py`
- `get_by_email(email, tenant_id)`, `create(email, password_hash, roles)`.

### `subjects.py`
- `create`, `get`, `list`, `update` (с consent), `get_baselines(subject_id)`.

### `assets.py`
- `create_pending(tenant_id, uploaded_by, source_type, mime, size, ...)`, `mark_ready(id, sha256, ...)`, `mark_failed(id, reason)`, `list(filters)`.

### `analysis_jobs.py`
- `create_or_get_idempotent(asset_sha256, subject_id, pipeline_version)` — если есть, вернуть существующий.
- `get`, `list(filters)`, `transition_state(id, from_state, to_state)` — проверяет текущее состояние.
- `record_stage(job_id, name, state, ...)`.

### `decisions.py`
- `create(...)` — append-only, без update.
- `get(id, tenant_id)`.
- `list_by_job(job_id)`.

### `reviews.py`
- `create(decision_id, reviewer_id, verdict, reason, confidence)` — append-only.
- `list(filters)`.

### `phrase_templates.py`
- `get_latest(subject_id, word, language)`.
- `get_version(id)`.
- `list_for_word(word, language)`.
- `create(...)` — immutable, новый row каждый раз.

### `phrase_samples.py`
- `create(...)` — immutable.
- `list_for_template(template_id)`.

### `model_versions.py`
- `create(kind, version, ...)`, `get(id)`, `list_active(kind)`, `transition_state(id, to_state, actor_id)`, `get_previous_active(kind)`.

### `audit.py`
- `create(...)` — append-only, audit-таблица пишется в той же транзакции что и действие.
- `list(filters)` с cursor pagination.
- `export_to_s3(filters, format)` — отдельный job.

### `outbox.py`
- `create(event_name, payload, correlation_id)` — внутри доменной транзакции.
- `claim_unpublished(limit)` — `SELECT ... FOR UPDATE SKIP LOCKED`.
- `mark_published(id)`.

## Tenant scoping enforcement
- Global event listener:
  ```python
  @event.listens_for(Session, "do_orm_execute")
  def filter_by_tenant(execute_state):
      if not execute_state.is_select: return
      if not execute_state.is_orm_load: return
      # Добавить WHERE tenant_id = :current_tenant
  ```
- Однако для некоторых таблиц (outbox, system events) tenant не нужен — флаг `__no_tenant_filter__`.

## Testing
- Каждый repo — test против ephemeral PostgreSQL.
- Cursor pagination — round-trip test.
- Optimistic concurrency — conflict detection test.
- Tenant isolation — repo из tenant A не видит данные tenant B.
