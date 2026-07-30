# Module 27: Baseline store (DTW + Mahalanobis)

**Путь:** `services/worker/app/baseline/`

## Файлы

### `dtw.py`
```python
"""
MG-STUB: реализовать DTW.
"""
import numpy as np

def dtw_distance(a: np.ndarray, b: np.ndarray, window: int | None = None) -> tuple[float, np.ndarray]:
    """Dynamic Time Warping distance.
    a, b: shape (T, D)
    Returns: (distance, path) where path is list of (i, j) indices.
    Sakoe-Chiba band if window is set.
    """
    n, m = len(a), len(b)
    cost = np.full((n + 1, m + 1), np.inf)
    cost[0, 0] = 0.0
    for i in range(1, n + 1):
        j_start = 1 if window is None else max(1, i - window)
        j_end = min(m, (i + window) if window is not None else m)
        for j in range(j_start, j_end + 1):
            d = np.linalg.norm(a[i-1] - b[j-1])
            cost[i, j] = d + min(cost[i-1, j], cost[i, j-1], cost[i-1, j-1])
    # backtrack path
    path = []
    i, j = n, m
    while i > 0 and j > 0:
        path.append((i-1, j-1))
        candidates = [(i-1, j-1), (i-1, j), (i, j-1)]
        costs = [cost[i-1, j-1], cost[i-1, j], cost[i, j-1]]
        k = int(np.argmin(costs))
        di, dj = candidates[k]
        i, j = di, dj
    path.reverse()
    return cost[n, m] / max(n, m), path  # normalized by length


def dtw_slope(path: list[tuple[int, int]]) -> float:
    """Compute slope of DTW path. > 1.3 = probe is slower, < 0.7 = faster."""
    n = len(path)
    if n < 2:
        return 1.0
    # Use linear regression slope
    xs = np.array([p[0] for p in path], dtype=float)
    ys = np.array([p[1] for p in path], dtype=float)
    slope = np.polyfit(xs, ys, 1)[0]
    return float(slope)


def dtw_phase_delay(path: list[tuple[int, int]], axis: int = 0) -> float:
    """Average time difference in milliseconds between matched frames."""
    # path[i] = (a_idx, b_idx) — for matching frame a_idx in probe to b_idx in template
    # phase_delay_ms = (b_idx - a_idx) * 1000 / fps
    pass
```

### `mahalanobis.py`
```python
"""
MG-STUB: реализовать Mahalanobis distance.
"""
import numpy as np

def mahalanobis(x: np.ndarray, mean: np.ndarray, cov_diag: np.ndarray) -> float:
    """Mahalanobis distance for diagonal covariance.
    x, mean: shape (D,)
    cov_diag: shape (D,)
    """
    d = x - mean
    return float(np.sqrt(np.sum(d * d / np.maximum(cov_diag, 1e-8))))


def chi2_threshold(dims: int, alpha: float = 0.05) -> float:
    """Chi-squared critical value for given dims and alpha."""
    from scipy.stats import chi2
    return float(chi2.ppf(1 - alpha, df=dims))
```

### `template.py`
```python
"""
MG-STUB: PhraseTemplate — структура и агрегация.
"""
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class PhraseTemplate:
    id: str
    subject_id: str | None   # None = global
    word: str
    language: str
    version: int
    parent_id: Optional[str]
    n_samples: int
    mean_curve: np.ndarray       # shape (30, n_dims)
    cov_diag: np.ndarray         # shape (30, n_dims) or (n_dims,)
    regional_stats: dict         # {"mouth_open": (mu, sigma), ...}
    samples: list[str] = field(default_factory=list)  # sample_ids
    model_version: str = "statistical-v1"
    created_at_ms: int = 0

    @classmethod
    def build(cls, samples: list, **kwargs) -> "PhraseTemplate":
        """Build template from list of PhraseSample (with .landmarks_slice + .features_slice)."""
        if not samples:
            raise ValueError("No samples")
        # Stack landmarks: shape (N, 30, 33)
        all_lmk = np.stack([s.landmarks_slice for s in samples])
        mean_curve = all_lmk.mean(axis=0)
        # covariance: per-dim variance over samples
        cov_diag = all_lmk.var(axis=0)  # shape (30, 33)
        # regional stats from features
        feats = np.stack([s.features_slice for s in samples])  # (N, 30, n_features)
        feats_mean = feats.mean(axis=(0, 1))  # (n_features,)
        feats_std = feats.std(axis=(0, 1))
        regional_stats = {
            "mouth_open_mu": float(feats_mean[0]),
            "mouth_open_sigma": float(feats_std[0]),
            "mouth_ratio_mu": float(feats_mean[2]),
            "mouth_ratio_sigma": float(feats_std[2]),
            "lip_asym_mu": float(feats_mean[3]),
            "lip_asym_sigma": float(feats_std[3]),
            "jaw_open_mu": float(feats_mean[4]),
            "jaw_open_sigma": float(feats_std[4]),
        }
        return cls(
            id=kwargs.get("id"),
            subject_id=kwargs.get("subject_id"),
            word=kwargs["word"],
            language=kwargs.get("language", "en"),
            version=kwargs.get("version", 1),
            parent_id=kwargs.get("parent_id"),
            n_samples=len(samples),
            mean_curve=mean_curve,
            cov_diag=cov_diag,
            regional_stats=regional_stats,
            samples=kwargs.get("sample_ids", []),
        )
```

