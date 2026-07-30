from dataclasses import dataclass
from enum import StrEnum

class Stage(StrEnum):
    VALIDATE_ASSET="VALIDATE_ASSET"; EXTRACT_LANDMARKS="EXTRACT_LANDMARKS"; QUALITY_GATE="QUALITY_GATE"
    NORMALIZE="NORMALIZE"; SCORE="SCORE"; PERSIST_DECISION="PERSIST_DECISION"
@dataclass(frozen=True)
class PipelineContext:
    job_id: str; asset_uri: str; claimed_person_id: str; attempt: int

async def run_analysis_pipeline(context: PipelineContext) -> None:
    """MG-STUB: durable orchestration boundary.

    Implement as idempotent stages. Persist stage state before acknowledging a queue message.
    `INSUFFICIENT_DATA` is a successful terminal outcome; exceptions are operational failures.
    """
    raise NotImplementedError("MG-STUB: durable worker orchestration is not configured")
