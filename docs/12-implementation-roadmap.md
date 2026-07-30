# Implementation roadmap

## Iteration 1 — operational spine
SQL schema/migrations, repositories, outbox, upload lifecycle, auth/RBAC, job queue and full admin list/detail states. No fake scorer: jobs stop at explicit stub in non-test environments.

## Iteration 2 — deterministic landmarks
Golden fixtures, MediaPipe adapter, face-track selection, quality dashboard, normalized feature storage and reproducibility report.

## Iteration 3 — baseline and scoring
Verified enrollment, baseline versions, interpretable statistical baseline, calibration, evidence intervals and reviewer workflow.

## Iteration 4 — validated ML
Temporal model, disjoint evaluation, shadow deployment, drift dashboards and promotion/rollback.

## Definition of done
Code, tests, migration, OpenAPI, observability, security review, runbook, rollback and data-retention impact are complete. A demo-only implementation cannot be promoted.
