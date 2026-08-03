// Typed API client. Zod-parsed responses on boundary.

import { z } from 'zod';

/// <reference types="vite/client" />
const API_BASE = (import.meta as any).env?.VITE_API_BASE_URL ?? '/api';

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public correlationId?: string,
    public fieldErrors?: Array<{ field: string; message: string; type?: string }>,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

type RequestInitWithExtras = RequestInit & { idempotencyKey?: string; raw?: boolean };

async function request<T>(
  path: string,
  schema: z.ZodType<T> | null,
  init?: RequestInitWithExtras,
  retryCount = 0,
): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (!(init?.body instanceof FormData) && !headers['Content-Type'] && init?.body) {
    headers['Content-Type'] = 'application/json';
  }
  const token = sessionStorage.getItem('access_token');
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (init?.idempotencyKey) headers['Idempotency-Key'] = init.idempotencyKey;
  const corrId = crypto.randomUUID();
  headers['X-Request-ID'] = corrId;

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (init?.raw) {
    if (!res.ok) {
      const text = await res.text();
      throw new ApiError(res.status, 'unknown', text || res.statusText, corrId);
    }
    return res as unknown as T;
  }
  if (res.status === 401 && retryCount === 0) {
    // Try to refresh token
    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
      try {
        const refreshRes = await fetch(`${API_BASE}/v1/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (refreshRes.ok) {
          const data = await refreshRes.json();
          localStorage.setItem('access_token', data.accessToken);
          localStorage.setItem('refresh_token', data.refreshToken);
          // Retry original request with new token
          return request(path, schema, init, 1);
        }
      } catch {
        // Refresh failed, will throw below
      }
    }
  }
  if (!res.ok) {
    let body: any = {};
    try { body = await res.json(); } catch { /* not JSON */ }
    throw new ApiError(
      res.status,
      body.code ?? 'unknown',
      body.message ?? res.statusText,
      body.correlationId ?? corrId,
      body.fieldErrors,
    );
  }
  if (res.status === 204) return undefined as unknown as T;
  const data = await res.json();
  if (!schema) return data as T;
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    console.error('Zod parse error', parsed.error, data);
    throw new ApiError(500, 'invalid_response', 'Server returned invalid data', corrId);
  }
  return parsed.data;
}

import {
  AnalysisJobSchema,
  AssetSchema,
  CurrentUserSchema,
  DashboardMetricsSchema,
  ModelVersionSchema,
  PhraseSampleSchema,
  PhraseTemplateDetailSchema,
  PhraseTemplateSummarySchema,
  ReviewSchema,
  SubjectSchema,
  WordSummarySchema,
} from './schemas';

export const api = {
  // Auth
  login: (email: string, password: string) =>
    request('/v1/auth/login', null, {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }) as Promise<{
      accessToken: string;
      refreshToken: string;
      tokenType: string;
      expiresIn: number;
      user: z.infer<typeof CurrentUserSchema>;
    }>,

  refresh: (refreshToken: string) =>
    request('/v1/auth/refresh', null, {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    }) as Promise<{ accessToken: string; refreshToken: string; expiresIn: number }>,

  me: () => request('/v1/auth/me', CurrentUserSchema) as Promise<z.infer<typeof CurrentUserSchema>>,

  // Dashboard
  dashboardMetrics: () =>
    request('/v1/dashboard/metrics', DashboardMetricsSchema) as Promise<
      z.infer<typeof DashboardMetricsSchema>
    >,

  // Assets
  prepareUpload: (body: {
    filename: string;
    mime: string;
    sizeBytes: number;
    title?: string;
  }) =>
    request('/v1/assets:prepareUpload', null, {
      method: 'POST',
      body: JSON.stringify(body),
      idempotencyKey: crypto.randomUUID(),
    }) as Promise<{
      assetId: string;
      uploadUrl: string;
      fields: Record<string, string>;
      objectKey: string;
      expiresIn: number;
    }>,

  completeUpload: (
    assetId: string,
    body: {
      sha256?: string;
      etag?: string;
      durationMs?: number;
      width?: number;
      height?: number;
      fps?: number;
      hasAudio?: boolean;
    },
  ) =>
    request(`/v1/assets/${assetId}:completeUpload`, AssetSchema, {
      method: 'POST',
      body: JSON.stringify(body),
    }) as Promise<z.infer<typeof AssetSchema>>,

  importFromUrl: (url: string, title?: string) =>
    request('/v1/assets:importFromUrl', null, {
      method: 'POST',
      body: JSON.stringify({ url, title }),
      idempotencyKey: crypto.randomUUID(),
    }) as Promise<{ taskId: string; assetId?: string; state: string; progress: number; error?: string }>,

  listAssets: (state?: string) =>
    request(`/v1/assets${state ? `?state=${state}` : ''}`, z.array(AssetSchema)) as Promise<
      z.infer<typeof AssetSchema>[]
    >,

  getAsset: (assetId: string) =>
    request(`/v1/assets/${assetId}`, AssetSchema) as Promise<z.infer<typeof AssetSchema>>,

  getAssetDownloadUrl: (assetId: string) =>
    request(`/v1/assets/${assetId}/downloadUrl`, null) as Promise<{
      url: string;
      expiresIn: number;
    }>,

  createClips: (
    assetId: string,
    body: {
      intervals: Array<{ startMs: number; endMs: number; label?: string }>;
      deleteSource: boolean;
    },
  ) =>
    request(`/v1/assets/${assetId}:createClips`, null, {
      method: 'POST',
      body: JSON.stringify(body),
      idempotencyKey: crypto.randomUUID(),
    }) as Promise<{
      clips: z.infer<typeof AssetSchema>[];
      sourceDeleted: boolean;
      codecProfile: string;
      totalDurationMs: number;
    }>,

  // Jobs
  listJobs: (filters?: { state?: string; subjectId?: string; limit?: number; cursor?: string }) => {
    const params = new URLSearchParams();
    if (filters?.state) params.set('state', filters.state);
    if (filters?.subjectId) params.set('subjectId', filters.subjectId);
    if (filters?.limit) params.set('limit', String(filters.limit));
    if (filters?.cursor) params.set('cursor', filters.cursor);
    const qs = params.toString();
    return request(`/v1/analysis-jobs${qs ? `?${qs}` : ''}`, z.array(AnalysisJobSchema)) as Promise<
      z.infer<typeof AnalysisJobSchema>[]
    >;
  },

  getJob: (id: string) =>
    request(`/v1/analysis-jobs/${id}`, AnalysisJobSchema) as Promise<z.infer<typeof AnalysisJobSchema>>,

  getJobArtifacts: (id: string) =>
    request(`/v1/analysis-jobs/${id}/artifacts`, null) as Promise<{
      videoUrl: string;
      landmarksUrl?: string;
      durationMs: number;
      fps: number;
      expiresIn: number;
    }>,

  createJob: (body: { assetId: string; claimedPersonId: string; pipelineVersion?: string }) =>
    request('/v1/analysis-jobs', AnalysisJobSchema, {
      method: 'POST',
      body: JSON.stringify(body),
      idempotencyKey: crypto.randomUUID(),
    }) as Promise<z.infer<typeof AnalysisJobSchema>>,

  cancelJob: (id: string) =>
    request(`/v1/analysis-jobs/${id}:cancel`, AnalysisJobSchema, { method: 'POST' }) as Promise<
      z.infer<typeof AnalysisJobSchema>
    >,

  retryJob: (id: string) =>
    request(`/v1/analysis-jobs/${id}:retry`, AnalysisJobSchema, { method: 'POST' }) as Promise<
      z.infer<typeof AnalysisJobSchema>
    >,

  // Subjects
  listSubjects: () =>
    request('/v1/subjects', z.array(SubjectSchema)) as Promise<z.infer<typeof SubjectSchema>[]>,

  getSubject: (id: string) =>
    request(`/v1/subjects/${id}`, SubjectSchema) as Promise<z.infer<typeof SubjectSchema>>,

  createSubject: (body: { externalId: string; displayName: string; consentState?: string }) =>
    request('/v1/subjects', SubjectSchema, {
      method: 'POST',
      body: JSON.stringify(body),
    }) as Promise<z.infer<typeof SubjectSchema>>,

  updateSubject: (id: string, body: Partial<{ displayName: string; consentState: string; retentionPolicy: object; version: number }>) =>
    request(`/v1/subjects/${id}`, SubjectSchema, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }) as Promise<z.infer<typeof SubjectSchema>>,

  recordConsent: (id: string, body: { state: string; signedBy?: string; evidenceUri?: string }) =>
    request(`/v1/subjects/${id}/consent`, null, {
      method: 'POST',
      body: JSON.stringify(body),
    }) as Promise<unknown>,

  // Words
  listWords: (filters?: { language?: string; subjectId?: string; limit?: number; cursor?: string }) => {
    const params = new URLSearchParams();
    if (filters?.language) params.set('language', filters.language);
    if (filters?.subjectId) params.set('subjectId', filters.subjectId);
    if (filters?.limit) params.set('limit', String(filters.limit));
    if (filters?.cursor) params.set('cursor', filters.cursor);
    const qs = params.toString();
    return request(`/v1/words${qs ? `?${qs}` : ''}`, z.array(WordSummarySchema)) as Promise<
      z.infer<typeof WordSummarySchema>[]
    >;
  },

  listTemplates: (word: string, language = 'en', subjectId?: string) => {
    const query = new URLSearchParams({ language });
    if (subjectId) query.set('subjectId', subjectId);
    return request(
      `/v1/words/${encodeURIComponent(word)}/templates?${query.toString()}`,
      z.array(PhraseTemplateSummarySchema),
    ) as Promise<z.infer<typeof PhraseTemplateSummarySchema>[]>;
  },

  getTemplate: (word: string, templateId: string) =>
    request(`/v1/words/${encodeURIComponent(word)}/templates/${templateId}`, PhraseTemplateDetailSchema) as Promise<
      z.infer<typeof PhraseTemplateDetailSchema>
    >,

  listSamplesForWord: (
    word: string,
    language = 'en',
    templateId?: string,
    _limit?: number,
    subjectId?: string,
  ) => {
    const qs = new URLSearchParams({ language });
    if (templateId) qs.set('templateId', templateId);
    if (subjectId) qs.set('subjectId', subjectId);
    return request(
      `/v1/words/${encodeURIComponent(word)}/samples?${qs.toString()}`,
      z.array(PhraseSampleSchema),
    ) as Promise<z.infer<typeof PhraseSampleSchema>[]>;
  },

  getSampleUrls: (word: string, sampleId: string) =>
    request(
      `/v1/words/${encodeURIComponent(word)}/samples/${sampleId}/urls`,
      null,
    ) as Promise<{
      videoClipUrl: string;
      landmarksUrl: string;
      audioClipUrl?: string;
      videoInPointMs: number;
      videoOutPointMs: number;
      expiresIn: number;
    }>,

  // Reviews
  listReviews: (filters?: { verdict?: string; reviewerId?: string; decisionId?: string; limit?: number; cursor?: string }) => {
    const params = new URLSearchParams();
    if (filters?.verdict) params.set('verdict', filters.verdict);
    if (filters?.reviewerId) params.set('reviewerId', filters.reviewerId);
    if (filters?.decisionId) params.set('decisionId', filters.decisionId);
    if (filters?.limit) params.set('limit', String(filters.limit));
    if (filters?.cursor) params.set('cursor', filters.cursor);
    const qs = params.toString();
    return request(`/v1/reviews${qs ? `?${qs}` : ''}`, z.array(ReviewSchema)) as Promise<
      z.infer<typeof ReviewSchema>[]
    >;
  },

  createReview: (body: {
    decisionId: string;
    verdict: string;
    reason: string;
    confidence?: number;
  }) =>
    request('/v1/reviews', ReviewSchema, {
      method: 'POST',
      body: JSON.stringify(body),
    }) as Promise<z.infer<typeof ReviewSchema>>,

  // Models
  listModels: (filters?: { kind?: string; state?: string }) => {
    const params = new URLSearchParams();
    if (filters?.kind) params.set('kind', filters.kind);
    if (filters?.state) params.set('state', filters.state);
    const qs = params.toString();
    return request(`/v1/models${qs ? `?${qs}` : ''}`, z.array(ModelVersionSchema)) as Promise<
      z.infer<typeof ModelVersionSchema>[]
    >;
  },

  getModel: (id: string) =>
    request(`/v1/models/${id}`, ModelVersionSchema) as Promise<z.infer<typeof ModelVersionSchema>>,

  promoteModel: (id: string, toState: string, reason: string) =>
    request(`/v1/models/${id}:promote`, ModelVersionSchema, {
      method: 'POST',
      body: JSON.stringify({ toState, reason }),
    }) as Promise<z.infer<typeof ModelVersionSchema>>,

  // Audit
  listAudit: (filters?: { actorId?: string; action?: string; resourceType?: string; limit?: number; cursor?: string }) => {
    const params = new URLSearchParams();
    if (filters?.actorId) params.set('actorId', filters.actorId);
    if (filters?.action) params.set('action', filters.action);
    if (filters?.resourceType) params.set('resourceType', filters.resourceType);
    if (filters?.limit) params.set('limit', String(filters.limit));
    if (filters?.cursor) params.set('cursor', filters.cursor);
    const qs = params.toString();
    return request(`/v1/audit${qs ? `?${qs}` : ''}`, null) as Promise<unknown[]>;
  },
};

export function isPermissionError(e: unknown): boolean {
  return e instanceof ApiError && e.status === 403;
}
export function isAuthError(e: unknown): boolean {
  return e instanceof ApiError && e.status === 401;
}
