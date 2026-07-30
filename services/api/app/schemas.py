from datetime import datetime
from enum import StrEnum
from uuid import UUID
from pydantic import BaseModel, Field

class JobStatus(StrEnum):
    QUEUED="QUEUED"; RUNNING="RUNNING"; SUCCEEDED="SUCCEEDED"; FAILED="FAILED"; INSUFFICIENT_DATA="INSUFFICIENT_DATA"
class DecisionLabel(StrEnum):
    CONSISTENT="CONSISTENT"; SUSPICIOUS="SUSPICIOUS"; INSUFFICIENT_DATA="INSUFFICIENT_DATA"
class ReviewVerdict(StrEnum):
    CONFIRMED_GENUINE="CONFIRMED_GENUINE"; CONFIRMED_SUSPICIOUS="CONFIRMED_SUSPICIOUS"; UNDECIDABLE="UNDECIDABLE"
class CreateAnalysisJob(BaseModel):
    asset_id: UUID
    claimed_person_id: UUID
    correlation_id: str | None = Field(default=None, max_length=128)
class Evidence(BaseModel):
    code: str; contribution: float = Field(ge=-1, le=1); message: str
    start_ms: int | None = Field(default=None, ge=0); end_ms: int | None = Field(default=None, ge=0)
class Decision(BaseModel):
    label: DecisionLabel; risk_score: float = Field(ge=0, le=1); quality_score: float = Field(ge=0, le=1)
    model_version: str; evidence: list[Evidence]
class AnalysisJob(BaseModel):
    id: UUID; status: JobStatus; created_at: datetime; decision: Decision | None = None
class CreateReview(BaseModel):
    verdict: ReviewVerdict; reason: str = Field(min_length=10, max_length=2000)
