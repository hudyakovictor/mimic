# Observability and SLO

## SLOs
- API availability 99.9% monthly.
- p95 job registration under 400 ms excluding upload.
- 95% of accepted ten-minute assets complete inside five minutes at target hardware.
- less than 1% operational failure after automatic retry.

## Signals
Metrics: queue depth/age, stage duration, extraction FPS, quality rejection by code, decisions by label/model, review agreement, retry/DLQ count. Logs: structured, correlated, no biometric arrays. Traces: API → outbox → worker stages. Alerts use burn-rate windows, not single spikes.

Model monitoring separates input quality drift, feature drift, calibration drift and reviewer disagreement.
