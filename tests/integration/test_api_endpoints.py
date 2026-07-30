"""End-to-end API tests using FastAPI TestClient + in-memory SQLite.

These tests:
- Spin up the full FastAPI app
- Patch the database engine to use in-memory SQLite
- Patch the outbox publisher to skip Redis
- Create schema + seed default tenant/admin via dependency_overrides
- Exercise auth, subjects, models, audit, dashboard endpoints
"""
from __future__ import annotations

import os
import unittest
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-for-end-to-end")
os.environ.setdefault("DEFAULT_ADMIN_EMAIL", "admin@test.io")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "test-admin-pass-1234")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:1/0")  # unreachable — graceful

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import session as session_mod
from app.db.models import (
    AnalysisJob,
    Asset,
    Base,
    Decision,
    JobStage,
    LandmarkSequence,
    ModelVersion,
    PhraseSample,
    PhraseTemplate,
    Review,
    Subject,
    Tenant,
    Transcript,
    User,
)
from app.security.passwords import hash_password


TEST_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEST_ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _bootstrap():
    """Create in-memory engine, schema, default admin.

    We use a SINGLE shared connection so data persists between requests in TestClient.
    """
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sm = async_sessionmaker(bind=engine, expire_on_commit=False)
    # Patch global so the app uses our engine
    session_mod._engine = engine
    session_mod._sessionmaker = sm

    async def _go():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sm() as session:
            tenant = Tenant(id=TEST_TENANT_ID, slug="default", name="Default")
            session.add(tenant)
            user = User(
                id=TEST_ADMIN_ID,
                tenant_id=tenant.id,
                email="admin@test.io",
                password_hash=hash_password("test-admin-pass-1234"),
                display_name="Admin",
                roles=["system_admin", "operator", "reviewer", "model_admin", "auditor"],
                is_active=True,
            )
            session.add(user)
            session.add(
                ModelVersion(
                    id=uuid.uuid4(),
                    kind="LANDMARK_EXTRACTOR",
                    version="mediapipe-v1",
                    artifact_checksum="test-checksum",
                    state="ACTIVE",
                )
            )
            await session.commit()

    asyncio.run(_go())
    return engine, sm


class ApiE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient

        cls._engine, cls._sm = _bootstrap()
        from app.main import app
        from app.db import get_db

        # Force the app to use our session via dependency_overrides
        async def _override_get_db():
            async with cls._sm() as s:
                try:
                    yield s
                except Exception:
                    await s.rollback()
                    raise

        app.dependency_overrides[get_db] = _override_get_db
        cls.client = TestClient(app)

    def test_health_live(self):
        r = self.client.get("/health/live")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_metrics_endpoint(self):
        r = self.client.get("/metrics")
        self.assertEqual(r.status_code, 200)
        body = r.text
        self.assertIn("mimicguard", body)

    def test_info_endpoint(self):
        r = self.client.get("/info")
        self.assertEqual(r.status_code, 200)
        self.assertIn("service", r.json())

    def test_unauthorized_request_returns_401(self):
        r = self.client.get("/v1/analysis-jobs")
        self.assertEqual(r.status_code, 401)
        body = r.json()
        self.assertIn("code", body)
        self.assertIn("correlationId", body)

    def test_login_success(self):
        r = self.client.post(
            "/v1/auth/login",
            json={"email": "admin@test.io", "password": "test-admin-pass-1234"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        # Wire format is camelCase
        self.assertIn("accessToken", data)
        self.assertIn("refreshToken", data)
        self.assertIn("user", data)
        self.assertEqual(data["user"]["email"], "admin@test.io")
        return data["accessToken"]

    def test_login_wrong_password(self):
        r = self.client.post(
            "/v1/auth/login",
            json={"email": "admin@test.io", "password": "wrong"},
        )
        self.assertEqual(r.status_code, 401)

    def test_login_unknown_user(self):
        r = self.client.post(
            "/v1/auth/login",
            json={"email": "nobody@test.io", "password": "anything"},
        )
        self.assertEqual(r.status_code, 401)

    def test_full_flow_with_token(self):
        token = self.test_login_success()
        headers = {"Authorization": f"Bearer {token}"}

        # /me
        r = self.client.get("/v1/auth/me", headers=headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["email"], "admin@test.io")

        # Dashboard
        r = self.client.get("/v1/dashboard/metrics", headers=headers)
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertIn("pendingReviews", data)
        self.assertIn("qualityOkRatio", data)

        # Empty analyses list
        r = self.client.get("/v1/analysis-jobs", headers=headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsInstance(r.json(), list)

        # Empty words list
        r = self.client.get("/v1/words", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)

        # Models list (seeded)
        r = self.client.get("/v1/models", headers=headers)
        self.assertEqual(r.status_code, 200)
        models = r.json()
        self.assertGreater(len(models), 0)

        # Audit
        r = self.client.get("/v1/audit", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)

    def test_create_subject_flow(self):
        token = self.test_login_success()
        headers = {"Authorization": f"Bearer {token}"}

        # Create
        r = self.client.post(
            "/v1/subjects",
            json={
                "externalId": "ext-test-1",
                "displayName": "Test Subject",
                "consentState": "PENDING",
            },
            headers=headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        subject = r.json()
        self.assertEqual(subject["externalId"], "ext-test-1")
        self.assertEqual(subject["consentState"], "PENDING")
        subject_id = subject["id"]

        # Get
        r = self.client.get(f"/v1/subjects/{subject_id}", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["id"], subject_id)

        # Update (optimistic concurrency)
        r = self.client.patch(
            f"/v1/subjects/{subject_id}",
            json={"consentState": "GRANTED", "version": subject["version"]},
            headers=headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        updated = r.json()
        self.assertEqual(updated["consentState"], "GRANTED")
        self.assertEqual(updated["version"], subject["version"] + 1)

        # Stale version → 409
        r = self.client.patch(
            f"/v1/subjects/{subject_id}",
            json={"consentState": "REVOKED", "version": subject["version"]},
            headers=headers,
        )
        self.assertEqual(r.status_code, 409)
        body = r.json()
        self.assertEqual(body["code"], "version_conflict")

    def test_create_review_validation(self):
        token = self.test_login_success()
        headers = {"Authorization": f"Bearer {token}"}
        # No real decision exists — either 404 or 422 (validation); both are OK
        r = self.client.post(
            "/v1/reviews",
            json={
                "decisionId": str(uuid.uuid4()),
                "verdict": "CONFIRMED_GENUINE",
                "reason": "short",
            },
            headers=headers,
        )
        self.assertIn(r.status_code, (404, 422))

    def test_invalid_token_rejected(self):
        r = self.client.get(
            "/v1/analysis-jobs",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        self.assertEqual(r.status_code, 401)

    def test_openapi_schema_accessible(self):
        r = self.client.get("/openapi.json")
        self.assertEqual(r.status_code, 200)
        schema = r.json()
        self.assertIn("paths", schema)
        self.assertIn("components", schema)

    def test_validation_error_format(self):
        """Validation errors return 422 with field-level details."""
        r = self.client.post(
            "/v1/auth/login",
            json={"email": "not-an-email", "password": ""},
        )
        self.assertEqual(r.status_code, 422)
        body = r.json()
        self.assertEqual(body["code"], "validation_failed")
        self.assertIn("fieldErrors", body)
        self.assertIsInstance(body["fieldErrors"], list)
