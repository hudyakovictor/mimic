"""IDOR (Insecure Direct Object Reference) test matrix.

For every endpoint that takes a resource_id, verify that user from tenant A
cannot read/write data belonging to tenant B. This is the #1 security
threat in multitenant systems.
"""
from __future__ import annotations

import os
import unittest
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-for-idor-tests")


def _bootstrap_two_tenants():
    """Create schema + two tenants (A and B), each with one admin user."""
    import asyncio
    from app.db import session as _session_mod
    from app.db.models import Base, Subject, Tenant, User
    from app.security.passwords import hash_password
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    sm = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    _session_mod._engine = test_engine
    _session_mod._sessionmaker = sm

    async def _go():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sm() as session:
            t_a = Tenant(id=uuid.uuid4(), slug="tenant-a", name="A")
            t_b = Tenant(id=uuid.uuid4(), slug="tenant-b", name="B")
            session.add_all([t_a, t_b])
            u_a = User(
                id=uuid.uuid4(),
                tenant_id=t_a.id,
                email="a@a.io",
                password_hash=hash_password("pass-a-1234"),
                display_name="A",
                roles=["system_admin", "operator", "reviewer", "model_admin", "auditor"],
                is_active=True,
            )
            u_b = User(
                id=uuid.uuid4(),
                tenant_id=t_b.id,
                email="b@b.io",
                password_hash=hash_password("pass-b-1234"),
                display_name="B",
                roles=["system_admin", "operator", "reviewer", "model_admin", "auditor"],
                is_active=True,
            )
            s_a = Subject(
                id=uuid.uuid4(),
                tenant_id=t_a.id,
                external_id="subj-a",
                display_name="Subject A",
                consent_state="GRANTED",
            )
            s_b = Subject(
                id=uuid.uuid4(),
                tenant_id=t_b.id,
                external_id="subj-b",
                display_name="Subject B",
                consent_state="GRANTED",
            )
            session.add_all([u_a, u_b, s_a, s_b])
            await session.commit()
            return t_a.id, t_b.id, s_a.id, s_b.id, u_a.id, u_b.id

    return asyncio.run(_go())


def _login(client, email, password):
    r = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    # Wire format is camelCase
    return body.get("accessToken") or body["access_token"]


class IDORMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient

        cls.tenant_a, cls.tenant_b, cls.subject_a, cls.subject_b, cls.user_a, cls.user_b = (
            _bootstrap_two_tenants()
        )
        from app.main import app
        from app.db import get_db

        async def _override():
            from app.db.session import get_sessionmaker

            sm = get_sessionmaker()
            async with sm() as s:
                try:
                    yield s
                except Exception:
                    await s.rollback()
                    raise

        app.dependency_overrides[get_db] = _override
        cls.client = TestClient(app)

    def _token_a(self):
        return _login(self.client, "a@a.io", "pass-a-1234")

    def _token_b(self):
        return _login(self.client, "b@b.io", "pass-b-1234")

    def _hdr(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_tenant_a_sees_only_own_subjects(self):
        tok = self._token_a()
        r = self.client.get("/v1/subjects", headers=self._hdr(tok))
        self.assertEqual(r.status_code, 200)
        subjects = r.json()
        ids = {s["id"] for s in subjects}
        # Wire format returns UUIDs as strings
        self.assertIn(str(self.subject_a), ids)
        self.assertNotIn(str(self.subject_b), ids)

    def test_tenant_b_cannot_get_tenant_a_subject(self):
        tok_b = self._token_b()
        r = self.client.get(f"/v1/subjects/{self.subject_a}", headers=self._hdr(tok_b))
        # 404 (not 403) — never leak existence
        self.assertEqual(r.status_code, 404)

    def test_tenant_b_cannot_update_tenant_a_subject(self):
        tok_b = self._token_b()
        r = self.client.patch(
            f"/v1/subjects/{self.subject_a}",
            json={"displayName": "HACKED", "version": 1},
            headers=self._hdr(tok_b),
        )
        # 404 (resource not visible in tenant B's scope)
        self.assertEqual(r.status_code, 404)

    def test_tenant_b_cannot_record_consent_for_tenant_a_subject(self):
        tok_b = self._token_b()
        r = self.client.post(
            f"/v1/subjects/{self.subject_a}/consent",
            json={"state": "REVOKED"},
            headers=self._hdr(tok_b),
        )
        self.assertEqual(r.status_code, 404)

    def test_unknown_subject_returns_404_not_500(self):
        tok = self._token_a()
        fake_id = str(uuid.uuid4())
        r = self.client.get(f"/v1/subjects/{fake_id}", headers=self._hdr(tok))
        self.assertEqual(r.status_code, 404)

    def test_invalid_uuid_format(self):
        tok = self._token_a()
        r = self.client.get("/v1/subjects/not-a-uuid", headers=self._hdr(tok))
        # FastAPI returns 422 for invalid path param format
        self.assertEqual(r.status_code, 422)


class RBACEnforcementTests(unittest.TestCase):
    """Verify that each role can only access endpoints for which it has permission."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient

        _bootstrap_two_tenants()
        from app.main import app
        from app.db import get_db

        async def _override():
            from app.db.session import get_sessionmaker

            sm = get_sessionmaker()
            async with sm() as s:
                try:
                    yield s
                except Exception:
                    await s.rollback()
                    raise

        app.dependency_overrides[get_db] = _override
        cls.client = TestClient(app)

    def _create_user_with_role(self, role: str) -> str:
        """Helper: create a user with one role, log in, return token."""
        import asyncio
        from app.db.models import User
        from app.db.session import get_sessionmaker
        from app.security.passwords import hash_password

        sm = get_sessionmaker()

        async def _go():
            async with sm() as session:
                # Pick tenant A
                from sqlalchemy import select

                from app.db.models import Tenant

                res = await session.execute(select(Tenant).where(Tenant.slug == "tenant-a"))
                tenant = res.scalar_one()
                # Use unique email per role to avoid UNIQUE collisions
                email = f"{role}-test-{uuid.uuid4().hex[:8]}@a.io"
                user = User(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    email=email,
                    password_hash=hash_password(f"pass-{role}-123"),
                    display_name=role.title(),
                    roles=[role],
                    is_active=True,
                )
                session.add(user)
                await session.commit()
                return email

        email = asyncio.run(_go())
        tok = _login(self.client, email, f"pass-{role}-123")
        return tok

    def test_auditor_cannot_create_jobs(self):
        tok = self._create_user_with_role("auditor")
        r = self.client.post(
            "/v1/analysis-jobs",
            json={"assetId": str(uuid.uuid4()), "claimedPersonId": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {tok}"},
        )
        self.assertEqual(r.status_code, 403)

    def test_auditor_cannot_create_subjects(self):
        tok = self._create_user_with_role("auditor")
        r = self.client.post(
            "/v1/subjects",
            json={"externalId": "x", "displayName": "x"},
            headers={"Authorization": f"Bearer {tok}"},
        )
        self.assertEqual(r.status_code, 403)

    def test_operator_cannot_read_audit(self):
        tok = self._create_user_with_role("operator")
        r = self.client.get("/v1/audit", headers={"Authorization": f"Bearer {tok}"})
        self.assertEqual(r.status_code, 403)

    def test_reviewer_cannot_promote_models(self):
        tok = self._create_user_with_role("reviewer")
        # First get a model
        m = self.client.get("/v1/models", headers={"Authorization": f"Bearer {tok}"})
        if m.status_code == 200 and m.json():
            model_id = m.json()[0]["id"]
            r = self.client.post(
                f"/v1/models/{model_id}:promote",
                json={"toState": "ACTIVE", "reason": "test promote attempt"},
                headers={"Authorization": f"Bearer {tok}"},
            )
            self.assertEqual(r.status_code, 403)

    def test_model_admin_can_promote_own_models(self):
        tok = self._create_user_with_role("model_admin")
        m = self.client.get("/v1/models", headers={"Authorization": f"Bearer {tok}"})
        self.assertEqual(m.status_code, 200)
        if m.json():
            model_id = m.json()[0]["id"]
            # Get current state
            current = self.client.get(
                f"/v1/models/{model_id}", headers={"Authorization": f"Bearer {tok}"}
            )
            self.assertEqual(current.status_code, 200)
            # Try to promote (will likely fail due to invalid state transition, but not due to RBAC)
            r = self.client.post(
                f"/v1/models/{model_id}:promote",
                json={"toState": "SHADOW", "reason": "test promote for RBAC test"},
                headers={"Authorization": f"Bearer {tok}"},
            )
            # RBAC passes; could be 200 or 409 (invalid state transition) — not 403
            self.assertIn(r.status_code, (200, 409))
