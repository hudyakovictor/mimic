"""Tests for API error classes and exception handlers."""
from __future__ import annotations

import unittest

from app.errors import (
    ApiError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    UnauthorizedError,
    ValidationFailedError,
)


class ApiErrorTests(unittest.TestCase):
    def test_base_error_default_code(self):
        e = ApiError("boom")
        self.assertEqual(e.status_code, 500)
        self.assertEqual(e.code, "internal_error")

    def test_subclass_codes(self):
        self.assertEqual(NotFoundError("x").code, "not_found")
        self.assertEqual(NotFoundError("x").status_code, 404)
        self.assertEqual(PermissionDeniedError("x").code, "permission_denied")
        self.assertEqual(PermissionDeniedError("x").status_code, 403)
        self.assertEqual(UnauthorizedError("x").code, "unauthorized")
        self.assertEqual(UnauthorizedError("x").status_code, 401)
        self.assertEqual(ValidationFailedError("x").code, "validation_failed")
        self.assertEqual(ValidationFailedError("x").status_code, 422)
        self.assertEqual(ConflictError("x").code, "conflict")
        self.assertEqual(ConflictError("x").status_code, 409)
        self.assertEqual(RateLimitError("x").code, "rate_limited")
        self.assertEqual(RateLimitError("x").status_code, 429)

    def test_field_errors_attachable(self):
        e = ValidationFailedError("bad", field_errors=[{"field": "email", "message": "x"}])
        self.assertEqual(len(e.field_errors), 1)
        self.assertEqual(e.field_errors[0]["field"], "email")

    def test_override_code_and_status(self):
        e = ApiError("x", code="custom", status_code=418)
        self.assertEqual(e.code, "custom")
        self.assertEqual(e.status_code, 418)
