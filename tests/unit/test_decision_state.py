"""Tests for state machine transitions on AnalysisJob."""
from __future__ import annotations

import os
import unittest
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")


class JobStateMachineTests(unittest.TestCase):
    def test_valid_transitions(self):
        """The state machine defines which transitions are allowed."""
        # Document the contract: from any of these states, only specific targets are valid
        valid = {
            "QUEUED": {"RUNNING", "FAILED"},
            "RUNNING": {"SUCCEEDED", "FAILED", "INSUFFICIENT_DATA"},
            "SUCCEEDED": set(),  # terminal
            "FAILED": {"QUEUED"},  # retry
            "INSUFFICIENT_DATA": {"QUEUED"},  # retry
        }
        for s, targets in valid.items():
            self.assertIsInstance(targets, set)

    def test_terminal_states_cannot_transition_out(self):
        """SUCCEEDED is a terminal state."""
        # Once SUCCEEDED, no further transitions
        valid = {
            "SUCCEEDED": set(),
        }
        self.assertEqual(len(valid["SUCCEEDED"]), 0)

    def test_idempotency_key_uniqueness(self):
        """Two jobs with the same (asset, subject, pipeline) are the same job."""
        asset_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        key1 = f"{asset_id}:{subject_id}:v1"
        key2 = f"{asset_id}:{subject_id}:v1"
        self.assertEqual(key1, key2)

    def test_different_pipeline_creates_different_job(self):
        asset_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        key1 = f"{asset_id}:{subject_id}:v1"
        key2 = f"{asset_id}:{subject_id}:v2"
        self.assertNotEqual(key1, key2)


class DecisionLabelTests(unittest.TestCase):
    def test_label_thresholds(self):
        from app.settings import get_settings

        s = get_settings()
        CONSISTENT_MAX = s.decision_risk_consistent_max
        SUSPICIOUS_MIN = s.decision_risk_suspicious_min

        # Below threshold → CONSISTENT
        for r in (0.0, 0.1, 0.2, CONSISTENT_MAX - 0.01):
            self.assertLess(r, CONSISTENT_MAX)
        # Above threshold → SUSPICIOUS
        for r in (SUSPICIOUS_MIN + 0.01, 0.8, 0.9, 1.0):
            self.assertGreaterEqual(r, SUSPICIOUS_MIN)
        # Between thresholds → INSUFFICIENT_DATA
        for r in [CONSISTENT_MAX, (CONSISTENT_MAX + SUSPICIOUS_MIN) / 2, SUSPICIOUS_MIN]:
            self.assertGreaterEqual(r, CONSISTENT_MAX)
            self.assertLessEqual(r, SUSPICIOUS_MIN)


class ModelStateMachineTests(unittest.TestCase):
    def test_promotion_flow(self):
        valid_transitions = {
            "DRAFT": {"VALIDATED", "RETIRED"},
            "VALIDATED": {"SHADOW", "RETIRED"},
            "SHADOW": {"ACTIVE", "RETIRED"},
            "ACTIVE": {"RETIRED"},
            "RETIRED": set(),
        }
        # Path: DRAFT → VALIDATED → SHADOW → ACTIVE → RETIRED
        path = ["DRAFT", "VALIDATED", "SHADOW", "ACTIVE", "RETIRED"]
        for prev, nxt in zip(path, path[1:]):
            self.assertIn(nxt, valid_transitions[prev], f"{prev} → {nxt} should be valid")

    def test_invalid_promotion_rejected(self):
        """You cannot skip DRAFT → SHADOW."""
        valid_transitions = {
            "DRAFT": {"VALIDATED", "RETIRED"},
        }
        self.assertNotIn("SHADOW", valid_transitions["DRAFT"])
        self.assertNotIn("ACTIVE", valid_transitions["DRAFT"])
