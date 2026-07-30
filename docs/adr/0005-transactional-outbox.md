# ADR 0005: Transactional outbox

**Status:** Accepted.

## Context
Worker должен получать события о новых job'ах. API не должен делать `await queue.publish()` после `await db.commit()` — между ними возможен краш, и событие потеряется. Двухфазный коммит между PostgreSQL и Redis — это сложно и не гарантирует atomicity.

## Decision
**Transactional outbox**:
1. В одной транзакции с доменным изменением пишем запись в `outbox_events` (с `payload`, `event_name`, `published_at=NULL`).
2. Отдельный relay-процесс (PostgreSQL LISTEN/NOTIFY + polling fallback) подхватывает новые строки и публикует в Redis Streams.
3. После успешной публикации — `UPDATE outbox_events SET published_at = NOW()`.

## Consequences
**Плюсы:** exactly-once-ish (at-least-once с idempotency key на consumer), no 2PC, simple.
**Минусы:** eventual consistency (latency ~50 ms), relay — single point of failure (mitigated: replicate).

## Consumer idempotency
Каждый consumer хранит `processed_event_ids` (или unique key от payload) в БД / Redis SET. Повторное событие — ignore.

## Schema
```sql
CREATE TABLE outbox_events (
  id UUID PRIMARY KEY,
  event_name VARCHAR(128) NOT NULL,
  payload JSONB NOT NULL,
  correlation_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  published_at TIMESTAMPTZ,
  attempts INT NOT NULL DEFAULT 0,
  last_error TEXT
);
CREATE INDEX outbox_unpublished ON outbox_events(created_at) WHERE published_at IS NULL;
```
