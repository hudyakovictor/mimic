# Module 42: Pages (full list with states)

Каждая страница должна иметь: **loading, empty, error, partial, success** состояния. Никаких "TODO" в production-готовом UI.

## `/` Dashboard
**Цель:** обзор системы, метрики, последние события.

**Содержимое:**
- 4 метрики: «требуют проверки», «качество OK», «медиана обработки», «согласие ревьюеров».
- График: jobs за 7 дней.
- Таблица: последние 10 analyses.
- Список: pending reviews (max 5).

**Запросы:** `GET /v1/dashboard/metrics`, `GET /v1/analysis-jobs?limit=10`, `GET /v1/reviews?status=pending&limit=5`.

**States:**
- Loading: skeleton cards.
- Empty: "Ничего нового".
- Error: retry button.

## `/analyses`
**Цель:** очередь анализов с фильтрами.

**Содержимое:**
- FilterBar: state, subject, model_version, date range, risk range.
- Saved filters (в localStorage + опционально в БД).
- Таблица: 50 строк, virtual scroll, columns: ID, Subject, State, Risk, Quality, Created.
- Bulk actions: cancel, retry.

**Запросы:** `GET /v1/analysis-jobs?cursor=...`.

**States:** loading, empty, error, stale (с пометкой "обновлено X мин назад").

## `/analyses/:id`
**Цель:** детальный просмотр одного анализа.

**Содержимое:**
- Видео-плеер (HTML5) + overlay landmarks (LandmarkOverlay).
- Tabs: Decision / Evidence / Phrases / Stages.
- Decision: risk-ring, label, quality.
- Evidence: timeline с маркерами, clickable → seek video.
- Phrases: список с переходом к /words/:word.
- Stages: статусы pipeline.

**Запросы:** `GET /v1/analysis-jobs/{id}`, `GET /v1/decisions?jobId={id}`.

## `/analyses/:id/compare`
**Цель:** side-by-side сравнение с baseline-прогонами тех же слов.

**Содержимое:**
- SyncPlayer (canvas-overlay).
- Слева: probe video.
- Справа: до 3 baseline-прогонов (по клику на слово).
- Overlay landmarks (разные цвета для каждой дорожки).
- Timeline с маркерами слов.

**Запросы:** `GET /v1/words/{word}/samples`, `GET /v1/words/{word}/samples/{sid}/videoClipUrl`, `GET /v1/words/{word}/samples/{sid}/landmarks`.

## `/words`
**Цель:** индекс распознанных слов с агрегатами.

**Содержимое:**
- Таблица: word, language, n_templates, n_samples, latest_decision_distribution, last_updated.
- Поиск (debounce 200 ms).
- Фильтры: language, min_samples, has_mature_baseline.

**Запросы:** `GET /v1/words`.

## `/words/:word`
**Цель:** детальная страница слова.

**Содержимое:**
- Header: word, language, total samples, total templates, maturity indicator.
- Templates timeline (versions).
- Latest template: визуализация mean_curve (sparkline), regional_stats.
- Samples list: с миниатюрами видео, decision link.

**Запросы:** `GET /v1/words/{word}/templates`, `GET /v1/words/{word}/templates/{tid}`.

## `/words/:word/compare`
**Цель:** multi-version visual comparison.

**Содержимое:**
- SyncPlayer (canvas-overlay) с 2-4 видео.
- Каждая дорожка: thumbnail + select checkbox + landmark overlay.
- Overlay: траектории mean curve vs probe.
- Кнопка "Play" общая.

**Запросы:** `GET /v1/words/{word}/samples?templateId=...`.

## `/subjects`
**Цель:** список субъектов.

**Содержимое:**
- Таблица: name, consent_state, n_jobs, n_baselines, last_analyzed_at, retention_policy.
- Quick actions: view, request consent.

## `/subjects/:id`
**Цель:** профиль субъекта.

**Содержимое:**
- Header: name, consent, retention.
- Tabs: Activity / Baselines / Settings.
- Activity: jobs timeline.
- Baselines: list PhraseTemplates, with rebuild button.
- Settings: consent update, retention update.

## `/reviews`
**Цель:** очередь ревью.

**Содержимое:**
- Tabs: Pending / Completed / My reviews.
- Bulk assignment (system_admin).
- Quick filter by risk threshold.

## `/reviews/:id`
**Цель:** форма ревью.

**Содержимое:**
- Video player с overlay + SyncPlayer с baseline-клипом (если есть).
- Decision summary + evidence.
- Radio: CONFIRMED_GENUINE / CONFIRMED_SUSPICIOUS / UNDECIDABLE.
- Textarea: reason (min 10, max 2000).
- Confidence slider (optional).
- Submit → optimistic update + redirect.

## `/models`
**Цель:** registry моделей.

**Содержимое:**
- Table: kind, version, state, FAR/FRR/AUC, drift, created.
- Filter: kind, state.

## `/models/:id`
**Цель:** детали модели.

**Содержимое:**
- Header: kind, version, state, checksum, code_commit, approver.
- Metrics: FAR/FRR/AUC/Calibration (sparkline).
- Drift: PSI per feature.
- Actions: promote / rollback / retire (с подтверждением и reason).
- History: state transitions log.

## `/audit`
**Цель:** audit log.

**Содержимое:**
- FilterBar: actor, action, resource_type, date range.
- Table: timestamp, actor, action, resource, ip, reason.
- Export button (auditor only).

## `/settings`
**Цель:** tenant settings, users, RBAC.

**Содержимое:**
- Tabs: Tenant / Users / API keys / Retention / Webhooks.
- User management: invite, role change, deactivate.
- API keys: create (returns once), revoke, last_used_at.

## `/login`
**Цель:** аутентификация.

**Содержимое:**
- Email + password.
- "Забыли пароль" ссылка.
- Branding: логотип, название тенанта.
- Rate limit UI feedback.
