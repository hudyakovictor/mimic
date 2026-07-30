"""Tests for storage key generation."""
from __future__ import annotations

import unittest
import uuid

from app.storage.keys import (
    asset_key,
    audio_clip_key,
    audio_key,
    clip_key,
    landmarks_key,
    model_key,
    phrase_landmarks_key,
    template_cov_key,
    template_curve_key,
    transcript_key,
)


class KeyGeneratorTests(unittest.TestCase):
    def test_asset_key_includes_tenant_and_id(self):
        t = uuid.uuid4()
        a = uuid.uuid4()
        k = asset_key(t, a, "mp4")
        self.assertIn(str(t), k)
        self.assertIn(str(a), k)
        self.assertTrue(k.endswith(".mp4"))

    def test_asset_key_strips_leading_dot(self):
        t = uuid.uuid4()
        a = uuid.uuid4()
        k = asset_key(t, a, ".mov")
        self.assertFalse(k.startswith(".."))
        self.assertTrue(k.endswith(".mov"))

    def test_landmarks_key_distinct_from_transcript_key(self):
        t = uuid.uuid4()
        j = uuid.uuid4()
        lk = landmarks_key(t, j)
        tk = transcript_key(t, j)
        self.assertNotEqual(lk, tk)
        self.assertIn("landmarks", lk)
        self.assertIn("transcript", tk)

    def test_template_keys_distinct(self):
        t = uuid.uuid4()
        tid = uuid.uuid4()
        c = template_curve_key(t, tid)
        d = template_cov_key(t, tid)
        self.assertIn("mean_curve", c)
        self.assertIn("cov_diag", d)

    def test_clip_key_uses_sample_id(self):
        t = uuid.uuid4()
        s = uuid.uuid4()
        k = clip_key(t, s)
        self.assertIn(str(t), k)
        self.assertIn(str(s), k)
        self.assertTrue(k.endswith("video.mp4"))

    def test_model_key_includes_version(self):
        m = uuid.uuid4()
        k = model_key(m, "1.0.0")
        self.assertIn(str(m), k)
        self.assertIn("1.0.0", k)

    def test_phrase_landmarks_key(self):
        t = uuid.uuid4()
        s = uuid.uuid4()
        k = phrase_landmarks_key(t, s)
        self.assertIn(str(s), k)
        self.assertIn("clips", k)

    def test_audio_keys(self):
        t = uuid.uuid4()
        j = uuid.uuid4()
        s = uuid.uuid4()
        self.assertIn(str(j), audio_key(t, j))
        self.assertIn(str(s), audio_clip_key(t, s))
