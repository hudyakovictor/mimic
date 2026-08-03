"""Baseline matching: DTW + Mahalanobis."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import chi2


@dataclass
class MatchResult:
    similarity: float
    dtw_distance: float
    dtw_slope: float
    mahalanobis: float
    evidence: list[dict]


def dtw_distance(a: np.ndarray, b: np.ndarray, window: int = 5) -> tuple[float, list[tuple[int, int]]]:
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return float("inf"), []
    cost = np.full((n + 1, m + 1), np.inf)
    cost[0, 0] = 0.0
    for i in range(1, n + 1):
        j_start = max(1, i - window)
        j_end = min(m, i + window)
        for j in range(j_start, j_end + 1):
            d = float(np.linalg.norm(a[i - 1] - b[j - 1]))
            cost[i, j] = d + min(cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1])
    # backtrack
    path: list[tuple[int, int]] = []
    i, j = n, m
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        candidates = [(i - 1, j - 1), (i - 1, j), (i, j - 1)]
        costs = [cost[i - 1, j - 1], cost[i - 1, j], cost[i, j - 1]]
        k = int(np.argmin(costs))
        di, dj = candidates[k]
        i, j = di, dj
    path.reverse()
    return float(cost[n, m] / max(n, m)), path


def dtw_slope(path: list[tuple[int, int]]) -> float:
    if len(path) < 2:
        return 1.0
    xs = np.array([p[0] for p in path], dtype=float)
    ys = np.array([p[1] for p in path], dtype=float)
    if xs.std() < 1e-6:
        return 1.0
    slope = float(np.polyfit(xs, ys, 1)[0])
    return slope


def mahalanobis(x: np.ndarray, mean: np.ndarray, cov_diag: np.ndarray) -> float:
    d = x - mean
    return float(np.sqrt(np.sum(d * d / np.maximum(cov_diag, 1e-8))))


def chi2_threshold(dims: int, alpha: float = 0.05) -> float:
    """Threshold for the (non-squared) Mahalanobis distance."""
    return float(np.sqrt(chi2.ppf(1 - alpha, df=dims)))


def features_from_landmarks(arr: np.ndarray) -> np.ndarray:
    """Compute 8 regional features from a 30x33 normalized landmarks array."""
    if arr.ndim != 2 or arr.shape[0] == 0:
        return np.zeros(8, dtype=np.float32)
    v = arr
    mouth_open = np.abs(v[:, 15] - v[:, 9])
    mouth_width = np.abs(v[:, 6] - v[:, 0])
    mouth_ratio = mouth_open / (mouth_width + 1e-6)
    lip_asym = v[:, 1] - v[:, 7]
    jaw_open = np.abs(v[:, 25] - v[:, 28])
    cheek_raise = (v[:, 31] + (v[:, 36] if v.shape[1] > 36 else v[:, 31])) / 2
    d_mouth_open = np.gradient(mouth_open) if arr.shape[0] > 1 else np.zeros_like(mouth_open)
    dd_mouth_open = np.gradient(d_mouth_open) if arr.shape[0] > 1 else np.zeros_like(mouth_open)
    return np.array(
        [
            mouth_open.mean(),
            mouth_width.mean(),
            mouth_ratio.mean(),
            lip_asym.mean(),
            jaw_open.mean(),
            cheek_raise.mean(),
            d_mouth_open.mean(),
            dd_mouth_open.mean(),
        ],
        dtype=np.float32,
    )


def match(probe_lm: np.ndarray, template_mean: np.ndarray, template_regional: dict) -> MatchResult:
    """Match a probe phrase (30x33) against a template (mean_curve + regional_stats)."""
    d, path = dtw_distance(probe_lm, template_mean, window=5)
    slope = dtw_slope(path)
    # Regional Mahalanobis
    probe_feats = features_from_landmarks(probe_lm)
    tmpl_vec = np.array(
        [
            template_regional.get("mouth_open_mu", 0),
            template_regional.get("mouth_ratio_mu", 0),
            template_regional.get("lip_asym_mu", 0),
            template_regional.get("jaw_open_mu", 0),
        ],
        dtype=np.float32,
    )
    tmpl_sigma = np.array(
        [
            template_regional.get("mouth_open_sigma", 0.1) + 1e-3,
            template_regional.get("mouth_ratio_sigma", 0.1) + 1e-3,
            template_regional.get("lip_asym_sigma", 0.1) + 1e-3,
            template_regional.get("jaw_open_sigma", 0.1) + 1e-3,
        ],
        dtype=np.float32,
    )
    selected_features = probe_feats[[0, 2, 3, 4]]
    maha = mahalanobis(selected_features, tmpl_vec, tmpl_sigma**2)
    thr = chi2_threshold(4, 0.05)
    dtw_sim = float(np.exp(-d * 5.0))
    maha_sim = 1.0 if maha < thr else float(np.exp(-(maha - thr)))
    similarity = max(0.0, min(1.0, 0.7 * dtw_sim + 0.3 * maha_sim))
    evidence: list[dict] = []
    if d > 0.3:
        evidence.append(
            {
                "code": "BASELINE_DISTANCE_HIGH",
                "contribution": min(1.0, d),
                "message": f"DTW distance {d:.3f} higher than typical range",
            }
        )
    if slope > 1.3 or slope < 0.7:
        evidence.append(
            {
                "code": "MOTION_TIMING_SHIFT",
                "contribution": float(abs(slope - 1.0)),
                "message": f"Motion timing ratio {slope:.2f} (expected ≈1.0)",
            }
        )
    if maha > thr:
        # Pick a code by which regional stat is most anomalous
        deltas = np.abs(selected_features - tmpl_vec) / tmpl_sigma
        idx = int(np.argmax(deltas))
        code = (
            "MOUTH_RANGE_HIGH",
            "MOUTH_RATIO_SHIFT",
            "LIP_ASYMMETRY",
            "JAW_RANGE_LOW",
        )[idx]
        evidence.append(
            {
                "code": code,
                "contribution": float(min(1.0, maha / (thr * 2))),
                "message": f"Regional motion anomaly (Mahalanobis {maha:.2f} > {thr:.2f})",
            }
        )
    return MatchResult(
        similarity=similarity,
        dtw_distance=d,
        dtw_slope=slope,
        mahalanobis=maha,
        evidence=evidence,
    )
