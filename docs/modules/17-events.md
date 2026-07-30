# Module 17: Outbox + event streaming

**Путь:** `services/api/app/events/` + `services/api/app/workers/outbox_relay.py`
**Backend:** PostgreSQL outbox → Redis Streams

## Файлы

### `outbox.py`
```python
"""
MG-STUB: реализовать:
- OutboxRepository:
    - create(session, event_name, payload, correlation_id) -> OutboxEvent
        # вызывается ВНУТРИ доменной транзакции
    - claim_unpublished(limit=100) -> list[OutboxEvent]
        # SELECT ... FOR UPDATE SKIP LOCKED
    - mark_published(id)
    - increment_attempts(id, error)
"""
```

### `publisher.py`
```python
"""
MG-STUB: реализовать:
- EventPublisher:
    - async publish_to_stream(stream_name, event_name, payload, correlation_id)
        # Redis Streams XADD
        # payload включает {event_id, occurred_at, event_name, data}
    - async publish_all_pending(): poll outbox, publish, mark_published
        # идемпотентно по event_id
"""
```

### `outbox_relay.py` (worker)
```python
"""
MG-STUB: реализовать:
- OutboxRelay (dramatiq actor):
    - loop every 200ms:
        pending = claim_unpublished(limit=200)
        for ev in pending:
            try: publish_to_stream(...)
            except: increment_attempts; if attempts > 10: dead-letter
            mark_published(ev.id)
- LISTEN/NOTIFY: optional, для снижения latency до <10ms.
"""
```

## Event envelope (canonical)
```json
{
  "event_id": "uuid",
  "event_name": "decision.created.v1",
  "event_version": 1,
  "occurred_at": "2026-07-30T12:00:00Z",
  "tenant_id": "uuid",
  "correlation_id": "uuid",
  "actor_id": "uuid|null",
  "data": { ... event-specific ... }
}
```

## Stream naming
- `mimicguard.events` — единый stream для всех событий.
- Consumer groups: `worker-pipeline`, `api-readmodel`, `baseline-aggregator`.

## Consumer idempotency
- Каждый consumer ведёт таблицу `processed_events(event_id PK, consumer_group, processed_at)`.
- На входе — `INSERT ... ON CONFLICT DO NOTHING`; если affected rows = 0, skip.
