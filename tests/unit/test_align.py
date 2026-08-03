"""Unit tests for word-to-landmark alignment."""
from __future__ import annotations

import unittest

import numpy as np

from worker.phoneme.align import align_words_to_landmarks, _resample


class ResampleTests(unittest.TestCase):
    def test_resample_correct_length(self):
        arr = np.random.RandomState(0).randn(15, 33)
        out = _resample(arr, 30)
        self.assertEqual(out.shape, (30, 33))

    def test_resample_same_length_returns_input(self):
        arr = np.random.RandomState(1).randn(30, 33)
        out = _resample(arr, 30)
        np.testing.assert_array_equal(out, arr)

    def test_resample_empty_input(self):
        arr = np.zeros((0, 33))
        out = _resample(arr, 30)
        self.assertEqual(out.shape, (30, 33))
        np.testing.assert_array_equal(out, np.zeros((30, 33)))

    def test_resample_monotone_preserved(self):
        """A linearly increasing curve should remain increasing after resample."""
        arr = np.tile(np.linspace(0, 1, 50).reshape(-1, 1), (1, 5))
        out = _resample(arr, 30)
        diffs = np.diff(out[:, 0])
        self.assertTrue((diffs >= 0).all())


class AlignTests(unittest.TestCase):
    def _fake_landmarks(self, n_frames: int = 300) -> np.ndarray:
        return np.random.RandomState(0).randn(n_frames, 33).astype(np.float32)

    def test_align_skips_too_short(self):
        words = [{"start_ms": 0, "end_ms": 50, "text": "hi", "confidence": 0.9}]  # 50ms
        lm = self._fake_landmarks(300)
        audio = np.random.randn(16000).astype(np.float32)
        out = align_words_to_landmarks(words, lm, audio)
        self.assertEqual(out, [])

    def test_align_skips_too_long(self):
        words = [{"start_ms": 0, "end_ms": 5000, "text": "long", "confidence": 0.9}]  # 5s
        lm = self._fake_landmarks(300)
        audio = np.random.randn(16000 * 6).astype(np.float32)
        out = align_words_to_landmarks(words, lm, audio)
        self.assertEqual(out, [])

    def test_align_normalizes_word_text(self):
        # Need enough audio so resample works
        words = [{"start_ms": 0, "end_ms": 500, "text": "Hello!", "confidence": 0.9}]
        lm = self._fake_landmarks(300)
        # 500ms at 30fps = 15 frames
        audio = np.zeros(8000, dtype=np.float32)
        out = align_words_to_landmarks(words, lm, audio)
        self.assertGreaterEqual(len(out), 1)
        if out:
            # The function strips punctuation and lowercases
            self.assertEqual(out[0].word, "hello")

    def test_align_resamples_landmarks_to_30(self):
        words = [{"start_ms": 0, "end_ms": 500, "text": "test", "confidence": 0.9}]
        lm = self._fake_landmarks(300)
        audio = np.zeros(8000, dtype=np.float32)
        out = align_words_to_landmarks(words, lm, audio)
        self.assertGreaterEqual(len(out), 1)
        if out:
            self.assertEqual(out[0].landmarks_slice.shape, (30, 33))

    def test_align_builds_bounded_word_combinations(self):
        words = [
            {"start_ms": 0, "end_ms": 400, "text": "добрый", "confidence": 0.95},
            {"start_ms": 450, "end_ms": 900, "text": "день", "confidence": 0.9},
            {"start_ms": 950, "end_ms": 1350, "text": "москва", "confidence": 0.85},
        ]
        lm = self._fake_landmarks(300)
        audio = np.zeros(16000 * 2, dtype=np.float32)
        out = align_words_to_landmarks(words, lm, audio, language="ru")
        labels = {instance.word for instance in out}
        self.assertIn("добрый день", labels)
        self.assertIn("добрый день москва", labels)

    def test_align_audio_slice_extracted(self):
        words = [{"start_ms": 1000, "end_ms": 1500, "text": "test", "confidence": 0.9}]
        lm = self._fake_landmarks(900)  # 30 sec @ 30fps to cover 1.5s easily
        audio = np.zeros(16000 * 3, dtype=np.float32)  # 3 sec
        out = align_words_to_landmarks(words, lm, audio)
        self.assertGreaterEqual(len(out), 1)
        if out:
            # 500ms @ 16kHz = 8000 samples (allow ±1 for rounding)
            self.assertAlmostEqual(out[0].audio_slice.shape[0], 8000, delta=10)
