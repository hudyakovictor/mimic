# API and events

The normative HTTP contract is `packages/contracts/openapi.yaml`. Events are in `packages/contracts/events.md`.

## Rules
- UUIDs, UTC RFC3339 timestamps and camelCase on wire.
- Idempotency-Key required for mutation retries in production.
- Error body: `code`, `message`, `correlationId`, optional field errors.
- Cursor pagination; never offset pagination for growing queues.
- Optimistic concurrency (`version`) for mutable configuration.
- Reviews create new records; decisions are never patched.

## Planned endpoints
- assets: prepare upload, complete upload, metadata;
- jobs: create/list/detail/cancel retryable jobs;
- subjects: CRUD metadata, baseline versions;
- decisions: detail and evidence timeline;
- reviews: create/list;
- models: versions, status, promotion/rollback;
- audit: filtered export.

Generate frontend types from OpenAPI; handwritten types in the scaffold are temporary and must be removed when generation is enabled.
