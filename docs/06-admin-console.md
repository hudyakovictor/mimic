# React administration console

## Information architecture
- Overview: system health and workload.
- Analyses: searchable queue and saved filters.
- Analysis detail: quality, decision, evidence timeline, feature preview.
- Subjects: profile and approved baseline versions.
- Reviews: pending and completed human decisions.
- Models: deployed version, drift and rollback controls.
- Audit/settings: role-restricted.

## UX rules
- Never show risk without quality.
- Never use color as the only status cue.
- `INSUFFICIENT_DATA` is visually distinct from low risk.
- Raw video access is permissioned and audited.
- Destructive/model promotion actions require confirmation and reason.
- Empty, loading, stale, partial and error states are first-class components.

## Frontend architecture
Route-level features own queries and forms. Shared UI contains no domain fetches. API calls go through one typed client. Server state uses React Query; local UI state stays local. Zod validates untrusted responses until generated runtime schemas are adopted.
