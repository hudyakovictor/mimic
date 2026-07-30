"""Tests for application settings."""
from __future__ import annotations

import unittest


class SettingsTests(unittest.TestCase):
    def test_settings_load_from_env(self):
        import os

        os.environ["DATABASE_URL"] = "postgresql+asyncpg://x/y"
        os.environ["JWT_SECRET"] = "abc"
        from app.settings import get_settings

        get_settings.cache_clear()
        s = get_settings()
        self.assertEqual(s.env, "development")
        self.assertEqual(s.log_level, "INFO")
        self.assertIn("postgresql", s.database_url)
        # Restore default
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
        get_settings.cache_clear()

    def test_settings_secrets_are_obscured_in_repr(self):
        """SecretStr values must be masked in repr()."""
        from app.settings import get_settings

        get_settings.cache_clear()
        s = get_settings()
        r = repr(s)
        # Secrets are SecretStr and should be masked as '**********'
        self.assertIn("**********", r)
        # Actual secret value must NOT appear
        self.assertNotIn(s.jwt_secret.get_secret_value(), r)

    def test_settings_singleton(self):
        from app.settings import get_settings

        s1 = get_settings()
        s2 = get_settings()
        self.assertIs(s1, s2)

    def test_decision_thresholds_sane(self):
        from app.settings import Settings

        s = Settings()
        # CONSISTENT < SUSPICIOUS
        self.assertLess(s.decision_risk_consistent_max, s.decision_risk_suspicious_min)
        # Both in [0, 1]
        self.assertGreaterEqual(s.decision_risk_consistent_max, 0.0)
        self.assertLessEqual(s.decision_risk_suspicious_min, 1.0)
        # Maturity >= minimum
        self.assertGreaterEqual(s.phrase_baseline_mature_samples, s.phrase_baseline_min_samples)
        # Max >= maturity
        self.assertGreaterEqual(s.phrase_template_max_samples, s.phrase_baseline_mature_samples)
