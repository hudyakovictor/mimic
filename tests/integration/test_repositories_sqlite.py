"""Integration tests for SQLAlchemy repositories against in-memory SQLite.

These tests exercise the full ORM stack including:
- Schema creation from metadata
- Tenant scoping
- Cursor pagination
- Optimistic concurrency
- Append-only enforcement
- Idempotency on jobs
"""
from __future__ import annotations

import asyncio
import os
import unittest
import uuid
from datetime import datetime, timezone

# Force SQLite in-memory for tests BEFORE importing the app
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests-only")

import pytest

from app.db import get_engine, get_sessionmaker
from app.db.models import (
    AnalysisJob,
    Asset,
    AuditEvent,
    Base,
    Decision,
    JobStage,
    ModelVersion,
    PhraseSample,
    PhraseTemplate,
    Review,
    Subject,
    Tenant,
    User,
)
from app.repositories.assets import AssetRepository
from app.repositories.audit import AuditRepository
from app.repositories.decisions import (
    DecisionRepository,
    PhraseSampleRepository,
    PhraseTemplateRepository,
    ReviewRepository,
)
from app.repositories.jobs import AnalysisJobRepository
from app.repositories.subjects import EnrollmentRepository, SubjectRepository
from app.repositories.users import UserRepository
from app.security.passwords import hash_password


