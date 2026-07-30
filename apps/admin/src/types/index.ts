// API types — mirror backend Pydantic schemas (camelCase on wire)

export type JobStatus = 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'INSUFFICIENT_DATA';
export type DecisionLabel = 'CONSISTENT' | 'SUSPICIOUS' | 'INSUFFICIENT_DATA';
export type ReviewVerdict = 'CONFIRMED_GENUINE' | 'CONFIRMED_SUSPICIOUS' | 'UNDECIDABLE';
export type AssetState = 'PENDING_UPLOAD' | 'UPLOADING' | 'READY' | 'FAILED' | 'DELETED';
export type ConsentState = 'PENDING' | 'GRANTED' | 'REVOKED';
export type ModelKind = 'LANDMARK_EXTRACTOR' | 'ASR' | 'MOTION_SCORER' | 'CALIBRATION';
export type ModelState = 'DRAFT' | 'VALIDATED' | 'SHADOW' | 'ACTIVE' | 'RETIRED';

export interface CurrentUser {
  id: string;
  email: string;
  displayName: string;
  roles: string[];
  tenantId: string;
  tenantSlug: string;
}

export interface Evidence {
  code: string;
  contribution: number;
  message: string;
  startMs?: number;
  endMs?: number;
  word?: string;
}

export interface PhraseInstance {
  word: string;
  language: string;
  startMs: number;
  endMs: number;
  similarity: number;
  confidence: number;
  hasMatureBaseline: boolean;
  evidence: Evidence[];
}

export interface Decision {
  id: string;
  jobId: string;
  label: DecisionLabel;
  riskScore: number;
  qualityScore: number;
  modelVersion: string;
  modelChecksum: string;
  evidence: Evidence[];
  phraseInstances: PhraseInstance[];
  createdAt: string;
}

export interface JobStage {
  id: string;
  name: string;
  state: string;
  startedAt?: string;
  completedAt?: string;
  error?: string;
  outputUri?: string;
}

export interface AnalysisJob {
  id: string;
  assetId: string;
  subjectId: string;
  pipelineVersion: string;
  state: JobStatus;
  attempt: number;
  lastError?: string;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
  decision?: Decision;
  stages: JobStage[];
}

export interface Subject {
  id: string;
  externalId: string;
  displayName: string;
  consentState: ConsentState;
  retentionPolicy: Record<string, unknown>;
  nJobs: number;
  nBaselines: number;
  lastAnalyzedAt?: string;
  createdAt: string;
  version: number;
}

export interface Asset {
  id: string;
  sourceType: 'UPLOAD' | 'YOUTUBE' | 'URL' | 'CLIP';
  sourceUrl?: string;
  mime: string;
  sizeBytes: number;
  sha256?: string;
  durationMs?: number;
  width?: number;
  height?: number;
  fps?: number;
  hasAudio: boolean;
  state: AssetState;
  title?: string;
  failureReason?: string;
  extra: Record<string, unknown>;
  createdAt: string;
}

export interface WordSummary {
  word: string;
  language: string;
  subjectId?: string;
  nTemplates: number;
  nSamples: number;
  hasMatureBaseline: boolean;
  lastDecisionLabel?: DecisionLabel;
  lastUpdated?: string;
}

export interface PhraseTemplateSummary {
  id: string;
  subjectId?: string;
  word: string;
  language: string;
  version: number;
  nSamples: number;
  isMature: boolean;
  state: string;
  modelVersion: string;
  createdAt: string;
}

export interface PhraseTemplateDetail extends PhraseTemplateSummary {
  meanCurve: number[][];
  regionalStats: Record<string, number>;
  sampleIds: string[];
  parentId?: string;
}

export interface PhraseSample {
  id: string;
  templateId: string;
  decisionId: string;
  reviewId: string;
  word: string;
  language: string;
  startMs: number;
  endMs: number;
  confidence: number;
  nFrames: number;
  meanDtwToTemplate?: number;
  createdAt: string;
}

export interface SampleUrls {
  videoClipUrl: string;
  landmarksUrl: string;
  audioClipUrl?: string;
  expiresIn: number;
}

export interface Review {
  id: string;
  decisionId: string;
  reviewerId: string;
  reviewerName: string;
  verdict: ReviewVerdict;
  reason: string;
  confidence?: number;
  createdAt: string;
}

export interface ModelVersion {
  id: string;
  kind: ModelKind;
  version: string;
  artifactChecksum: string;
  codeCommit: string;
  featureSchema: string;
  state: ModelState;
  intendedUse: string;
  knownLimitations: string;
  evaluationReport: Record<string, unknown>;
  calibrationProfile: Record<string, unknown>;
  approverId?: string;
  approvedAt?: string;
  promotedBy?: string;
  promotedAt?: string;
  createdAt: string;
}

export interface AuditEvent {
  id: string;
  actorId?: string;
  action: string;
  resourceType: string;
  resourceId?: string;
  at: string;
  ip?: string;
  correlationId?: string;
  reason?: string;
}

export interface DashboardMetrics {
  pendingReviews: number;
  qualityOkRatio: number;
  medianProcessingSeconds: number;
  reviewerAgreement: number;
  jobsLast7d: Array<{ date: string; count: number; suspicious: number }>;
  recentAnalyses: AnalysisJob[];
}
