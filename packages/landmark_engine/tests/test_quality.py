import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from packages.landmark_engine.domain import LandmarkFrame, LandmarkSequence, HeadPose
from packages.landmark_engine.quality import assess_quality

class QualityTests(unittest.TestCase):
    def test_short_sequence_is_rejected(self):
        frames = [LandmarkFrame(i * 33, {}, 0.95, HeadPose(0, 0, 0)) for i in range(5)]
        result = assess_quality(LandmarkSequence("t", "v1", frames, 30))
        self.assertFalse(result.accepted)
        self.assertIn("TOO_FEW_FRAMES", result.failures)

if __name__ == '__main__': unittest.main()
