# Testing strategy

## Test pyramid
- Unit: quality formulas, normalization, state transitions and policy.
- Contract: OpenAPI examples, event compatibility, adapter protocols.
- Integration: PostgreSQL/outbox, object storage and queue idempotency.
- Golden video: fixed assets with expected landmark schema and quality metrics.
- Model evaluation: subject/session/device-disjoint splits and calibration.
- UI: component states, keyboard flow and Playwright reviewer journey.
- Security: authorization matrix, tenant isolation and malicious uploads.
- Load: queue burst, long video and worker restart.

## Release gates
No placeholder adapter may be silently selected. All `MG-STUB` references are inventoried. Model checksum/schema must match. Migrations roll forward/back in a staging copy. Accessibility reaches WCAG AA for primary workflows.
