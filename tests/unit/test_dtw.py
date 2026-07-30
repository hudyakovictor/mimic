"""Unit tests for DTW + Mahalanobis matcher."""
from __future__ import annotations

import unittest

import numpy as np

from worker.baseline.match import (
    dtw_distance,
    dtw_slope,
    features_from_landmarks,
    mahalanobis,
    match,
)


class DTWTests(unittest.TestCase):
    def test_identical_sequences_zero_distance(self):
        seq = np.random.RandomState(0).randn(30, 33).astype(np.float32)
        d, path = dtw_distance(seq, seq, window=5)
        self.assertLess(d, 1e-5)
        self.assertEqual(len(path), 30)

    def test_dtw_symmetry_approximately(self):
        """DTW distance is symmetric."""
        a = np.random.RandomState(1).randn(30, 33).astype(np.float32)
        b = np.random.RandomState(2).randn(30, 33).astype(np.float32)
        d_ab, _ = dtw_distance(a, b, window=5)
        d_ba, _ = dtw_distance(b, a, window=5)
        self.assertAlmostEqual(d_ab, d_ba, places=4)

    def test_dtw_triangle_inequality(self):
        """d(a, c) ≤ d(a, b) + d(b, c)."""
        rng = np.random.RandomState(3)
        a = rng.randn(30, 33).astype(np.float32)
        b = rng.randn(30, 33).astype(np.float32)
        c = rng.randn(30, 33).astype(np.float32)
        d_ac, _ = dtw_distance(a, c, window=5)
        d_ab, _ = dtw_distance(a, b, window=5)
        d_bc, _ = dtw_distance(b, c, window=5)
        # Soft check (DTW is not strictly metric but approximately is)
        self.assertLessEqual(d_ac, d_ab + d_bc + 0.05)

    def test_slope_approximately_one_for_identical(self):
        seq = np.random.RandomState(4).randn(30, 33).astype(np.float32)
        _, path = dtw_distance(seq, seq, window=5)
        s = dtw_slope(path)
        self.assertAlmostEqual(s, 1.0, places=2)

    def test_window_constraint(self):
        """With a window, DTW path stays within the band."""
        a = np.random.RandomState(5).randn(30, 33).astype(np.float32)
        b = np.random.RandomState(6).randn(30, 33).astype(np.float32)
        _, path = dtw_distance(a, b, window=2)
        for i, j in path:
            self.assertLessEqual(abs(i - j), 2)


class MahalanobisTests(unittest.TestCase):
    def test_zero_distance_for_self(self):
        x = np.array([1.0, 2.0, 3.0])
        self.assertAlmostEqual(mahalanobis(x, x, np.array([1.0, 1.0, 1.0])), 0.0, places=5)

    def test_scales_inversely_with_variance(self):
        x = np.array([1.0, 0.0, 0.0])
        mean = np.array([0.0, 0.0, 0.0])
        # small variance → large distance
        small_var = np.array([0.1, 1.0, 1.0])
        # large variance → small distance
        big_var = np.array([10.0, 1.0, 1.0])
        d_small = mahalanobis(x, mean, small_var)
        d_big = mahalanobis(x, mean, big_var)
        self.assertGreater(d_small, d_big)


class MatchTests(unittest.TestCase):
    def test_high_similarity_for_self(self):
        rng = np.random.RandomState(7)
        # Make a curve that roughly matches the assumed regional stats
        # by keeping motion values near the means
        template_curve = np.zeros((30, 33), dtype=np.float32)
        template_curve[:, 15] = 0.5  # mouth_open
        template_curve[:, 9] = -0.5
        template_curve[:, 0] = -0.2
        template_curve[:, 6] = 0.2
        template_curve[:, 1] = 0.1
        template_curve[:, 7] = 0.1
        template_curve[:, 25] = 0.4
        template_curve[:, 28] = -0.4
        regional = {
            "mouth_open_mu": 0.5,
            "mouth_open_sigma": 0.5,
            "mouth_ratio_mu": 0.3,
            "mouth_ratio_sigma": 0.5,
            "lip_asym_mu": 0.0,
            "lip_asym_sigma": 0.5,
            "jaw_open_mu": 0.4,
            "jaw_open_sigma": 0.5,
        }
        result = match(template_curve, template_curve, regional)
        # Identical input should produce high similarity
        self.assertGreater(result.similarity, 0.7)

    def test_low_similarity_for_different(self):
        rng = np.random.RandomState(8)
        template = rng.randn(30, 33).astype(np.float32) * 0.1
        probe = rng.randn(30, 33).astype(np.float32) * 2.0  # very different
        regional = {
            "mouth_open_mu": 0.5,
            "mouth_open_sigma": 0.01,
            "mouth_ratio_mu": 0.3,
            "mouth_ratio_sigma": 0.01,
            "lip_asym_mu": 0.0,
            "lip_asym_sigma": 0.01,
            "jaw_open_mu": 0.4,
            "jaw_open_sigma": 0.01,
        }
        result = match(probe, template, regional)
        self.assertLess(result.similarity, 0.7)

    def test_features_extraction_shape(self):
        arr = np.random.RandomState(9).randn(30, 33).astype(np.float32)
        feats = features_from_landmarks(arr)
        self.assertEqual(feats.shape, (8,))
