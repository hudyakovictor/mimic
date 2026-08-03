"""Versioned statistical scorer for local, signed baseline artifacts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

from ..domain import NormalizedSequence


@dataclass(frozen=True, slots=True)
class StatisticalScore:
    risk_score: float
    evidence: tuple[dict[str, object], ...]


class VersionedMotionScorer:
    """Compare a normalized sequence with a versioned ``.npz`` baseline.

    The artifact must contain ``mean_curve`` and may contain ``std_curve``.
    A configured SHA-256 pins the artifact used for regulated inference.
    """

    def __init__(self, model_version: str, *, expected_sha256: str | None = None) -> None:
        if not model_version.strip():
            raise ValueError("model_version is required")
        self.model_version = model_version
        self.expected_sha256 = expected_sha256

    def score(self, probe: NormalizedSequence, baseline_uri: str) -> StatisticalScore:
        if not baseline_uri or "://" in baseline_uri:
            raise ValueError("baseline_uri must be a local materialized artifact path")
        with open(baseline_uri, "rb") as stream:
            payload = stream.read()
        digest = hashlib.sha256(payload).hexdigest()
        if self.expected_sha256 and digest != self.expected_sha256:
            raise ValueError("Baseline checksum mismatch")
        with np.load(baseline_uri, allow_pickle=False) as artifact:
            mean = np.asarray(artifact["mean_curve"], dtype=np.float32)
            std = np.asarray(artifact.get("std_curve", np.ones_like(mean)), dtype=np.float32)
        values = np.asarray([frame.vector for frame in probe.frames], dtype=np.float32)
        if values.ndim != 2 or values.shape[0] < 2 or mean.ndim != 2:
            raise ValueError("Probe and baseline must be non-empty 2D motion curves")
        if values.shape[1] != mean.shape[1]:
            raise ValueError("Probe feature schema does not match the baseline")
        old_x = np.linspace(0.0, 1.0, values.shape[0])
        new_x = np.linspace(0.0, 1.0, mean.shape[0])
        aligned = np.column_stack([np.interp(new_x, old_x, values[:, i]) for i in range(values.shape[1])])
        z_rmse = float(np.sqrt(np.mean(((aligned - mean) / np.maximum(np.abs(std), 0.03)) ** 2)))
        risk = float(np.clip(1.0 - np.exp(-z_rmse / 3.0), 0.0, 1.0))
        evidence = (
            {
                "code": "STANDARDIZED_MOTION_DISTANCE",
                "value": z_rmse,
                "baseline_sha256": digest,
                "feature_schema": probe.feature_schema_version,
            },
        )
        return StatisticalScore(risk, evidence)
