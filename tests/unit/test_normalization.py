"""Unit tests for landmark normalization."""
from __future__ import annotations

import unittest

import numpy as np

from packages.landmark_engine.domain import (
    HeadPose,
    LandmarkFrame,
    LandmarkSequence,
    Point3D,
)
from packages.landmark_engine.normalization import normalize_sequence


def make_frame(t_ms: int, *, eye_d: float = 0.4, nose: tuple = (0.5, 0.5, 0.0)) -> LandmarkFrame:
    """Construct a frame with consistent geometry so normalization is well-defined."""
    nx, ny, nz = nose
    points = {
        33: Point3D(nx - eye_d / 2, ny, 0),  # left eye outer
        263: Point3D(nx + eye_d / 2, ny, 0),  # right eye outer
        1: Point3D(*nose),  # nose tip
        61: Point3D(0.4, 0.6, 0),
        291: Point3D(0.6, 0.6, 0),
        13: Point3D(0.5, 0.55, 0),
        14: Point3D(0.5, 0.65, 0),
        78: Point3D(0.45, 0.6, 0),
        308: Point3D(0.55, 0.6, 0),
        152: Point3D(0.5, 0.8, 0),
        234: Point3D(0.25, 0.5, 0),
        454: Point3D(0.75, 0.5, 0),
        50: Point3D(0.4, 0.45, 0),
        280: Point3D(0.6, 0.45, 0),
    }
    return LandmarkFrame(t_ms, points, 0.95, HeadPose(0, 0, 0))


class NormalizationTests(unittest.TestCase):
    def test_output_shape(self):
        seq = LandmarkSequence("t", "v1", [make_frame(i * 33) for i in range(10)], 30)
        norm = normalize_sequence(seq)
        self.assertEqual(norm.frames[0].vector.__len__(), 33)  # 11 motion points × 3 coords
        self.assertEqual(len(norm.frames), 10)

    def test_translation_invariance(self):
        """Nose-anchored coords should be invariant to global translation.

        We translate both the nose AND the motion points together (same offset)
        so that after normalization (subtracting nose, dividing by eye distance)
        the result is identical.
        """
        # Build two sequences with identical relative geometry
        def build(nose_x, nose_y):
            eye_d = 0.4
            nx, ny = nose_x, nose_y
            # Motion points relative to nose (same relative offsets)
            offsets = [
                (0.4 - 0.5, 0.6 - 0.5, 0),  # 61
                (0.6 - 0.5, 0.6 - 0.5, 0),  # 291
                (0.5 - 0.5, 0.55 - 0.5, 0),  # 13
                (0.5 - 0.5, 0.65 - 0.5, 0),  # 14
                (0.45 - 0.5, 0.6 - 0.5, 0),  # 78
                (0.55 - 0.5, 0.6 - 0.5, 0),  # 308
                (0.5 - 0.5, 0.8 - 0.5, 0),  # 152
                (0.25 - 0.5, 0.5 - 0.5, 0),  # 234
                (0.75 - 0.5, 0.5 - 0.5, 0),  # 454
                (0.4 - 0.5, 0.45 - 0.5, 0),  # 50
                (0.6 - 0.5, 0.45 - 0.5, 0),  # 280
            ]
            motion_indices = [61, 291, 13, 14, 78, 308, 152, 234, 454, 50, 280]
            frames = []
            for i in range(5):
                points = {
                    33: Point3D(nx - eye_d / 2, ny, 0),  # left eye outer
                    263: Point3D(nx + eye_d / 2, ny, 0),  # right eye outer
                    1: Point3D(nx, ny, 0),  # nose
                }
                for idx, (ox, oy, oz) in zip(motion_indices, offsets):
                    points[idx] = Point3D(nx + ox, ny + oy, oz)
                frames.append(LandmarkFrame(i * 33, points, 0.95, HeadPose(0, 0, 0)))
            return LandmarkSequence("t", "v1", frames, 30)

        seq1 = build(0.4, 0.4)
        seq2 = build(0.6, 0.6)
        n1 = np.array([f.vector for f in normalize_sequence(seq1).frames])
        n2 = np.array([f.vector for f in normalize_sequence(seq2).frames])
        np.testing.assert_allclose(n1, n2, atol=1e-6)

    def test_scale_invariance(self):
        """Doubled eye distance should yield same normalized coordinates."""
        def build(eye_d):
            offsets = [
                (0.4, 0.6, 0), (0.6, 0.6, 0), (0.5, 0.55, 0), (0.5, 0.65, 0),
                (0.45, 0.6, 0), (0.55, 0.6, 0), (0.5, 0.8, 0), (0.25, 0.5, 0),
                (0.75, 0.5, 0), (0.4, 0.45, 0), (0.6, 0.45, 0),
            ]
            motion_indices = [61, 291, 13, 14, 78, 308, 152, 234, 454, 50, 280]
            # Scale motion points by the same factor
            scale = eye_d / 0.4
            points = {
                33: Point3D(0.5 - eye_d / 2, 0.5, 0),
                263: Point3D(0.5 + eye_d / 2, 0.5, 0),
                1: Point3D(0.5, 0.5, 0),
            }
            for idx, (ox, oy, oz) in zip(motion_indices, offsets):
                points[idx] = Point3D(0.5 + ox * scale, 0.5 + oy * scale, oz)
            frame = LandmarkFrame(0, points, 0.95, HeadPose(0, 0, 0))
            return LandmarkSequence("t", "v1", [frame], 30)

        seq_small = build(0.2)
        seq_big = build(0.4)
        ns = np.array([f.vector for f in normalize_sequence(seq_small).frames])
        nb = np.array([f.vector for f in normalize_sequence(seq_big).frames])
        np.testing.assert_allclose(ns, nb, atol=1e-6)

    def test_degenerate_eye_distance_raises(self):
        """If eye distance is 0, normalization must fail loudly."""
        bad = LandmarkFrame(
            0,
            {
                33: Point3D(0.5, 0.5, 0),
                263: Point3D(0.5, 0.5, 0),  # same as left — degenerate
                1: Point3D(0.5, 0.5, 0),
                61: Point3D(0.4, 0.6, 0),
                291: Point3D(0.6, 0.6, 0),
                13: Point3D(0.5, 0.55, 0),
                14: Point3D(0.5, 0.65, 0),
                78: Point3D(0.45, 0.6, 0),
                308: Point3D(0.55, 0.6, 0),
                152: Point3D(0.5, 0.8, 0),
                234: Point3D(0.25, 0.5, 0),
                454: Point3D(0.75, 0.5, 0),
                50: Point3D(0.4, 0.45, 0),
                280: Point3D(0.6, 0.45, 0),
            },
            0.9,
            HeadPose(0, 0, 0),
        )
        seq = LandmarkSequence("t", "v1", [bad], 30)
        with self.assertRaises(ValueError):
            normalize_sequence(seq)

    def test_missing_required_points_raises(self):
        """Missing semantic anchors must fail loudly."""
        bad = LandmarkFrame(
            0,
            {1: Point3D(0.5, 0.5, 0)},  # only nose
            0.9,
            HeadPose(0, 0, 0),
        )
        seq = LandmarkSequence("t", "v1", [bad], 30)
        with self.assertRaises(ValueError):
            normalize_sequence(seq)
