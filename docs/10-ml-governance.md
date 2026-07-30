# ML governance

## ModelVersion deployability
Артефакт deployable только с:
- `artifact_checksum` (SHA-256)
- `code_commit` (git SHA с обучившим коммитом)
- `training_dataset_manifest` (список source jobs, хеши, сплиты)
- `feature_schema` (semver)
- `evaluation_report` (FAR, FRR, AUC, calibration, CIs)
- `calibration_profile` (Platt или isotonic, JSON)
- `intended_use`
- `known_limitations`
- `approver_id` (model_admin, отличный от автора)

## Promotion flow
```
DRAFT
  │ (evaluation passed, registered)
  ▼
VALIDATED
  │ (deploy в shadow, run 24h на live traffic, log decisions без влияния)
  ▼
SHADOW
  │ (manual promote by model_admin, with reason)
  ▼
ACTIVE  ←──┐
  │       │ (rollback by model_admin)
  ▼       │
RETIRED ──┘
```

- Active всегда **один** на `model_kind`.
- Rollback переключает pointer; исторические decisions остаются привязаны к своей версии (immutable).
- Каждое переключение — `model.promoted.v1` event + audit.

## Baseline curation
- Шаблоны строятся **только** из `Review.verdict = CONFIRMED_GENUINE`.
- Минимум 3 confirmed-сессии для создания первой версии шаблона.
- Каждое новое CONFIRMED_GENUINE инкрементит версию шаблона (новый immutable row).
- Quarantine dataset: `Review.verdict = CONFIRMED_SUSPICIOUS` или `UNDECIDABLE` — никогда не попадает в baseline автоматически.
- **Никакого** автоматического retrain из reviewer actions. Только curated promotion.

## Evaluation splits
- **Person-disjoint:** тестовая выборка не содержит людей из train.
- **Session-disjoint:** разные сессии одного человека в train/test.
- **Device-disjoint:** разные устройства съёмки.
- Splits фиксируются при обучении и запекаются в manifest.

## Reporting
- **Запрещено** оптимизировать accuracy в ущерб calibration и FAR.
- Каждая evaluation отчёт включает:
  - FAR @ FRR=5% и @ FRR=1%
  - AUC с 95% bootstrap CI
  - Brier score, ECE
  - Confusion matrix
  - Per-subject метрики
  - Failure analysis (топ-10 false positives с evidence)
- Отчёт хранится в БД + object storage.

## Drift management
- PSI/KS-test на input features, ежедневно.
- PSI > 0.2 → WARNING, > 0.5 → CRITICAL (страница модели подсвечивается).
- Calibration drift: weekly Brier score на reviewed-выборке, тренд за 30 дней.
- Reviewer disagreement: monthly Cohen's κ; если κ < 0.6 — required reviewer training + recalibration round.
