import itertools
from statistics import fmean

from .domain import LandmarkSequence, QualityAssessment, QualityFailure

MIN_FRAMES = 15
MIN_MEAN_CONFIDENCE = 0.72
MAX_GAP_MS = 180
MAX_ABS_YAW = 45.0


def assess_quality(sequence: LandmarkSequence) -> QualityAssessment:
    """Deterministic gate before normalization/scoring.

    This implementation is final for the documented v1 thresholds. Thresholds must be
    configuration-backed before production calibration, but failures must remain explicit.
    """
    failures: list[QualityFailure] = []
    frames = tuple(sequence.frames)
    if len(frames) < MIN_FRAMES:
        failures.append(QualityFailure.TOO_FEW_FRAMES)
    mean_confidence = fmean(f.confidence for f in frames) if frames else 0.0
    if mean_confidence < MIN_MEAN_CONFIDENCE:
        failures.append(QualityFailure.LOW_TRACKING_CONFIDENCE)
    gaps = [b.timestamp_ms - a.timestamp_ms for a, b in itertools.pairwise(frames)]
    max_gap = max(gaps, default=0)
    if max_gap > MAX_GAP_MS:
        failures.append(QualityFailure.EXCESSIVE_GAPS)
    max_yaw = max((abs(f.head_pose.yaw) for f in frames), default=0.0)
    if max_yaw > MAX_ABS_YAW:
        failures.append(QualityFailure.EXCESSIVE_HEAD_POSE)
    confidence_component = min(1.0, mean_confidence / 0.9)
    continuity_component = max(0.0, 1.0 - max_gap / 500.0)
    pose_component = max(0.0, 1.0 - max_yaw / 90.0)
    score = round(0.5 * confidence_component + 0.3 * continuity_component + 0.2 * pose_component, 4)
    return QualityAssessment(not failures, score, tuple(failures), {
        "frame_count": float(len(frames)), "mean_confidence": mean_confidence,
        "max_gap_ms": float(max_gap), "max_abs_yaw": max_yaw,
    })
