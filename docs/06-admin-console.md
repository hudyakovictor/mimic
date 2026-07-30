# React administration console

## Information architecture

```
/                       → Dashboard (system health, pending reviews)
/analyses               → Analyses queue (searchable, saved filters)
/analyses/:id           → Analysis detail (video, landmarks overlay, decision, evidence)
/analyses/:id/compare   → Side-by-side comparator (new)
/words                  → Words / phrases index
/words/:word            → Phrase detail (templates + samples)
/words/:word/compare    → Multi-version visual comparison (up to 4 runs)
/subjects               → Subjects list
/subjects/:id           → Subject profile (baselines, consent, history)
/reviews                → Reviews queue (pending + completed)
/reviews/:id            → Review detail
/models                 → Model registry + drift
/models/:id             → Model version detail (metrics, promote/rollback)
/audit                  → Audit log
/settings               → Tenant settings, users, RBAC
/login                  → Auth
```

## UX rules
- **Никогда** не показывать risk без quality и evidence.
- **Никогда** не использовать цвет как единственный сигнал.
- `INSUFFICIENT_DATA` визуально отличается от низкого риска (иконка, текст, фон).
- Raw video доступ — permissioned, с audit-записью.
- Destructive/model-promotion действия — с подтверждением и reason.
- **First-class состояния:** empty, loading, stale, partial, error.

## Frontend architecture

```
apps/admin/src/
├── main.tsx                  # root, providers
├── App.tsx                   # router, layout
├── pages/                    # route components
│   ├── DashboardPage.tsx
│   ├── AnalysesPage.tsx
│   ├── AnalysisDetailPage.tsx
│   ├── AnalysisComparePage.tsx
│   ├── WordsPage.tsx
│   ├── PhraseDetailPage.tsx
│   ├── PhraseComparePage.tsx
│   ├── SubjectsPage.tsx
│   ├── SubjectDetailPage.tsx
│   ├── ReviewsPage.tsx
│   ├── ReviewDetailPage.tsx
│   ├── ModelsPage.tsx
│   ├── ModelDetailPage.tsx
│   ├── AuditPage.tsx
│   ├── SettingsPage.tsx
│   └── LoginPage.tsx
├── features/                 # feature-level composition
│   ├── analyses/
│   ├── comparator/
│   ├── words/
│   ├── reviews/
│   ├── models/
│   └── audit/
├── components/               # generic UI
│   ├── StatusBadge.tsx
│   ├── Metric.tsx
│   ├── RiskRing.tsx
│   ├── VideoPlayer.tsx
│   ├── LandmarkOverlay.tsx
│   ├── SyncPlayer.tsx
│   ├── DataTable.tsx
│   ├── FilterBar.tsx
│   └── ...
├── api/                      # typed client
│   ├── client.ts
│   ├── queries.ts
│   └── schemas.ts            # Zod
├── hooks/
├── lib/
├── stores/                   # zustand for cross-route UI
├── types/
└── styles.css
```

## Canvas-overlay синхронное воспроизведение

`SyncPlayer` — компонент, который:
- Принимает `Track[]` (2..4 дорожки).
- Поддерживает общее `currentTimeMs`, `playing`, `speed`.
- Каждая дорожка имеет свой `<video>` (hidden), рисующий на off-screen canvas для sampling.
- **Один видимый** canvas, на котором рендерим все видео рядом + overlay landmarks.
- Реализация: per-frame `requestVideoFrameCallback` (Chromium/Safari TP) → отрисовка каждой дорожки в свой region видимого canvas → рисование skeleton'а поверх.
- При `pause` все треки на паузе; при `seek(t)` все треки `currentTime = t/1000`; при загрузке новой дорожки ждём `seeked` event.

## State management
- **Server state:** TanStack Query 5 (queries + mutations + invalidation).
- **Local UI state:** React useState/useReducer, zustand для cross-route (например, current playback time при переходе к /words).
- **No global Redux.** Избегаем prop drilling через composition.

## Routing
- `react-router-dom@7` data routers (`createBrowserRouter`), `loader` для prefetch, `action` для mutations.
- Error boundaries на каждом route level.
- ProtectedRoute wrapper с role-based redirect.

## Form management
- `react-hook-form` + `zod` resolver.
- Optimistic updates с rollback on error.

## API client
- Один `api` объект в `api/client.ts`, типизированный из OpenAPI.
- Zod-parsing всех ответов на boundary (defence in depth).
- Error → `ApiError(status, code, message, correlationId)`.
- Auto-retry только на 5xx + idempotent endpoints; max 3, exp backoff.

## Theming / a11y
- CSS variables для тем.
- `prefers-reduced-motion` уважается в анимациях.
- Focus rings, `aria-*` на всех interactive.
- Lighthouse a11y ≥ 95 для основных страниц.
- Keyboard: `j/k` для навигации по списку, `space` — play/pause, `←/→` — seek, `1..4` — выбор активной дорожки для деталей.
