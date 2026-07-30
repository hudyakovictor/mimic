from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum


class QualityFailure(StrEnum):
    TOO_FEW_FRAMES = "TOO_FEW_FRAMES"
    LOW_TRACKING_CONFIDENCE = "LOW_TRACKING_CONFIDENCE"
    EXCESSIVE_GAPS = "EXCESSIVE_GAPS"
    EXCESSIVE_HEAD_POSE = "EXCESSIVE_HEAD_POSE"
    INSUFFICIENT_MOUTH_MOTION = "INSUFFICIENT_MOUTH_MOTION"

@dataclass(frozen=True, slots=True)
class Point3D:
    x: float
    y: float
    z: float

@dataclass(frozen=True, slots=True)
class HeadPose:
    yaw: float
    pitch: float
    roll: float

@dataclass(frozen=True, slots=True)
class LandmarkFrame:
    """One timestamped observation. Coordinates are image-normalized at extraction time."""
    timestamp_ms: int
    points: Mapping[int, Point3D]
    confidence: float
    head_pose: HeadPose

@dataclass(frozen=True, slots=True)
class LandmarkSequence:
    """Ordered frames from exactly one stable face track."""
    track_id: str
    schema_version: str
    frames: Sequence[LandmarkFrame]
    source_fps: float

@dataclass(frozen=True, slots=True)
class QualityAssessment:
    accepted: bool
    score: float
    failures: tuple[QualityFailure, ...] = field(default_factory=tuple)
    metrics: Mapping[str, float] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class NormalizedFrame:
    timestamp_ms: int
    vector: tuple[float, ...]
    confidence: float

@dataclass(frozen=True, slots=True)
class NormalizedSequence:
    track_id: str
    feature_schema_version: str
    frames: tuple[NormalizedFrame, ...]
