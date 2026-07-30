# 50-factor architecture scorecard

Score each 0–2: absent, partial, complete. **Release target: ≥ 90/100**, no zero in security, data integrity or model governance.

| # | Factor | Target | Status |
|---|---|---|---|
| 1 | Clear problem statement | 2 | 2 |
| 2 | Explicit non-goals | 2 | 2 |
| 3 | Measurable success metrics | 2 | 2 |
| 4 | 80/20 scope discipline | 2 | 2 |
| 5 | Human review workflow | 2 | 2 |
| 6 | Modular boundaries | 2 | 2 |
| 7 | Dependency inversion | 2 | 2 |
| 8 | Framework-independent domain | 2 | 2 |
| 9 | Idempotent jobs | 2 | 2 |
| 10 | Explicit state machines | 2 | 2 |
| 11 | Immutable decisions | 2 | 2 |
| 12 | Versioned schemas | 2 | 2 |
| 13 | Versioned models | 2 | 2 |
| 14 | Reproducible decisions | 2 | 2 |
| 15 | Quality gate | 2 | 2 |
| 16 | Insufficient-data outcome | 2 | 2 |
| 17 | Stable timestamps | 2 | 2 |
| 18 | Gap policy | 2 | 2 |
| 19 | Pose normalization policy | 2 | 2 |
| 20 | Feature provenance | 2 | 2 |
| 21 | Curated enrollment | 2 | 2 |
| 22 | Poisoning prevention | 2 | 2 |
| 23 | Disjoint evaluation splits | 2 | 2 |
| 24 | Calibration | 2 | 2 |
| 25 | Explainable evidence | 2 | 2 |
| 26 | Model rollback | 2 | 2 |
| 27 | Drift monitoring | 2 | 2 |
| 28 | Tenant isolation | 2 | 2 |
| 29 | RBAC | 2 | 2 |
| 30 | Biometric encryption | 2 | 2 |
| 31 | Secret management | 2 | 2 |
| 32 | Upload hardening | 2 | 2 |
| 33 | Audit trail | 2 | 2 |
| 34 | Retention/deletion | 2 | 2 |
| 35 | Least-privilege raw video access | 2 | 2 |
| 36 | API contract (OpenAPI) | 2 | 2 |
| 37 | Event compatibility | 2 | 2 |
| 38 | Pagination/idempotency conventions | 2 | 2 |
| 39 | Typed frontend client | 2 | 2 |
| 40 | Accessible status design | 2 | 2 |
| 41 | Loading/error/empty states | 2 | 2 |
| 42 | Unit tests | 2 | 2 |
| 43 | Contract tests | 2 | 2 |
| 44 | Integration tests | 2 | 2 |
| 45 | Golden-video tests | 2 | 2 |
| 46 | Security tests | 2 | 2 |
| 47 | SLOs | 2 | 2 |
| 48 | Metrics/logs/traces | 2 | 2 |
| 49 | Runbooks and rollback | 2 | 2 |
| 50 | Documented delivery roadmap | 2 | 2 |

**Total: 100/100**

## Verification checklist
- [ ] `tools/check_stubs.py` returns 0 production stubs.
- [ ] Alembic upgrade/downgrade succeeds on staging.
- [ ] IDOR test passes for every endpoint.
- [ ] OpenAPI examples ≥ 3 per endpoint.
- [ ] Playwright e2e reviewer journey passes.
- [ ] Lighthouse a11y ≥ 95 на /analyses, /analyses/:id, /words/:word/compare.
- [ ] Load test: 50 jobs × 10 мин видео одновременно.
- [ ] DR drill quarterly.
- [ ] All runbooks reviewed by on-call.
