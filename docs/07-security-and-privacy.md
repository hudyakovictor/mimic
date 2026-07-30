# Security and privacy

Facial landmarks and motion profiles are biometric data.

## Required controls
- OIDC authentication; short-lived access tokens.
- RBAC: operator, reviewer, model-admin, auditor, system-admin.
- Tenant scoping enforced in repository layer and database policies.
- TLS in transit; KMS-backed encryption at rest.
- Pre-signed uploads/downloads with short expiry.
- Malware/media parser sandbox before analysis.
- No raw video in application logs, analytics or error traces.
- Append-only audit for view, export, review and model promotion.
- Secrets from a secret manager, never `.env` in production.
- Rate limits, file size/duration limits and decompression-bomb controls.
- Explicit retention, consent/legal basis and deletion workflow.

## Threat priorities
IDOR/tenant breakout, poisoned baselines, model substitution, malicious media, credential theft, unbounded uploads, audit tampering and unauthorized biometric export.
