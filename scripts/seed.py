"""Seed script: creates default tenant, admin user, baseline model.

MG-STUB: final.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))

from app.db import session_scope
from app.db.models import ModelVersion, Tenant, User
from app.security.passwords import hash_password
from app.settings import get_settings


async def seed() -> None:
    settings = get_settings()
    async with session_scope() as session:
        # Default tenant
        result = await session.execute(
            __import__("sqlalchemy").select(Tenant).where(Tenant.slug == settings.default_tenant_slug)
        )
        tenant = result.scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(
                id=uuid.uuid4(),
                slug=settings.default_tenant_slug,
                name="Default Tenant",
                settings={},
            )
            session.add(tenant)
            await session.flush()
            print(f"Created tenant: {tenant.slug} ({tenant.id})")
        else:
            print(f"Tenant exists: {tenant.slug} ({tenant.id})")

        # Default admin
        result = await session.execute(
            __import__("sqlalchemy").select(User).where(
                User.tenant_id == tenant.id, User.email == settings.default_admin_email
            )
        )
        admin = result.scalar_one_or_none()
        if admin is None:
            admin = User(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                email=settings.default_admin_email,
                password_hash=hash_password(settings.default_admin_password),
                display_name="System Administrator",
                roles=["system_admin", "operator", "reviewer", "model_admin", "auditor"],
            )
            session.add(admin)
            await session.flush()
            print(f"Created admin: {admin.email}")
        else:
            print(f"Admin exists: {admin.email}")

        # Default model versions
        from sqlalchemy import select

        for kind, version in [
            ("LANDMARK_EXTRACTOR", "mediapipe-v1"),
            ("ASR", "faster-whisper-small"),
            ("MOTION_SCORER", "statistical-v1"),
            ("CALIBRATION", "default-v1"),
        ]:
            result = await session.execute(
                select(ModelVersion).where(
                    ModelVersion.kind == kind, ModelVersion.version == version
                )
            )
            m = result.scalar_one_or_none()
            if m is None:
                m = ModelVersion(
                    id=uuid.uuid4(),
                    kind=kind,
                    version=version,
                    artifact_checksum=f"{hash(version):x}",
                    code_commit="initial",
                    feature_schema="motion-v1",
                    training_dataset_manifest={"sources": []},
                    evaluation_report={"AUC": 0.0, "FAR": 0.0, "FRR": 0.0},
                    calibration_profile={"type": "none"},
                    intended_use=f"{kind} baseline",
                    known_limitations="Initial bootstrap version. No validation data yet.",
                    state="ACTIVE",
                    approver_id=admin.id,
                    approved_at=datetime.now(UTC),
                    promoted_by=admin.id,
                    promoted_at=datetime.now(UTC),
                    promotion_reason="Initial seed",
                )
                session.add(m)
                print(f"Created model: {kind} {version}")
            else:
                print(f"Model exists: {kind} {version}")


if __name__ == "__main__":
    asyncio.run(seed())
