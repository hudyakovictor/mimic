"""Top-level conftest — makes both `app` and `services` importable from tests.

This file is auto-loaded by pytest before any test collection.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Make `app` (services/api/app) and `packages` importable
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT / "services" / "worker"))
