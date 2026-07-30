# MimicGuard Landmarks

Production-oriented monorepo scaffold for detecting anomalous facial motion in low-quality video using **only facial landmarks and their temporal dynamics**.

> Status: architecture baseline. Contracts, boundaries, validation and admin UI shell are implemented. ML extraction, training and production scoring are explicit adapters that raise `NotImplementedError` until a validated model is supplied.

## 80/20 product scope

The first release intentionally solves the five capabilities that create most of the value:

1. ingest and track video-analysis jobs;
2. validate landmark sequence quality;
3. normalize motion against head pose, scale and frame rate;
4. compare a probe sequence with a verified person baseline by phoneme/word context;
5. review explainable risk signals in a React administration console.

Not in v1: texture, rPPG, optical flow, emotion recognition, general-purpose surveillance, automatic identity enrollment from unreviewed video.

## Repository map

- `apps/admin` — React 19 + TypeScript administration console.
- `services/api` — FastAPI application and application services.
- `packages/landmark_engine` — domain algorithms and replaceable ML ports.
- `packages/contracts` — API/event contracts and enums.
- `docs` — architecture, data model, security, testing and delivery documentation.
- `infra` — local Docker topology and observability placeholders.

## Start here

1. Read `docs/01-product-scope.md`.
2. Read `docs/02-architecture.md` and `docs/03-domain-model.md`.
3. Use `docs/12-implementation-roadmap.md` as the delivery sequence.
4. Every placeholder is marked `MG-STUB` and must either remain an explicit failure or be replaced by a tested implementation.

## Local development target

```bash
cp .env.example .env
make bootstrap
make dev
```

The commands are documented contracts. Dependency installation is intentionally not executed by the scaffold generator.

## Architectural rules

- Raw videos never become training data automatically.
- Unknown or poor-quality input returns `INSUFFICIENT_DATA`, not a forced verdict.
- API handlers contain no domain decisions.
- Feature schemas and model versions are immutable once used in a decision.
- Every score is accompanied by evidence, quality and model version.
- Landmark extraction is a replaceable port; MediaPipe is the reference adapter, not a domain dependency.
