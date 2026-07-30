# Deployment

## Production topology

```
            ┌──────────────────┐
            │   CloudFront /   │
            │   Cloudflare CDN │
            └────────┬─────────┘
                     │
            ┌────────▼─────────┐
            │   ALB / Nginx    │
            │  (TLS termination│
            │   + WAF rules)   │
            └────────┬─────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
   ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
   │ API     │  │ API     │  │ API     │   (stateless, ≥ 3 replicas)
   │ pod 1   │  │ pod 2   │  │ pod 3   │
   └────┬────┘  └────┬────┘  └────┬────┘
        │            │            │
        └────────────┼────────────┘
                     │
       ┌─────────────┼─────────────┐
       │             │             │
   ┌───▼────┐   ┌────▼────┐   ┌────▼────┐
   │ RDS PG │   │  Redis  │   │   S3    │   (managed)
   │ primary│   │ cluster │   │         │
   │ +RO×2  │   │         │   │         │
   └────────┘   └─────────┘   └─────────┘

   ┌──────────────────────────────────┐
   │  Worker fleet (autoscaling)      │
   │  min=2, max=20, by queue depth   │
   │  GPU pool для ASR (spot)         │
   └──────────────────────────────────┘

   ┌──────────────────────────────────┐
   │  Observability                   │
   │  Prometheus + Grafana + Tempo    │
   │  Loki / CloudWatch               │
   │  PagerDuty                       │
   └──────────────────────────────────┘
```

## Kubernetes manifests
- `infra/k8s/api.yaml` — Deployment + Service + HPA.
- `infra/k8s/worker.yaml` — Deployment + HPA (cpu + queue depth).
- `infra/k8s/postgres.yaml` — managed external (или operator-managed in-cluster).
- `infra/k8s/redis.yaml` — managed external.
- `infra/k8s/minio.yaml` — statefulset + PVC.
- `infra/k8s/ingress.yaml` — TLS + cert-manager.
- `infra/k8s/networkpolicy.yaml` — default deny + allowlists.
- `infra/k8s/podsecuritypolicy.yaml` — non-root, readOnlyRootFilesystem, no privileged.

## CI/CD
- GitHub Actions:
  - `lint` (ruff, mypy, eslint, tsc)
  - `test` (pytest, vitest, playwright)
  - `build` (docker images, sbom, sign with cosign)
  - `migrate` (alembic upgrade head against staging)
  - `deploy-staging`
  - `smoke` (Playwright e2e against staging)
  - `deploy-prod` (manual approval, blue/green)

## Secrets
- External Secrets Operator синкает из AWS Secrets Manager / Vault.
- Pre-commit hook: блокирует коммиты с secret patterns.

## Backups
- PostgreSQL: PITR, daily snapshot, retention 30 дней.
- S3: versioning + lifecycle rules.
- MinIO (если self-hosted): backup через `mc mirror` nightly.

## Disaster recovery
- RPO: 1 час (S3 versioning) / 5 минут (PG WAL streaming).
- RTO: 30 минут.
- Регулярные DR-учения (quarterly).

## Cost notes
- API: маленькие инстансы (2 vCPU, 4 GB) — stateless.
- Worker: выделенный пул, autoscale по queue depth.
- ASR (faster-whisper `small`): CPU достаточно для dev, `medium` рекомендуется на GPU.
- Storage: cold tier для видео старше 90 дней.