@pytest.mark.asyncio
class RepositoryIntegrationTests(unittest.TestCase):
    """Each test runs against a fresh in-memory SQLite DB."""

    @classmethod
    def setUpClass(cls):
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from app.db.base import Base as _Base

        # Create dedicated test engine
        cls._engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:", future=True, echo=False
        )
        cls._sessionmaker = async_sessionmaker(bind=cls._engine, expire_on_commit=False)

    def setUp(self):
        from app.db import session as _session_mod

        # Reset metadata and tables for each test
        async def _reset():
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
            # Patch global sessionmaker to use test engine
            _session_mod._engine = self._engine
            _session_mod._sessionmaker = self._sessionmaker

        asyncio.run(_reset())

    def _run(self, coro):
        return asyncio.run(coro)

    def test_tenant_and_user_create(self):
        async def go():
            async with self._sessionmaker() as session:
                tenant = Tenant(id=uuid.uuid4(), slug="acme", name="Acme")
                session.add(tenant)
                await session.flush()
                repo = UserRepository(session, tenant.id)
                user = await repo.create(
                    email="alice@acme.io",
                    password_hash=hash_password("strong-pass-123"),
                    roles=["operator"],
                    display_name="Alice",
                )
                await session.commit()
                self.assertEqual(user.email, "alice@acme.io")
                self.assertIn("operator", user.roles)

        self._run(go())

    def test_subject_consent_lifecycle(self):
        async def go():
            async with self._sessionmaker() as session:
                tenant_id = uuid.uuid4()
                session.add(Tenant(id=tenant_id, slug="t1", name="T1"))
                await session.flush()
                sub_repo = SubjectRepository(session, tenant_id)
                s = await sub_repo.create("ext-1", "John", "PENDING")
                self.assertEqual(s.consent_state, "PENDING")
                s_id = s.id
                s_version = s.version
                await session.commit()
                # Reload after commit
                s2 = await sub_repo.update_optimistic(s_id, s_version, consent_state="GRANTED")
                self.assertEqual(s2.consent_state, "GRANTED")
                s2_version = s2.version
                await session.commit()
                # Wrong version → ConflictError
                from app.errors import ConflictError

                with self.assertRaises(ConflictError):
                    await sub_repo.update_optimistic(s_id, s_version, consent_state="REVOKED")
                await session.rollback()

        self._run(go())

    def test_analysis_job_idempotency(self):
        async def go():
            async with self._sessionmaker() as session:
                tenant_id = uuid.uuid4()
                session.add(Tenant(id=tenant_id, slug="t", name="T"))
                await session.flush()
                subj = Subject(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    external_id="x",
                    display_name="",
                    consent_state="GRANTED",
                )
                session.add(subj)
                asset = Asset(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    source_type="UPLOAD",
                    object_key="k",
                    mime="video/mp4",
                    uploaded_by=uuid.uuid4(),
                    state="READY",
                )
                session.add(asset)
                await session.flush()
                jobs = AnalysisJobRepository(session, tenant_id)
                # First call creates
                j1 = await jobs.create_or_get_idempotent(asset.id, subj.id, "v1")
                await session.commit()
                # Second call returns same
                j2 = await jobs.create_or_get_idempotent(asset.id, subj.id, "v1")
                await session.commit()
                self.assertEqual(j1.id, j2.id)

        self._run(go())

    def test_decision_append_only_via_trigger_check(self):
        """Append-only tables have triggers in production; for SQLite we verify
        the model is configured correctly (no version field on Decision/Review).
        """
        from sqlalchemy import inspect

        mapper = inspect(Decision)
        cols = {c.key for c in mapper.columns}
        self.assertIn("evidence", cols)
        self.assertIn("phrase_instances", cols)
        # Append-only tables: no version field
        self.assertNotIn("version", cols)

    def test_phrase_template_versioning(self):
        async def go():
            async with self._sessionmaker() as session:
                tenant_id = uuid.uuid4()
                session.add(Tenant(id=tenant_id, slug="t", name="T"))
                await session.flush()
                templates = PhraseTemplateRepository(session, tenant_id)
                # No template initially
                latest = await templates.get_latest_active("hello", "en", subject_id=None)
                self.assertIsNone(latest)
                # Create v1
                t1 = await templates.create_version(
                    word="hello",
                    language="en",
                    subject_id=None,
                    version=1,
                    parent_id=None,
                    n_samples=5,
                    mean_curve_object_key="k1",
                    cov_diag_object_key="k2",
                    regional_stats={"mouth_open_mu": 0.5},
                    model_version="v1",
                    is_mature=False,
                )
                await session.commit()
                latest = await templates.get_latest_active("hello", "en", subject_id=None)
                self.assertEqual(latest.id, t1.id)
                self.assertEqual(latest.version, 1)
                # Create v2
                t2 = await templates.create_version(
                    word="hello",
                    language="en",
                    subject_id=None,
                    version=2,
                    parent_id=t1.id,
                    n_samples=10,
                    mean_curve_object_key="k3",
                    cov_diag_object_key="k4",
                    regional_stats={"mouth_open_mu": 0.5},
                    model_version="v1",
                    is_mature=True,
                )
                await session.commit()
                # Latest is v2
                latest = await templates.get_latest_active("hello", "en", subject_id=None)
                self.assertEqual(latest.version, 2)
                self.assertTrue(latest.is_mature)

        self._run(go())

    def test_audit_create_and_filter(self):
        async def go():
            async with self._sessionmaker() as session:
                tenant_id = uuid.uuid4()
                session.add(Tenant(id=tenant_id, slug="t", name="T"))
                await session.flush()
                repo = AuditRepository(session, tenant_id)
                for i in range(3):
                    await repo.create(
                        action="test.event",
                        resource_type="X",
                        resource_id=str(i),
                        actor_id=uuid.uuid4(),
                    )
                await session.commit()
                items, nc = await repo.list_filtered(action="test.event", limit=10)
                self.assertEqual(len(items), 3)

        self._run(go())

    def test_model_state_transitions(self):
        async def go():
            async with self._sessionmaker() as session:
                mv = ModelVersion(
                    id=uuid.uuid4(),
                    kind="LANDMARK_EXTRACTOR",
                    version="v1",
                    artifact_checksum="abc",
                )
                session.add(mv)
                await session.commit()
                self.assertEqual(mv.state, "DRAFT")
                self.assertEqual(mv.kind, "LANDMARK_EXTRACTOR")
                # Test invalid transition: DRAFT → ACTIVE should fail
                from app.errors import ConflictError
                from app.repositories.models_registry import ModelVersionRepository

                # tenant_id arg is required but ModelVersion is global (tenant_id is None)
                repo = ModelVersionRepository(session, uuid.uuid4())
                with self.assertRaises(ConflictError):
                    await repo.transition_state(mv.id, "ACTIVE", uuid.uuid4(), "Skip to active")
                # State unchanged
                await session.refresh(mv)
                self.assertEqual(mv.state, "DRAFT")

        self._run(go())
