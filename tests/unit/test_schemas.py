"""Tests for Pydantic schemas and camelCase wire format."""
from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from app.schemas import (
    CreateJobRequest,
    DecisionOut,
    EvidenceItem,
    LoginRequest,
    PhraseInstance,
    ReviewVerdict,
)


class SchemaTests(unittest.TestCase):
    def test_create_job_request_accepts_camelcase(self):
        asset_uuid = uuid.uuid4()
        subject_uuid = uuid.uuid4()
        payload = {
            "assetId": str(asset_uuid),
            "claimedPersonId": str(subject_uuid),
        }
        req = CreateJobRequest.model_validate(payload)
        self.assertEqual(req.asset_id, asset_uuid)
        self.assertEqual(req.claimed_person_id, subject_uuid)

    def test_create_job_request_serializes_to_camelcase(self):
        asset_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        req = CreateJobRequest(asset_id=asset_id, claimed_person_id=subject_id)
        dumped = req.model_dump(by_alias=True)
        self.assertIn("assetId", dumped)
        self.assertIn("claimedPersonId", dumped)

    def test_login_request_validation(self):
        req = LoginRequest(email="user@example.com", password="secret")
        self.assertEqual(req.email, "user@example.com")

    def test_login_request_invalid_email_rejected(self):
        with self.assertRaises(Exception):
            LoginRequest(email="not-an-email", password="x")

    def test_evidence_contribution_range(self):
        # Valid range: [-1, 1]
        ev = EvidenceItem(code="X", contribution=0.5, message="msg")
        self.assertEqual(ev.contribution, 0.5)
        with self.assertRaises(Exception):
            EvidenceItem(code="X", contribution=2.0, message="msg")
        with self.assertRaises(Exception):
            EvidenceItem(code="X", contribution=-2.0, message="msg")

    def test_decision_label_enum(self):
        d = DecisionOut(
            id=uuid.uuid4(),
            job_id=uuid.uuid4(),
            label="SUSPICIOUS",
            risk_score=0.8,
            quality_score=0.9,
            model_version="v1",
            model_checksum="",
            evidence=[],
            phrase_instances=[],
            created_at=datetime.now(timezone.utc),
        )
        self.assertEqual(d.label, "SUSPICIOUS")

    def test_review_verdict_values(self):
        # Literal types are string literals, not enum members
        from typing import get_args

        values = get_args(ReviewVerdict)
        self.assertIn("CONFIRMED_GENUINE", values)
        self.assertIn("CONFIRMED_SUSPICIOUS", values)
        self.assertIn("UNDECIDABLE", values)

    def test_phrase_instance_required_fields(self):
        pi = PhraseInstance(
            word="hello",
            language="en",
            start_ms=0,
            end_ms=500,
            similarity=0.85,
            confidence=0.9,
            has_mature_baseline=True,
            evidence=[],
        )
        self.assertEqual(pi.word, "hello")
        self.assertTrue(pi.has_mature_baseline)
