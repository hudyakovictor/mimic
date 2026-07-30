"""Tests for JWT, RBAC, password hashing."""
from __future__ import annotations

import unittest
import uuid

from app.security.jwt_service import JwtService
from app.security.passwords import hash_password, verify_password
from app.security.rbac import (
    Permission,
    RolePermissionMatrix,
    has_permission,
    has_role,
)
from app.settings import get_settings


class PasswordTests(unittest.TestCase):
    def test_hash_and_verify(self):
        h = hash_password("my-secret-password-123")
        self.assertNotEqual(h, "my-secret-password-123")
        self.assertTrue(verify_password("my-secret-password-123", h))

    def test_wrong_password_fails(self):
        h = hash_password("correct-horse-battery-staple")
        self.assertFalse(verify_password("wrong-password", h))

    def test_bcrypt_cost(self):
        """Bcrypt rounds must be ≥ 12 (security policy)."""
        h = hash_password("test-password")
        # bcrypt hash format: $2b$XX$...
        cost = int(h.split("$")[2])
        self.assertGreaterEqual(cost, 12)


class JWTTests(unittest.TestCase):
    def setUp(self):
        self.svc = JwtService(get_settings())
        self.user_id = uuid.uuid4()
        self.tenant_id = uuid.uuid4()

    def test_encode_decode_roundtrip(self):
        token, ttl = self.svc.encode_access(self.user_id, self.tenant_id, ["operator"])
        self.assertGreater(ttl, 0)
        claims = self.svc.decode(token)
        self.assertEqual(claims["sub"], str(self.user_id))
        self.assertEqual(claims["tid"], str(self.tenant_id))
        self.assertEqual(claims["roles"], ["operator"])

    def test_refresh_token_type_enforced(self):
        access, _ = self.svc.encode_access(self.user_id, self.tenant_id, [])
        refresh = self.svc.encode_refresh(self.user_id, self.tenant_id)
        with self.assertRaises(Exception):
            self.svc.decode(refresh, expect_type="access")
        # refresh decodes with expect_type=refresh
        claims = self.svc.decode(refresh, expect_type="refresh")
        self.assertEqual(claims["typ"], "refresh")

    def test_invalid_signature_rejected(self):
        token, _ = self.svc.encode_access(self.user_id, self.tenant_id, [])
        tampered = token[:-2] + ("AB" if token[-2:] != "AB" else "CD")
        with self.assertRaises(Exception):
            self.svc.decode(tampered)

    def test_audience_mismatch_rejected(self):
        """Tokens from a different audience must be rejected."""
        token, _ = self.svc.encode_access(self.user_id, self.tenant_id, [])
        # Manually craft a token with wrong audience by hacking the secret
        from jose import jwt as jose_jwt

        bad = jose_jwt.encode(
            {
                "sub": str(self.user_id),
                "tid": str(self.tenant_id),
                "roles": [],
                "aud": "different-audience",
                "iss": self.svc.settings.jwt_issuer,
                "exp": 9_999_999_999,
            },
            self.svc.settings.jwt_secret.get_secret_value(),
            algorithm=self.svc.settings.jwt_alg,
        )
        with self.assertRaises(Exception):
            self.svc.decode(bad)


class RBACTests(unittest.TestCase):
    """Lightweight fake-User to exercise the matrix without DB."""

    def _user(self, roles: list[str], active: bool = True) -> "User":
        from app.db.models import User

        return User(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="t@x.io",
            password_hash="x",
            display_name="t",
            roles=roles,
            is_active=active,
        )

    def test_system_admin_has_all_permissions(self):
        u = self._user(["system_admin"])
        for perm in Permission:
            self.assertTrue(has_permission(u, perm), f"system_admin missing {perm}")

    def test_operator_lacks_review_write(self):
        u = self._user(["operator"])
        self.assertTrue(has_permission(u, Permission.ASSET_READ))
        self.assertTrue(has_permission(u, Permission.JOB_WRITE))
        self.assertFalse(has_permission(u, Permission.REVIEW_WRITE))
        self.assertFalse(has_permission(u, Permission.MODEL_PROMOTE))
        self.assertFalse(has_permission(u, Permission.AUDIT_EXPORT))

    def test_reviewer_can_write_reviews(self):
        u = self._user(["reviewer"])
        self.assertTrue(has_permission(u, Permission.REVIEW_WRITE))
        self.assertTrue(has_permission(u, Permission.BASELINE_READ))
        self.assertFalse(has_permission(u, Permission.MODEL_PROMOTE))

    def test_auditor_can_export(self):
        u = self._user(["auditor"])
        self.assertTrue(has_permission(u, Permission.AUDIT_READ))
        self.assertTrue(has_permission(u, Permission.AUDIT_EXPORT))
        self.assertFalse(has_permission(u, Permission.JOB_WRITE))

    def test_inactive_user_has_no_permissions(self):
        u = self._user(["system_admin"], active=False)
        self.assertFalse(has_permission(u, Permission.ASSET_READ))

    def test_has_role(self):
        u = self._user(["operator", "reviewer"])
        self.assertTrue(has_role(u, "operator"))
        self.assertTrue(has_role(u, "reviewer"))
        self.assertFalse(has_role(u, "model_admin"))

    def test_matrix_covers_all_roles(self):
        """Every role mentioned in the enum must have an entry in the matrix."""
        # Operators, reviewers, model_admins, auditors, system_admins
        for role in ("operator", "reviewer", "model_admin", "auditor", "system_admin"):
            self.assertIn(role, RolePermissionMatrix)
