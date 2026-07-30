from math import hypot

from .domain import LandmarkSequence, NormalizedFrame, NormalizedSequence

# Stable MediaPipe-like anchor IDs; adapters must map their schema to these semantic anchors.
LEFT_EYE_OUTER, RIGHT_EYE_OUTER, NOSE_TIP = 33, 263, 1
MOTION_POINTS = (61, 291, 13, 14, 78, 308, 152, 234, 454, 50, 280)


def normalize_sequence(sequence: LandmarkSequence) -> NormalizedSequence:
    """Remove translation and scale, retaining only high-value facial motion.

    Rotation compensation is intentionally delegated to a calibrated 3D adapter (`MG-STUB`)
    because a naive 2D rotation would create false biometric evidence. This function fails
    loudly when semantic anchors are absent.
    """
    output: list[NormalizedFrame] = []
    for frame in sequence.frames:
        missing = [idx for idx in (LEFT_EYE_OUTER, RIGHT_EYE_OUTER, NOSE_TIP, *MOTION_POINTS) if idx not in frame.points]
        if missing:
            raise ValueError(f"Landmark schema is missing required semantic points: {missing}")
        left, right, nose = frame.points[LEFT_EYE_OUTER], frame.points[RIGHT_EYE_OUTER], frame.points[NOSE_TIP]
        scale = hypot(right.x - left.x, right.y - left.y)
        if scale <= 1e-8:
            raise ValueError("Degenerate eye distance; frame cannot be normalized")
        vector: list[float] = []
        for idx in MOTION_POINTS:
            p = frame.points[idx]
            vector.extend(((p.x - nose.x) / scale, (p.y - nose.y) / scale, (p.z - nose.z) / scale))
        output.append(NormalizedFrame(frame.timestamp_ms, tuple(vector), frame.confidence))
    return NormalizedSequence(sequence.track_id, "motion-v1", tuple(output))
