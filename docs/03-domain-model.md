# Domain model

| Entity | Purpose | Key invariants |
|---|---|---|
| Tenant | security boundary | all queries tenant-scoped |
| Subject | claimed person | no biometric baseline without consent state |
| Asset | immutable video metadata | SHA-256 unique per tenant; object URI immutable |
| AnalysisJob | pipeline execution | terminal state is immutable |
| FaceTrack | one tracked face | one landmark schema/version |
| LandmarkSequence | timestamped points | monotonic timestamps; semantic point map |
| Baseline | verified subject motion | only approved source decisions; immutable version |
| ModelVersion | scoring artifact | checksum, feature schema and calibration required |
| Decision | machine result | immutable; evidence and model version required |
| Review | human assessment | append-only; reviewer identity required |
| AuditEvent | security/accounting history | append-only, UTC, correlation ID |

## State machine
`QUEUED → RUNNING → SUCCEEDED | INSUFFICIENT_DATA | FAILED`.

`INSUFFICIENT_DATA` is a domain outcome. `FAILED` means infrastructure/code failure.

## Retention
Raw video, derived landmarks, decisions and audit records have separate retention policies. Deleting a subject creates a tombstone/audit record and removes biometric artifacts according to jurisdiction and policy.
