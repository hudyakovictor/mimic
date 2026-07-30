# Landmark pipeline

## Input contract
One media asset and claimed subject. The adapter emits per-frame semantic landmarks, confidence, head pose and source timestamp.

## Stages
1. Validate codec, duration, time base and corruption.
2. Extract candidate face tracks.
3. Select or request review of the target track.
4. Quality gate: count, confidence, gaps, pose and usable motion.
5. Normalize translation/scale; calibrated adapter handles 3D rotation.
6. Derive displacement, velocity, acceleration and regional ratios.
7. Window sequence by time and, later, speech context.
8. Score against a versioned subject baseline.
9. Calibrate and create evidence.

## High-value points
Eye corners and nose are stable anchors. The first feature schema prioritizes mouth corners, inner/outer lips, chin, lateral cheeks and upper cheek points. More points are added only if an ablation proves value.

## Missing data
Never forward-fill large gaps. Gaps under a calibrated limit may be interpolated only in a versioned preprocessing adapter and must produce a mask channel. If quality is inadequate, stop with `INSUFFICIENT_DATA`.

## Evidence codes
`MOUTH_CHEEK_LAG`, `JAW_RANGE_LOW`, `LIP_ASYMMETRY`, `MOTION_TIMING_SHIFT`, `BASELINE_DISTANCE_HIGH`, plus quality failures. Each code carries contribution and interval.
