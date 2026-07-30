# Runbook: Model drift detected

## Симптомы
- Алерт `ModelDrift` сработал (PSI > 0.2 в течение 24h).
- Brier score / ECE ухудшился > 0.05 за неделю.
- Reviewer disagreement κ < 0.6 в отчёте.

## Диагностика

```bash
# 1. Подробный отчёт по фичам
psql -c "SELECT feature, psi, ks_stat, sample_size FROM feature_drift WHERE computed_at > NOW() - INTERVAL '7 days' ORDER BY psi DESC LIMIT 20;"

# 2. Calibration по неделе
psql -c "SELECT date_trunc('day', created_at), avg(brier_score), avg(ece) FROM decision_metrics WHERE created_at > NOW() - INTERVAL '30 days' GROUP BY 1 ORDER BY 1;"

# 3. Reviewer disagreement
psql -c "SELECT reviewer_id, count(*), avg(kappa_score) FROM reviewer_metrics GROUP BY 1;"
```

## Митигация

1. **Если PSI > 0.5 (CRITICAL):** немедленно понизить модель в SHADOW, откатить на предыдущую ACTIVE.
2. **Если 0.2 < PSI < 0.5:** оставить ACTIVE, страница модели подсвечивается, model_admin получает уведомление.
3. **Если calibration drift:** запустить `python -m scripts.recalibrate --model-id ... --since 30d`.
4. **Если reviewer disagreement:** запросить у auditor обязательный double-review для следующих 100 решений.

## Follow-up
- Investigation ticket: какие фичи изменились? Возможно, новый тип камеры/освещения.
- Curate новый training dataset, если нужно.
- Plan retrain + new ModelVersion (DRAFT).
