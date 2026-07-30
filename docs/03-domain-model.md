# Domain model

## Entities

| Entity | Purpose | Key invariants |
|---|---|---|
| `Tenant` | граница безопасности | все queries tenant-scoped |
| `User` | оператор/ревьюер/аудитор | role ∈ {operator, reviewer, model_admin, auditor, system_admin} |
| `Subject` | заявленный человек | baseline только при `consent_state=GRANTED` |
| `Asset` | immutable video metadata | SHA-256 unique per tenant; object URI immutable |
| `AnalysisJob` | пайплайн выполнения | terminal state immutable |
| `JobStage` | идемпотентная стадия | completed_at ставится до ack |
| `FaceTrack` | один трек лица | one landmark schema/version |
| `LandmarkSequence` | пофреймовые точки | monotonic timestamps, semantic point map |
| `Transcript` | распознанная речь | words с char-level alignment |
| `PhraseInstance` | произнесённое слово/словосочетание в конкретном видео | references transcript + landmark interval |
| `PhraseTemplate` | агрегированный baseline по слову/фразе | versioned, immutable |
| `PhraseSample` | один verified-прогон, вошедший в template | references AnalysisJob, video, landmarks |
| `Baseline` | (alias для PhraseTemplate collection) | curated only from CONFIRMED_GENUINE reviews |
| `ModelVersion` | scoring artifact | checksum + feature schema + calibration required |
| `Decision` | machine result | immutable; evidence + model version required |
| `Review` | human assessment | append-only; reviewer identity required |
| `AuditEvent` | security/accounting history | append-only, UTC, correlation_id |
| `Enrollment` | акт согласия субъекта | signed consent + retention policy |

## State machines

### AnalysisJob
```
QUEUED → RUNNING → SUCCEEDED
              ↘
               INSUFFICIENT_DATA  (terminal, доменное)
              ↘
               FAILED             (terminal, инфраструктурное)
```
- `INSUFFICIENT_DATA` — **доменный успех**: качество недостаточно, нельзя вынести вердикт.
- `FAILED` — инфраструктурная ошибка: OOM, диск, битый медиа. Подлежит retry.

### ModelVersion
```
DRAFT → VALIDATED → SHADOW → ACTIVE → RETIRED
```
- `ACTIVE` всегда один на `model_kind`.
- `SHADOW` пишет решения в audit, но не используется в production scoring.

### Review
```
PENDING → COMPLETED
              ↘ WITHDRAWN (только для system_admin, с reason)
```

## Phrase / Baseline aggregation

```
Asset (video) ── AnalysisJob ─── LandmarkSequence
                              ── Transcript
                              ── Decision
                              ── Review (CONFIRMED_GENUINE)
                                        │
                                        ▼
              PhraseInstance (word, [start,end], landmark slice)
                                        │
                                        ▼  (если >=3 CONFIRMED_GENUINE по тому же слову)
              PhraseTemplate vN (mean curve, covariance, phoneme_class, version)
                                        │
                                        ▼  (каждое новое подтверждение инкрементит version)
              PhraseTemplate v(N+1)   (immutable, новая строка в БД)
```

- Каждый новый CONFIRMED_GENUINE-ревью по `Decision`, в котором присутствует `PhraseInstance` со словом X, **атомарно** создаёт новую версию `PhraseTemplate` для слова X (если уже есть baseline по этому слову, иначе создаёт первую).
- Версии никогда не перезаписываются: `PhraseTemplate.id = uuid()`, `version = int`, `parent_id` указывает на предыдущую.
- Decision-скор учитывает последнюю ACTIVE-версию шаблона; исторические Decision-ы остаются привязаны к своим версиям.

## Retention
- Raw video: настраиваемая (default 90 дней после последнего доступа).
- Derived landmarks: 365 дней.
- Decisions + reviews + audit: 7 лет (для compliance).
- При удалении Subject: tombstone + audit + удаление biometric artifacts согласно политике.
