# Module 20: Worker orchestration

**Путь:** `services/worker/`
**Framework:** dramatiq + RabbitMQ / Redis Streams broker
**Concurrency:** от 2 до 20 процессов, autoscale по queue depth

## Архитектура
```
Redis Stream "mimicguard.events"
    │
    ▼
Consumer group "worker-pipeline"
    │
    ├── video.ingest
    ├── landmarks.extract
    ├── quality.gate
    ├── asr.transcribe
    ├── phoneme.align
    ├── baseline.match
    ├── decision.create
    │
    ▼
PostgreSQL (job_stages, decisions)
```

## Файлы

### `broker.py`
```python
"""
MG-STUB: реализовать:
- setup_broker(): dramatiq broker = RedisStreamBroker(url=REDIS_URL)
- setup_middleware(): register PrometheusMiddleware, AgeLimit, TimeLimit, Retries
"""
```

### `actors/__init__.py`
```python
"""
MG-STUB: реализовать dramatiq actors (один файл или подмодули):

@dramatiq.actor(queue_name="video.ingest", max_retries=3, time_limit=300_000)
def ingest_video(asset_id: str, correlation_id: str | None) -> None:
    # 1. Update job state QUEUED→RUNNING
    # 2. record_stage("VALIDATE_ASSET", state=RUNNING)
    # 3. ffprobe → MediaInfo
    # 4. mark stage complete
    # 5. record_stage("DOWNLOAD_AUDIO", state=RUNNING)
    # 6. ffmpeg → mono PCM 16kHz numpy array (сохранить в S3)
    # 7. publish event: video.ingested.v1 (→ следующий actor)

@dramatiq.actor(queue_name="landmarks.extract", max_retries=3, time_limit=900_000)
def extract_landmarks(job_id: str):
    # 1. job_stages: extract → RUNNING
    # 2. OpenCV → frames
    # 3. MediaPipe Face Landmarker → face tracks
    # 4. Select longest track
    # 5. Save LandmarkSequence metadata + landmarks.npz in S3
    # 6. mark stage complete, publish landmarks.extracted.v1

@dramatiq.actor(queue_name="quality.gate", max_retries=2, time_limit=120_000)
def quality_gate(job_id):
    # 1. assess_quality(sequence)
    # 2. if accepted: write quality_score, publish next event
    # 3. if rejected: write INSUFFICIENT_DATA, job → INSUFFICIENT_DATA, NO next event

@dramatiq.actor(queue_name="asr.transcribe", max_retries=2, time_limit=600_000)
def transcribe(job_id):
    # 1. faster-whisper
    # 2. write Transcript rows + transcript.json in S3
    # 3. publish asr.completed.v1

@dramatiq.actor(queue_name="phoneme.align", max_retries=2, time_limit=60_000)
def align(job_id):
    # 1. загрузить transcript + landmarks.npz
    # 2. для каждого word: landmarks_slice = frames[start_ms:end_ms]
    # 3. нормализация по длительности: 30 frames
    # 4. write PhraseInstance records + decision.phrase_instances
    # 5. publish phrase.aligned.v1

@dramatiq.actor(queue_name="baseline.match", max_retries=2, time_limit=120_000)
def match_baseline(job_id):
    # 1. загрузить PhraseInstance records
    # 2. для каждого: найти PhraseTemplate, DTW + Mahalanobis
    # 3. собрать evidence
    # 4. decision_score aggregation
    # 5. write Decision row, publish decision.created.v1
    # 6. job state → SUCCEEDED

Каждый actor:
- идемпотентен: проверяет job_stages перед работой
- пишет heartbeat каждые 30s через redis SET job:{id}:heartbeat
- при exception: increment attempt, retry, или DLQ
"""
```

### `recovery.py`
```python
"""
MG-STUB: реализовать:
- StaleJobRecovery (cron every 60s):
    - SELECT jobs WHERE state='RUNNING' AND last_heartbeat_at < NOW() - INTERVAL '5 minutes'
    - mark FAILED, increment attempt, re-enqueue
- DLQDrainer: ручной инструмент для оператора
"""
```

## Per-stage timeout
| Stage | Timeout | Retry | DLQ |
|---|---|---|---|
| validate_asset | 60 s | 3 | yes |
| extract_video_frames | 600 s | 2 | yes |
| extract_landmarks | 900 s | 2 | yes |
| quality_gate | 30 s | 2 | yes |
| transcribe_asr | 600 s | 2 | yes |
| phoneme_align | 60 s | 2 | yes |
| match_baseline | 120 s | 2 | yes |
| create_decision | 30 s | 3 | yes |

## Observability
- per-stage histogram: `worker_stage_duration_seconds{stage, outcome}`.
- DLQ counter: `worker_dlq_total{stage}`.
- Active job gauge: `worker_active_jobs{stage}`.
