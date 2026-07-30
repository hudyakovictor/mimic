// Zod schemas — mirror backend Pydantic models. Wire format = camelCase.

import { z } from 'zod';

export const EvidenceSchema = z.object({
  code: z.string(),
  contribution: z.number(),
  message: z.string(),
  startMs: z.number().optional(),
  endMs: z.number().optional(),
  word: z.string().optional(),
});

export const PhraseInstanceSchema = z.object({
  word: z.string(),
  language: z.string(),
  startMs: z.number(),
  endMs: z.number(),
  similarity: z.number(),
  confidence: z.number(),
  hasMatureBaseline: z.boolean(),
  evidence: z.array(EvidenceSchema),
});

export const DecisionSchema = z.object({
  id: z.string(),
  jobId: z.string(),
  label: z.enum(['CONSISTENT', 'SUSPICIOUS', 'INSUFFICIENT_DATA']),
  riskScore: z.number(),
  qualityScore: z.number(),
  modelVersion: z.string(),
  modelChecksum: z.string(),
  evidence: z.array(EvidenceSchema),
  phraseInstances: z.array(PhraseInstanceSchema),
  createdAt: z.string(),
});

export const JobStageSchema = z.object({
  id: z.string(),
  name: z.string(),
  state: z.string(),
  startedAt: z.string().optional(),
  completedAt: z.string().optional(),
  error: z.string().optional(),
  outputUri: z.string().optional(),
});

export const AnalysisJobSchema = z.object({
  id: z.string(),
  assetId: z.string(),
  subjectId: z.string(),
  pipelineVersion: z.string(),
  state: z.enum(['QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'INSUFFICIENT_DATA']),
  attempt: z.number(),
  lastError: z.string().optional(),
  createdAt: z.string(),
  startedAt: z.string().optional(),
  finishedAt: z.string().optional(),
  decision: DecisionSchema.optional(),
  stages: z.array(JobStageSchema),
});

export const SubjectSchema = z.object({
  id: z.string(),
  externalId: z.string(),
  displayName: z.string(),
  consentState: z.enum(['PENDING', 'GRANTED', 'REVOKED']),
  retentionPolicy: z.record(z.unknown()),
  nJobs: z.number(),
  nBaselines: z.number(),
  lastAnalyzedAt: z.string().optional(),
  createdAt: z.string(),
  version: z.number(),
});

export const AssetSchema = z.object({
  id: z.string(),
  sourceType: z.enum(['UPLOAD', 'YOUTUBE', 'URL']),
  sourceUrl: z.string().optional(),
  mime: z.string(),
  sizeBytes: z.number(),
  sha256: z.string().optional(),
  durationMs: z.number().optional(),
  width: z.number().optional(),
  height: z.number().optional(),
  fps: z.number().optional(),
  hasAudio: z.boolean(),
  state: z.enum(['PENDING_UPLOAD', 'UPLOADING', 'READY', 'FAILED', 'DELETED']),
  title: z.string().optional(),
  failureReason: z.string().optional(),
  createdAt: z.string(),
});

export const WordSummarySchema = z.object({
  word: z.string(),
  language: z.string(),
  nTemplates: z.number(),
  nSamples: z.number(),
  hasMatureBaseline: z.boolean(),
  lastDecisionLabel: z.enum(['CONSISTENT', 'SUSPICIOUS', 'INSUFFICIENT_DATA']).optional(),
  lastUpdated: z.string().optional(),
});

export const PhraseTemplateSummarySchema = z.object({
  id: z.string(),
  subjectId: z.string().optional(),
  word: z.string(),
  language: z.string(),
  version: z.number(),
  nSamples: z.number(),
  isMature: z.boolean(),
  state: z.string(),
  modelVersion: z.string(),
  createdAt: z.string(),
});

export const PhraseTemplateDetailSchema = PhraseTemplateSummarySchema.extend({
  meanCurve: z.array(z.array(z.number())),
  regionalStats: z.record(z.number()),
  sampleIds: z.array(z.string()),
  parentId: z.string().optional(),
});

export const PhraseSampleSchema = z.object({
  id: z.string(),
  templateId: z.string(),
  decisionId: z.string(),
  reviewId: z.string(),
  word: z.string(),
  language: z.string(),
  startMs: z.number(),
  endMs: z.number(),
  confidence: z.number(),
  nFrames: z.number(),
  meanDtwToTemplate: z.number().optional(),
  createdAt: z.string(),
});

export const ReviewSchema = z.object({
  id: z.string(),
  decisionId: z.string(),
  reviewerId: z.string(),
  reviewerName: z.string(),
  verdict: z.enum(['CONFIRMED_GENUINE', 'CONFIRMED_SUSPICIOUS', 'UNDECIDABLE']),
  reason: z.string(),
  confidence: z.number().optional(),
  createdAt: z.string(),
});

export const ModelVersionSchema = z.object({
  id: z.string(),
  kind: z.enum(['LANDMARK_EXTRACTOR', 'ASR', 'MOTION_SCORER', 'CALIBRATION']),
  version: z.string(),
  artifactChecksum: z.string(),
  codeCommit: z.string(),
  featureSchema: z.string(),
  state: z.enum(['DRAFT', 'VALIDATED', 'SHADOW', 'ACTIVE', 'RETIRED']),
  intendedUse: z.string(),
  knownLimitations: z.string(),
  evaluationReport: z.record(z.unknown()),
  calibrationProfile: z.record(z.unknown()),
  approverId: z.string().optional(),
  approvedAt: z.string().optional(),
  promotedBy: z.string().optional(),
  promotedAt: z.string().optional(),
  createdAt: z.string(),
});

export const AuditEventSchema = z.object({
  id: z.string(),
  actorId: z.string().optional(),
  action: z.string(),
  resourceType: z.string(),
  resourceId: z.string().optional(),
  at: z.string(),
  ip: z.string().optional(),
  correlationId: z.string().optional(),
  reason: z.string().optional(),
});

export const CurrentUserSchema = z.object({
  id: z.string(),
  email: z.string().email(),
  displayName: z.string(),
  roles: z.array(z.string()),
  tenantId: z.string(),
  tenantSlug: z.string(),
});

export const DashboardMetricsSchema = z.object({
  pendingReviews: z.number(),
  qualityOkRatio: z.number(),
  medianProcessingSeconds: z.number(),
  reviewerAgreement: z.number(),
  jobsLast7d: z.array(z.object({ date: z.string(), count: z.number(), suspicious: z.number() })),
  recentAnalyses: z.array(AnalysisJobSchema),
});
