# Runbook: Worker stuck

## Симптомы
- `analysis_jobs_in_state{state="RUNNING"}` растёт, не уменьшается.
- Queue depth растёт.
- Новые job'ы в state `RUNNING` не двигаются.

## Диагностика

```bash
# 1. Проверить запущен ли worker
kubectl -n mimicguard get pods -l app=worker
docker compose -f infra/docker-compose.yml ps worker

# 2. Проверить логи
kubectl -n mimicguard logs -l app=worker --tail=200
docker compose -f infra/docker-compose.yml logs --tail=200 worker

# 3. Список текущих job'ов в БД
psql -c "SELECT id, state, started_at, last_heartbeat_at FROM analysis_jobs WHERE state='RUNNING' ORDER BY started_at LIMIT 20;"

# 4. Redis lag
redis-cli XLEN mimicguard.events
redis-cli XINFO GROUPS mimicguard.events
```

## Типовые причины
1. **OOM kill** — MediaPipe или faster-whisper съел память.
2. **Зависший face tracker** — бесконечный цикл на одном frame.
3. **Длинная операция без progress** — extraction > 30 мин (видео 4K).
4. **Сегfault в native-библиотеке.**

## Митигация

```bash
# Перезапуск pod'а
kubectl -n mimicguard delete pod -l app=worker --field-selector=status.phase=Running

# Пометить job как FAILED для retry
psql -c "UPDATE analysis_jobs SET state='QUEUED', last_error=NULL WHERE id IN (...);"
```

## Предотвращение
- Per-job timeout (alarm(2) + soft kill).
- Heartbeat: worker пишет `last_heartbeat_at` каждые 30 сек; orchestrator переводит в FAILED через 5 мин без heartbeat.
- Memory limit per worker (4 GB).
- CPU limit per worker (2 cores).
- Pre-flight: ffmpeg probe до того, как встать в очередь.
