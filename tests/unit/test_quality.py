"""Unit tests for the landmark quality gate."""
from __future__ import annotations

import unittest

from packages.landmark_engine.domain import (
    HeadPose,
    LandmarkFrame,
    LandmarkSequence,
    Point3D,
    QualityFailure,
)
from packages.landmark_engine.quality import assess_quality


def make_frame(t_ms: int, *, confidence: float = 0.9, yaw: float = 0.0) -> LandmarkFrame:
    """Make a synthetic frame with required semantic points."""
    points = {
        33: Point3D(0.3, 0.5, 0.0),  # left eye outer
        263: Point3D(0.7, 0.5, 0.0),  # right eye outer
        1: Point3D(0.5, 0.5, 0.0),  # nose
        # motion points
        61: Point3D(0.4, 0.6, 0.0),
        291: Point3D(0.6, 0.6, 0.0),
        13: Point3D(0.5, 0.55, 0.0),
        14: Point3D(0.5, 0.65, 0.0),
        78: Point3D(0.45, 0.6, 0.0),
        308: Point3D(0.55, 0.6, 0.0),
        152: Point3D(0.5, 0.8, 0.0),
        234: Point3D(0.25, 0.5, 0.0),
        454: Point3D(0.75, 0.5, 0.0),
        50: Point3D(0.4, 0.45, 0.0),
        280: Point3D(0.6, 0.45, 0.0),
    }
    return LandmarkFrame(
        timestamp_ms=t_ms, points=points, confidence=confidence, head_pose=HeadPose(yaw=yaw, pitch=0, roll=0)
    )


class QualityGateTests(unittest.TestCase):
    def test_short_sequence_rejected(self):
        seq = LandmarkSequence("t", "v1", [make_frame(i * 33) for i in range(5)], 30)
        qa = assess_quality(seq)
        self.assertFalse(qa.accepted)
        self.assertIn(QualityFailure.TOO_FEW_FRAMES, qa.failures)

    def test_low_confidence_rejected(self):
        seq = LandmarkSequence(
            "t", "v1", [make_frame(i * 33, confidence=0.5) for i in range(20)], 30
        )
        qa = assess_quality(seq)
        self.assertFalse(qa.accepted)
        self.assertIn(QualityFailure.LOW_TRACKING_CONFIDENCE, qa.failures)

    def test_excessive_gaps_rejected(self):
        frames = [make_frame(i * 33) for i in range(15)]
        # introduce a big gap
        frames.append(make_frame(15 * 33 + 1000))  # 1000ms gap
        frames.extend(make_frame(15 * 33 + 1000 + i * 33) for i in range(1, 10))
        seq = LandmarkSequence("t", "v1", frames, 30)
        qa = assess_quality(seq)
        self.assertFalse(qa.accepted)
        self.assertIn(QualityFailure.EXCESSIVE_GAPS, qa.failures)

    def test_excessive_yaw_rejected(self):
        frames = [make_frame(i * 33, yaw=70) for i in range(20)]
        seq = LandmarkSequence("t", "v1", frames, 30)
        qa = assess_quality(seq)
        self.assertFalse(qa.accepted)
        self.assertIn(QualityFailure.EXCESSIVE_HEAD_POSE, qa.failures)

    def test_good_sequence_accepted(self):
        frames = [make_frame(i * 33) for i in range(30)]
        seq = LandmarkSequence("t", "v1", frames, 30)
        qa = assess_quality(seq)
        self.assertTrue(qa.accepted)
        self.assertEqual(qa.failures, ())
        self.assertGreater(qa.score, 0.7)

    def test_score_monotonic_in_confidence(self):
        high = LandmarkSequence("t", "v1", [make_frame(i * 33, confidence=0.95) for i in range(20)], 30)
        low = LandmarkSequence("t", "v1", [make_frame(i * 33, confidence=0.75) for i in range(20)], 30)
        high_qa = assess_quality(high)
        low_qa = assess_quality(low)
        self.assertGreater(high_qa.score, low_qa.score)

    def test_metrics_dict(self):
        seq = LandmarkSequence("t", "v1", [make_frame(i * 33) for i in range(20)], 30)
        qa = assess_quality(seq)
        self.assertIn("frame_count", qa.metrics)
        self.assertEqual(qa.metrics["frame_count"], 20.0)
        self.assertIn("mean_confidence", qa.metrics)
        self.assertIn("max_gap_ms", qa.metrics)
        self.assertIn("max_abs_yaw", qa.metrics)
