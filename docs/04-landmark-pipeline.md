# Landmark pipeline

## Входной контракт
Один media asset + заявленный человек. Adapter эмитит per-frame semantic landmarks, confidence, head pose и source timestamp.

## Stages (полный список с контрактами)

### 1. validate_asset
- **Вход:** object URI в S3, content-type, content-length.
- **Действия:** probe с `ffprobe` (codec, duration, time base, corruption check); проверка, что длительность ≤ 30 мин, размер ≤ 1 GB; MIME-sniff; magic bytes.
- **Выход:** `MediaInfo` (duration_ms, fps, width, height, has_audio, codec).
- **Failure modes:** `MEDIA_UNREADABLE`, `MEDIA_CORRUPTED`, `MEDIA_TOO_LARGE`, `MEDIA_TOO_LONG`.

### 2. extract_video_stream + extract_audio_stream
- Декодирование в raw frames (BGR24 numpy) и mono 16kHz PCM float32 audio.
- **Адаптер:** OpenCV (video) + ffmpeg-python (audio).

### 3. track_face (Face Mesh)
- **Адаптер:** MediaPipe Face Landmarker (Tasks API), model = `face_landmarker.task`.
- На каждом frame детектируется до 1 лица (можно расширить). Confidence ≥ 0.5.
- **Tracking:** по центроиду bbox (Hungarian assignment, simple IoU).
- Если трек теряется на > 30 кадров — закрываем трек, открываем новый.
- Для v1 — берём самый длинный трек.
- **Выход:** `FaceTrack(track_id, frames: list[LandmarkFrame], fps)`.
- 478 точек × 3 координаты (x, y, z) + 1 confidence per face.

### 4. quality_gate
- `assess_quality(sequence)` — см. `packages/landmark_engine/quality.py`.
- Принимаем только при `accepted=True` И `score ≥ 0.55`.
- Иначе → job → `INSUFFICIENT_DATA`.

### 5. normalize_sequence
- `normalize_sequence(sequence)` — см. `packages/landmark_engine/normalization.py`.
- 3D-rotation compensation (выделено в отдельный адаптер `head_pose_correction.py`, чтобы не давать ложных биометрических сигналов от наивной 2D-ротации).

### 6. derive_features
- Displacement: `Δ = f(t) - f(t-1)`.
- Velocity: `v = Δ / dt`.
- Acceleration: `a = dv / dt`.
- Regional ratios: mouth_open / mouth_width, lip_corner_distance, jaw_opening, brow_raise.
- Эмитим версионированный schema `motion-features-v1`.

### 7. asr_transcribe
- **Адаптер:** faster-whisper (модель `small` для dev, `medium` для production).
- **Выход:** `Transcript(words: list[Word(start_ms, end_ms, text, confidence)])`.
- Язык: en+ru (auto-detect).

### 8. align_words_to_landmarks
- По timestamp каждого слова вычисляем `landmark_slice = frames[start_ms:end_ms]`.
- Дополнительно — нормализуем по длительности: 30 фреймов на слово (time-warp).
- **Выход:** `list[PhraseInstance(word, normalized_sequence, start_ms, end_ms, confidence)]`.

### 9. find_baseline
- Для каждого `PhraseInstance` ищем `PhraseTemplate` для этого слова (если есть).
- Используется **DTW (Dynamic Time Warping)** на нормализованных последовательностях + **Mahalanobis distance** на региональных ratios.
- Минимум: 3 verified-сессии для слова → шаблон создаётся; ≥10 — статистически устойчивый baseline.

### 10. score_and_decide
- `decision_score = max(0, 1 - min_similarity)` ∈ [0, 1].
- Label: `CONSISTENT` если `< 0.35`, `SUSPICIOUS` если `≥ 0.65`, иначе — `INSUFFICIENT_DATA` (с пометкой о слабом baseline).
- Evidence: top-3 фразы с наихудшим score + их contribution.

### 11. create_evidence
- Каждый evidence-item: code, contribution ∈ [-1, 1], message, [start_ms, end_ms].
- Коды: см. ниже.

### 12. persist_decision
- Immutable insert в `decisions`.
- Event `decision.created.v1` в outbox.

## High-value points (v1)
- Глаза: outer corners (33, 263), inner corners (133, 362).
- Брови: 105, 334, 46, 70.
- Нос: tip (1), alar (49, 279), bridge (168).
- Рот: outer (61, 291, 0, 17), inner (13, 14, 78, 308), corners расширенные.
- Челюсть: chin (152), jaw (172, 397).
- Щёки: lateral (234, 454), upper (50, 280), lower (132, 361).
- Эти ~30 точек — «motion-v1» schema. Каждое добавление точки — bump schema version + ablate.

## Missing data policy
- Никогда не делаем forward-fill больших gap'ов.
- Gap < 180 ms — линейная интерполяция + mask channel.
- Gap ≥ 180 ms — frame помечается invalid, в scoring не участвует.
- Если > 30% frames invalid → `INSUFFICIENT_DATA`.

## Evidence codes
| Code | Что значит | Когда срабатывает |
|---|---|---|
| `MOUTH_CHEEK_LAG` | Запаздывание движения щёк относительно рта | phase delay > 80 ms в DTW |
| `JAW_RANGE_LOW` | Сниженная амплитуда челюсти | max jaw_opening < baseline_μ - 2σ |
| `LIP_ASYMMETRY` | Асимметрия углов губ | L-R разница > 2σ |
| `MOTION_TIMING_SHIFT` | Сдвиг общего времени артикуляции | DTW path наклон > 1.3 или < 0.7 |
| `BASELINE_DISTANCE_HIGH` | Общая дистанция от baseline | Mahalanobis > χ²(0.95) |
| `LOW_QUALITY_AUDIO` | Плохое аудио, ASR неуверен | mean word confidence < 0.6 |
| `INSUFFICIENT_BASELINE` | Недостаточно verified-сессий для слова | samples < 3 |
| `EXCESSIVE_GAPS` | Длинные разрывы в треке | max_gap > 180 ms |
| `MULTIPLE_FACES` | Найдено несколько лиц | detection count > 1 |
| `HEAD_POSE_OUT_OF_RANGE` | Голова слишком сильно повёрнута | abs(yaw) > 45° |

Каждый evidence несёт contribution ∈ [-1, 1] (отрицательный — снижает риск) и временной интервал.
