# Security and privacy

Facial landmarks и motion profiles — **биометрические данные** (PII + биометрия). Подход — privacy by design, defense in depth.

## Authentication
- **OIDC** (Keycloak / Auth0 / Okta) в production. JWT access token (5 мин TTL) + refresh token (24 ч, rotation).
- В dev — HS256 с shared secret в `.env` (`JWT_SECRET`).
- `aud=mimicguard-api`, `iss` проверяется.
- Subject claim = user_id, custom claim `roles: ["operator","reviewer",...]`.

## Authorization (RBAC)
5 базовых ролей:
| Role | Permissions |
|---|---|
| `operator` | create jobs, view jobs, view assets, no model ops |
| `reviewer` | + create reviews, view audit (read-only) |
| `model_admin` | + promote/rollback models, rebuild baselines |
| `auditor` | + view/export audit, view users, no mutations |
| `system_admin` | superset, manage users/RBAC |

- Role check в FastAPI через `Depends(require_role("reviewer"))`.
- Tenant scoping через SQLAlchemy event listener (`before_compile` добавляет `WHERE tenant_id = :current_tenant`).
- IDOR тесты: пользователь tenant A не может читать данные tenant B.

## Encryption
- **In transit:** TLS 1.3 everywhere; HSTS в production.
- **At rest:**
  - PostgreSQL: KMS-managed disk encryption.
  - MinIO/S3: SSE-KMS bucket default.
  - Models: SSE-KMS + signed URLs с TTL 5 мин.
  - Landmarks.npz: client-side encryption опционально (envelope, KMS DEK per tenant).
- **Secrets:** HashiCorp Vault / AWS Secrets Manager / GCP Secret Manager. `.env` только в dev.

## Upload hardening
- MIME sniff + magic bytes.
- File size limit 1 GB, duration limit 30 мин.
- Decompression bomb checks (ffprobe duration vs file size sanity).
- Video decoder в sandbox (`subprocess` с `rlimit`, no network).
- Pre-signed uploads с TTL 15 мин, single-use, content-length-binding.

## Threat priorities
1. **IDOR / tenant breakout** — SQL filter + test.
2. **Poisoned baselines** — только CONFIRMED_GENUINE + minimum 3 sessions + drift detection.
3. **Model substitution** — checksum + signature verification при загрузке.
4. **Malicious media** — sandboxed ffmpeg + clamav scan (опционально).
5. **Credential theft** — short JWT, refresh rotation, mTLS для worker→API.
6. **Unbounded uploads** — rate limits, quota per tenant.
7. **Audit tampering** — append-only (revoke UPDATE/DELETE + WORM bucket для S3 audit exports).
8. **Unauthorized biometric export** — отдельный permission `biometric:export`, reason обязателен, audit.

## Privacy controls
- **Consent state** на Subject: `PENDING` → `GRANTED` → `REVOKED`. Baseline создаётся только при `GRANTED`.
- **Right to be forgotten:** soft-delete + tombstone + удаление raw video и landmarks + audit запись.
- **Data minimization:** клиент не получает raw landmarks по умолчанию; только агрегаты и временные точки.
- **No telemetry of biometric data:** OpenTelemetry attributes — только counts, timings, error codes.
- **Retention policies** настраиваются per tenant; по умолчанию — 90 дней для raw video.

## Audit log
- Каждое значимое действие: `view_asset`, `view_landmarks`, `create_review`, `promote_model`, `export_baseline`, `delete_subject`, etc.
- Fields: `id`, `tenant_id`, `actor_id`, `action`, `resource_type`, `resource_id`, `at`, `ip`, `user_agent`, `correlation_id`, `reason?`, `metadata?`.
- Append-only: PostgreSQL triggers `RAISE EXCEPTION` на UPDATE/DELETE.
- Export — отдельный job с audit-записью о самом export'е.
