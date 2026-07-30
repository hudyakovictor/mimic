# Module 41: API client

**Путь:** `apps/admin/src/api/`

## Файлы

### `client.ts`
```typescript
/**
 * MG-STUB: реализовать полностью.
 */
import { z } from 'zod';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api';

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public correlationId?: string,
    public fieldErrors?: Array<{ field: string; message: string }>
  ) {
    super(message);
  }
}

type RequestInitWithIdempotency = RequestInit & { idempotencyKey?: string };

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInitWithIdempotency
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string> | undefined),
  };
  const token = localStorage.getItem('access_token');
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (init?.idempotencyKey) headers['Idempotency-Key'] = init.idempotencyKey;
  const corrId = crypto.randomUUID();
  headers['X-Request-ID'] = corrId;

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      body.code ?? 'unknown',
      body.message ?? res.statusText,
      body.correlationId ?? corrId,
      body.fieldErrors
    );
  }
  const data = await res.json();
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    console.error('Zod parse error', parsed.error, data);
    throw new ApiError(500, 'invalid_response', 'Server returned invalid data', corrId);
  }
  return parsed.data;
}

export const api = {
  // Auth
  login: (body: { email: string; password: string }) =>
    request('/v1/auth/login', z.object({ access: z.string(), refresh: z.string(), user: UserSchema }),
      { method: 'POST', body: JSON.stringify(body) }),

  // Assets
  prepareUpload: (body: PrepareUploadRequest) =>
    request('/v1/assets:prepareUpload', PrepareUploadResponseSchema,
      { method: 'POST', body: JSON.stringify(body), idempotencyKey: crypto.randomUUID() }),

  // ... полный набор endpoints
};
```

### `schemas.ts`
- Все Zod-схемы, экспортируемые как TS-типы через `z.infer`.
- Соответствуют OpenAPI на 1:1.
- Генерируются через `openapi-typescript` + ручной refinement.

### `queries.ts`
- React Query hooks: `useJobs`, `useJob`, `useCreateJob`, `useReviews`, `useCreateReview`, `useWords`, `usePhraseTemplates`, `usePhraseSamples`, `useDecisions`, `useModels`, `useAudit`.
- Query keys: `['jobs', filters]`, `['job', id]`, `['words', filters]`, `['phrase', word, version]`, и т.д.
- Mutations: invalidate соответствующие query keys.

### `mutations.ts`
- `useCreateReview`, `usePromoteModel`, `useRebuildTemplate`.
- Optimistic updates.
- Error → rollback + toast.

### `ws.ts` (опционально)
- WebSocket для live job progress.
- Reconnect с exp backoff.
- Fallback на polling.