### `matcher.py`
```python
"""
MG-STUB: PhraseMatcher — сравнение probe PhraseInstance с template.
"""
import numpy as np
from .dtw import dtw_distance, dtw_slope
from .mahalanobis import mahalanobis, chi2_threshold

def match(probe_landmarks: np.ndarray, probe_features: np.ndarray,
          template: PhraseTemplate) -> dict:
    """Returns dict with similarity score + diagnostics."""
    # 1. DTW
    dtw_dist, dtw_path = dtw_distance(probe_landmarks, template.mean_curve, window=5)
    slope = dtw_slope(dtw_path)

    # 2. Mahalanobis on regional features
    feat_mean = probe_features.mean(axis=0)  # (n_features,)
    # build vector from template regional_stats
    tmpl_vec = np.array([
        template.regional_stats["mouth_open_mu"],
        template.regional_stats["mouth_ratio_mu"],
        template.regional_stats["lip_asym_mu"],
        template.regional_stats["jaw_open_mu"],
    ])
    tmpl_sigma = np.array([
        template.regional_stats["mouth_open_sigma"] + 1e-3,
        template.regional_stats["mouth_ratio_sigma"] + 1e-3,
        template.regional_stats["lip_asym_sigma"] + 1e-3,
        template.regional_stats["jaw_open_sigma"] + 1e-3,
    ])
    maha = mahalanobis(feat_mean, tmpl_vec, tmpl_sigma)
    threshold = chi2_threshold(4, 0.05)

    # 3. Combine into similarity
    # dtw_dist is roughly in [0, 0.5] for typical values
    # maha is in [0, ~10] for typical values
    dtw_sim = np.exp(-dtw_dist * 5.0)
    maha_sim = 1.0 if maha < threshold else float(np.exp(-(maha - threshold)))
    similarity = 0.6 * dtw_sim + 0.4 * maha_sim

    return {
        "dtw_distance": float(dtw_dist),
        "dtw_slope": float(slope),
        "mahalanobis": float(maha),
        "mahalanobis_threshold": float(threshold),
        "similarity": float(similarity),
        "evidence": _build_evidence(dtw_dist, slope, maha, threshold, template),
    }


def _build_evidence(dtw_dist, slope, maha, threshold, template) -> list[dict]:
    evidence = []
    if dtw_dist > 0.3:
        evidence.append({
            "code": "BASELINE_DISTANCE_HIGH",
            "contribution": min(1.0, dtw_dist),
            "message": f"DTW distance {dtw_dist:.3f} higher than typical range",
        })
    if slope > 1.3 or slope < 0.7:
        evidence.append({
            "code": "MOTION_TIMING_SHIFT",
            "contribution": abs(slope - 1.0),
            "message": f"Motion timing ratio {slope:.2f} (expected ≈1.0)",
        })
    if maha > threshold:
        evidence.append({
            "code": "LIP_ASYMMETRY" if template.regional_stats.get("lip_asym_sigma", 0) < 0.05 else "JAW_RANGE_LOW",
            "contribution": min(1.0, maha / (threshold * 2)),
            "message": f"Regional motion (Mahalanobis {maha:.2f} > {threshold:.2f})",
        })
    return evidence
```

### `aggregator.py`
```python
"""
MG-STUB: PhraseAggregator — атомарное обновление template при новом verified sample.
"""
import asyncio
from .template import PhraseTemplate

class PhraseAggregator:
    def __init__(self, db_session_factory, s3):
        self.session_factory = db_session_factory
        self.s3 = s3

    async def on_review_confirmed_genuine(self, review, decision):
        """Создать/обновить PhraseTemplate для каждого слова в decision.phrase_instances."""
        for inst in decision.phrase_instances:
            async with self.session_factory() as session:
                # latest template
                latest = await session.execute(
                    select(PhraseTemplate)
                    .where(PhraseTemplate.word == inst.word, ...)
                    .order_by(PhraseTemplate.version.desc())
                )
                latest = latest.scalar_one_or_none()

                if latest is None or latest.n_samples >= MAX_N:
                    new_version = 1 if latest is None else latest.version + 1
                    template = PhraseTemplate.build(...)
                else:
                    # rebuild with new sample
                    samples = await self._load_samples(session, latest)
                    samples.append(load_new_sample(inst))
                    template = PhraseTemplate.build(samples, version=latest.version + 1, parent_id=latest.id)

                # write to S3 (mean_curve.npz, cov_diag.npz)
                await self.s3.put_object(template_key, template.mean_curve.tobytes())

                session.add(template)
                await session.commit()
                # emit phrase.template.built.v1
```

## Thresholds
- `MAX_N` = 50 samples per template (далее — ребилд с top-50 by recency).
- `MIN_SAMPLES_FOR_BASELINE` = 3 — иначе baseline не публикуется.
- `MATURITY_THRESHOLD` = 10 — начиная с этого, decision может быть выдан без пометки INSUFFICIENT_BASELINE.
