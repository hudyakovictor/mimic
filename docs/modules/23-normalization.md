# Module 23: Normalization & features

**Путь:** `packages/landmark_engine/normalization.py` + `packages/landmark_engine/features.py`

## `normalize_sequence(sequence)` — уже реализовано в каркасе
- Translation: subtract nose_tip.
- Scale: divide by eye distance.
- Output: NormalizedSequence с vector = 11 motion points × 3 coords = 33 dims.
- Schema: `motion-v1`.

## `features.py` (доделать)

```python
"""
MG-STUB: реализовать.
"""
import numpy as np
from .domain import NormalizedSequence, NormalizedFrame

FEATURE_SCHEMA = "motion-features-v1"

# Семантические индексы внутри vector (33-dim)
MOUTH_OUTER_L = (61 - 61) * 3   # offset в vector для mouth_outer_l
# (см. MOTION_POINTS в normalization.py)
LIP_CORNER_LEFT_X = 0   # mouth_outer_l x
LIP_CORNER_LEFT_Y = 1   # mouth_outer_l y
LIP_CORNER_RIGHT_X = 6  # mouth_outer_r x
LIP_CORNER_RIGHT_Y = 7
MOUTH_INNER_TOP_Y = 9   # mouth_inner_top y
MOUTH_INNER_BOTTOM_Y = 15  # mouth_inner_bottom y
CHIN_Y = 21             # chin y
JAW_LEFT_X = 24         # jaw_l x
JAW_LEFT_Y = 25
JAW_RIGHT_X = 27
JAW_RIGHT_Y = 28
CHEEK_UPPER_LEFT_Y = 31
CHEEK_UPPER_RIGHT_Y = 37


def derive_features(seq: NormalizedSequence) -> "FeatureSequence":
    """Compute motion features per frame + temporal derivatives.
    Output shape per frame: ~12 features (regional ratios + derivatives).
    """
    vectors = np.array([f.vector for f in seq.frames])  # (T, 33)
    n = len(vectors)
    features = []

    for i in range(n):
        v = vectors[i]
        row = []
        # 1. mouth opening (inner bottom - inner top), normalized by eye distance (already in normalized space)
        mouth_open = abs(v[MOUTH_INNER_BOTTOM_Y] - v[MOUTH_INNER_TOP_Y])
        # 2. mouth width (right corner - left corner)
        mouth_width = abs(v[LIP_CORNER_RIGHT_X] - v[LIP_CORNER_LEFT_X])
        # 3. mouth aspect ratio
        mouth_ratio = mouth_open / max(mouth_width, 1e-6)
        # 4. lip asymmetry (left corner y - right corner y)
        lip_asym = v[LIP_CORNER_LEFT_Y] - v[LIP_CORNER_RIGHT_Y]
        # 5. jaw opening
        jaw_open = abs(v[JAW_LEFT_Y] - v[JAW_RIGHT_Y])
        # 6. cheek raise (avg upper cheek y - inner brow y, normalized)
        cheek_left = v[CHEEK_UPPER_LEFT_Y]
        cheek_right = v[CHEEK_UPPER_RIGHT_Y]
        cheek_raise = (cheek_left + cheek_right) / 2.0
        # 7-12. velocity / acceleration of mouth_open
        if i >= 1:
            d_mouth_open = mouth_open - features[-1][0]
        else:
            d_mouth_open = 0.0
        if i >= 2:
            dd_mouth_open = d_mouth_open - features[-1][6]
        else:
            dd_mouth_open = 0.0

        row.extend([
            mouth_open, mouth_width, mouth_ratio,
            lip_asym, jaw_open, cheek_raise,
            d_mouth_open, dd_mouth_open,
        ])
        features.append(row)

    return FeatureSequence(
        track_id=seq.track_id,
        schema_version=FEATURE_SCHEMA,
        frames=tuple(features),
    )


class FeatureSequence:
    def __init__(self, track_id: str, schema_version: str, frames: list[list[float]]):
        self.track_id = track_id
        self.schema_version = schema_version
        self.frames = frames
```

## `time_warp.py` (новый файл)

```python
"""
MG-STUB: реализовать.
"""
import numpy as np

def resample_to_length(curve: np.ndarray, target_length: int = 30) -> np.ndarray:
    """Linear interpolation resample to fixed length."""
    src_length = len(curve)
    if src_length == target_length:
        return curve
    src_idx = np.linspace(0, src_length - 1, src_length)
    tgt_idx = np.linspace(0, src_length - 1, target_length)
    out = np.zeros((target_length, curve.shape[1]) if curve.ndim > 1 else (target_length,))
    if curve.ndim > 1:
        for d in range(curve.shape[1]):
            out[:, d] = np.interp(tgt_idx, src_idx, curve[:, d])
    else:
        out = np.interp(tgt_idx, src_idx, curve)
    return out
```
