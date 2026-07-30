# Module 24: Quality gate

**Путь:** `packages/landmark_engine/quality.py` — уже реализован в каркасе.
**Путь:** `packages/landmark_engine/quality_features.py` (новый)

## `assess_quality(sequence)` — финальный
- Возвращает `QualityAssessment(accepted, score, failures, metrics)`.
- `accepted` = `len(failures) == 0` AND `score >= 0.55`.
- Настраиваемые thresholds через `MG_QUALITY_CONFIG` env.

## `quality_features.py` (новый)
```python
"""
MG-STUB: реализовать расширенный quality report с per-region diagnostics.
"""
from dataclasses import dataclass
from .domain import LandmarkSequence

@dataclass(frozen=True)
class RegionQuality:
    region: str       # mouth|jaw|cheeks|eyes|brows
    coverage: float   # доля frames с валидной детекцией в регионе
    motion_range: float  # амплитуда движения (max - min) в нормализованных координатах
    gap_ms: int       # максимальный gap в регионе

@dataclass(frozen=True)
class ExtendedQualityReport:
    base: "QualityAssessment"
    regions: list[RegionQuality]
    motion_distribution: dict[str, float]   # mean/std per region
    pose_coverage: dict[str, float]          # доля времени в каждом диапазоне yaw/pitch/roll

def assess_extended_quality(seq: LandmarkSequence) -> ExtendedQualityReport:
    # 1. base = assess_quality(seq)
    # 2. для каждой region group: coverage, motion_range, gap_ms
    # 3. motion_distribution: mean/std per region feature
    # 4. pose_coverage: bins [-45,-15), [-15,15), [15,45)
    pass
```

## Что показывать в админке
- Quality score с breakdown (confidence, gaps, pose).
- Evidence codes (если есть failures).
- Регионы: визуальная карта (heatmap) coverage и motion.
- Pose coverage: гистограмма.
