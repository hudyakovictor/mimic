# Стек и план достижения измеримой точности — 30 июля 2026

## Граница продукта

MimicGuard решает задачу **1:1 verification**: динамика лица в проверяемом видео сравнивается с добровольно собранным baseline заявленного человека. Система не должна искать неизвестного человека по общей базе, определять эмоции/намерения или автоматически обвинять человека в использовании маски.

Выход модели — `risk + quality + evidence`, а не «истина». Финальный вердикт остаётся у ревьюера. Это важно и технически: силиконовые маски, плохое освещение, motion blur, дубляж, стоматологические изменения и неврологические состояния могут давать похожие отклонения.

## Что означает цель 95%

Нельзя честно обещать «вероятность подмены 95%» до испытаний. Корректная целевая метрика:

- recall силиконовых масок >= 95% **при заранее фиксированном false-positive rate** (например, <= 2%);
- отдельные срезы по человеку, камере, разрешению, языку, слову, освещению и типу маски;
- 95% bootstrap confidence interval для recall/FPR;
- split по людям и сессиям: кадры одного человека/ролика не могут попадать одновременно в train и test;
- отдельный внешний holdout, не использованный при настройке порога;
- `INSUFFICIENT_DATA` считается отдельным исходом, а не «низким риском».

Зрелый персональный baseline начинается с 10 verified-сессий, но для production-калибровки желательно 20–30 независимых сессий на частые фонетические классы. Редкие слова используют иерархический prior по фонемам, а не притворяются статистически зрелыми.

## Рекомендуемый стек на 2026-07-30

### Реализованное ядро (80/20)

| Слой | Выбор | Зачем |
|---|---|---|
| API | Python 3.12, FastAPI 0.141, Pydantic 2, SQLAlchemy 2 async | строгие контракты и быстрый ML integration path |
| Очередь | Dramatiq 2 + Redis, transactional outbox | повторяемые тяжёлые задачи без потери команды после commit |
| Метаданные | PostgreSQL 17+ | tenant scope, версии baseline, audit |
| Объекты | S3/MinIO | видео и массивы не раздувают PostgreSQL |
| Media | FFmpeg/ffprobe, OpenCV 4.14 | frame-accurate trim, decode, валидация |
| Лицо | MediaPipe Tasks Face Landmarker 0.10.x/1.x | 478 landmarks, pose; быстрый CPU baseline |
| ASR | faster-whisper 1.2 / CTranslate2 | word timestamps, RU/EN, CPU/CUDA |
| Сопоставление | NumPy 2, SciPy 1.17, DTW + online covariance | интерпретируемый baseline при малом числе образцов |
| UI | React 19.2, TypeScript 5.9, Vite 8.2, TanStack Query 5 | быстрый операторский интерфейс |
| Контракты UI | Zod 3, React Hook Form 7, Zustand 5 | validation на границе и минимальный local state |
| Security | Argon2id (`pwdlib`), JWT, RBAC, append-only audit | защита учётных и биометрических данных |
| Observability | OpenTelemetry 1.44, Prometheus | воспроизводимость и контроль drift/SLO |

Версии фиксируются lock-файлами и обновляются только после golden-video regression. «Самая новая» библиотека не должна автоматически попадать в production inference.

### Вторая ветка модели для реальной борьбы с масками

Одних landmarks недостаточно для устойчивых 95% на разных масках. После накопления размеченного набора добавляется multimodal fusion:

1. **Motion branch** — MediaPipe blendshapes + нормализованные 3D landmarks, velocity/acceleration, lip/cheek phase lag, DTW/temporal transformer.
2. **Audio-visual branch** — faster-whisper + WhisperX forced alignment (или wav2vec2 aligner), SyncNet-подобные lip/audio embeddings. Она отделяет чужую артикуляцию и плохой ASR.
3. **Appearance/deformation branch** — PyTorch 2.x, timm/Transformers, ConvNeXt/ViT на face crops; optical flow (RAFT/GMFlow) для границ маски, слабой деформации щёк и неестественных бликов.
4. **1:1 identity branch (опционально)** — SCRFD + ArcFace через ONNX Runtime/TensorRT, только для проверки заявленной личности и только при согласии. Score идентичности не смешивается молча со score маски.
5. **Calibration** — LightGBM или небольшая logistic/isotonic calibration поверх независимых branch scores и quality features. Для каждого решения сохраняются версия, checksum и вклад признаков.

