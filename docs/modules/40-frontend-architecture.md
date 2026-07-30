# Module 40: Frontend architecture

**Путь:** `apps/admin/`
**Стек:** React 19 + Vite 6 + TypeScript 5.7 + TanStack Query 5 + Zustand 4 + Zod 3 + react-router-dom 7

## Слои

```
┌─────────────────────────────────────┐
│ pages/         Route components     │  ← минимальная логика, layout
├─────────────────────────────────────┤
│ features/      Domain features      │  ← composition + queries
├─────────────────────────────────────┤
│ components/    Generic UI           │  ← pure, no fetches
├─────────────────────────────────────┤
│ api/           Typed HTTP client    │  ← Zod parsing
├─────────────────────────────────────┤
│ lib/           Pure utilities       │  ← formatting, math
├─────────────────────────────────────┤
│ stores/        Zustand stores       │  ← cross-route UI
└─────────────────────────────────────┘
```

## State rules
- Server state — TanStack Query (cache, invalidation, retries).
- Local UI state — useState/useReducer.
- Cross-route UI state (текущий playback time, выбранные треки) — zustand.
- No Redux, no MobX.

## Routing
- React Router 7 data routers (`createBrowserRouter`).
- `loader` для prefetch, `action` для mutations.
- Error boundaries per route.
- `ProtectedRoute` с role-check.

## Forms
- `react-hook-form` + `@hookform/resolvers/zod`.
- Optimistic updates с rollback.
- Server-side validation errors → form fields.

## API client
- Один `api` объект в `api/client.ts`, типизированный из OpenAPI.
- Zod parsing всех ответов на boundary.
- `ApiError` с status/code/message/correlationId.
- Auto-retry только на 5xx + idempotent, exp backoff.

## Accessibility
- WCAG 2.1 AA для primary workflows.
- Keyboard navigation (`j/k`, `space`, `←/→`, `1..4`).
- Focus rings.
- ARIA на всех interactive.
- `prefers-reduced-motion` уважается.
- Lighthouse a11y ≥ 95.

## Theming
- CSS variables (light/dark).
- Тёмная тема по умолчанию (analyst-friendly).

## Performance budgets
- Initial bundle < 200 KB gz.
- Route lazy loading.
- Video overlay uses `requestVideoFrameCallback` где доступно, fallback `setTimeout(16)`.

## Errors
- Global ErrorBoundary: 404, 500.
- Per-page: loading, empty, stale, partial, error.
- ApiError → toast + retry button.

## Internationalization
- i18next + react-i18next.
- Default language: en.
- ru translation: complete.
- Date/time/numbers через Intl.
