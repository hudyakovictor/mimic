from typing import BinaryIO, Protocol

from .domain import LandmarkSequence, NormalizedSequence


class LandmarkExtractor(Protocol):
    """Adapter boundary for MediaPipe or another landmark detector."""
    def extract(self, video: BinaryIO, *, track_id: str) -> LandmarkSequence: ...

class MotionScorer(Protocol):
    """Versioned model that compares probe motion against a verified baseline."""
    @property
    def model_version(self) -> str: ...
    def score(self, probe: NormalizedSequence, baseline_uri: str) -> "ScoreResult": ...

class ScoreResult(Protocol):
    risk_score: float
    evidence: tuple[object, ...]