rPPG по обычному сжатому YouTube-видео нестабилен; его можно использовать только как дополнительный evidence при достаточном качестве, но не как обязательный сигнал.

## Пайплайн данных

```text
upload / HTTPS MP4 / YouTube
        -> quarantine + ffprobe + SSRF/size checks
        -> экран выбора 1..20 интервалов
        -> frame-accurate H.264 analysis clips
        -> удаление длинного source (default)
        -> streaming decode -> face landmarks + quality
        -> audio -> ASR -> words -> exact time slices
        -> subject + language + word baseline lookup
        -> score + evidence -> human review
        -> CONFIRMED_GENUINE -> immutable sample + template v(N+1)
```

Baseline key всегда `(tenant_id, subject_id, language, normalized_word, feature_schema)`. Смешивание разных людей в одном шаблоне запрещено.

## Хранение без преждевременной сложности

### Канонический анализ-клип

Текущий профиль `analysis-v1`:

- H.264 High, `CRF 17`, preset `medium`, `yuv420p`;
- CFR, исходная частота с cap 60 fps;
- без upscale, максимум 1920x1080;
- GOP около 1 секунды, `faststart`;
- mono AAC 48 kHz, 96 kbit/s;
- точная нарезка с re-encode, а не keyframe stream-copy.

Почему не AV1/H.265 по умолчанию: они экономнее как архивные proxy, но усложняют браузерное декодирование и могут менять мелкую текстуру. Для 80/20 одна browser-safe каноническая копия лучше двух копий. Позже можно добавить AV1 proxy как disposable cache, не использовать его для inference и удалять по LRU.

### Производные данные

- 478-point overlay хранится как MGML + gzip; браузер распаковывает gzip штатным `DecompressionStream`;
- scoring curve — float32 `npy`, всего 33 нормализованных координаты на кадр;
- PostgreSQL хранит только индексы/статистику/решения, не бинарные массивы;
- phrase sample переиспользует уже короткий analysis clip через in/out points — отдельный MP4 на каждое слово не создаётся;
- исходный длинный объект удаляется только после успешного создания всех выбранных clips;
- lifecycle: незавершённые upload — 24 часа, proxy/cache — 30 дней, verified clips/landmarks — по consent retention policy.

## Эксперименты перед заявлением 95%

1. Собрать consented набор: genuine + минимум несколько семейств silicone/latex mask, replay/deepfake как hard negatives.
2. Для каждого ролика хранить camera/source/compression/mask metadata.
3. Зафиксировать golden holdout и метрики до обучения fusion.
4. Сравнить ablation: landmarks; +blendshapes; +audio-visual; +appearance/flow; full fusion.
5. Калибровать пороги на validation, один раз измерить holdout.
6. Провести shadow deployment и double-review подозрительных/случайных genuine случаев.
7. Показывать «95%» только для того operating point и домена, где нижняя граница доверительного интервала это подтверждает.

## Следующие инвестиции после 80/20

- вынести `createClips` из HTTP request в media queue с persisted progress;
- forced alignment по фонемам и phrase mining из соседних слов;
- ONNX/TensorRT inference и NVDEC/CV-CUDA при устойчивой GPU-нагрузке;
- pgvector нужен только для поиска похожих feature-сегментов, не для основной реляционной навигации;
- ClickHouse нужен только когда audit/telemetry действительно перерастут PostgreSQL;
- Kubernetes не нужен до появления нескольких worker pools и измеренного scheduling pressure.
