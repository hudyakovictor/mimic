# Event contracts

Events are immutable and use an outbox. Consumers must be idempotent by `event_id`.

| Event | Producer | Required fields | Consumer |
|---|---|---|---|
| `asset.accepted.v1` | API | event_id, asset_id, sha256, created_at | analysis worker |
| `landmarks.extracted.v1` | worker | job_id, sequence_uri, schema_version, quality | scorer |
| `decision.created.v1` | scorer | decision_id, job_id, label, model_version | API/read model |
| `review.created.v1` | API | review_id, decision_id, verdict, reviewer_id | audit/training curation |

Breaking changes create a new event name/version. Consumers ignore unknown optional fields and reject missing required fields.
