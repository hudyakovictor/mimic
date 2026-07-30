"""Model registry repository."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import desc, select

from ..db.models import ModelVersion
from .base import BaseRepository


class ModelVersionRepository(BaseRepository[ModelVersion]):
    model = ModelVersion

    async def list_filtered(
        self,
        kind: str | None = None,
        state: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[ModelVersion], str | None]:
        stmt = select(ModelVersion)
        if kind:
            stmt = stmt.where(ModelVersion.kind == kind)
        if state:
            stmt = stmt.where(ModelVersion.state == state)
        return await self.paginate(stmt, cursor, limit)

    async def get_active(self, kind: str) -> ModelVersion | None:
        stmt = (
            select(ModelVersion)
            .where(ModelVersion.kind == kind, ModelVersion.state == "ACTIVE")
            .order_by(desc(ModelVersion.promoted_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def transition_state(
        self,
        model_id: uuid.UUID,
        to_state: str,
        actor_id: uuid.UUID,
        reason: str,
    ) -> ModelVersion:
        from ..errors import ConflictError, NotFoundError

        m = await self.session.get(ModelVersion, model_id)
        if m is None:
            raise NotFoundError("Model not found")

        valid_transitions = {
            "DRAFT": {"VALIDATED", "RETIRED"},
            "VALIDATED": {"SHADOW", "RETIRED"},
            "SHADOW": {"ACTIVE", "RETIRED"},
            "ACTIVE": {"RETIRED"},
            "RETIRED": set(),
        }
        if to_state not in valid_transitions.get(m.state, set()):
            raise ConflictError(
                f"Cannot transition {m.state} → {to_state}",
                code="invalid_state_transition",
            )

        if to_state == "ACTIVE":
            # Demote current ACTIVE
            current = await self.get_active(m.kind)
            if current is not None and current.id != m.id:
                current.state = "RETIRED"
                current.promoted_by = actor_id
                current.promoted_at = datetime.now(UTC)
                current.promotion_reason = f"Auto-demoted on activation of {m.id}"
                current.version = (current.version or 1) + 1
                await self.session.flush()

        m.state = to_state
        m.promoted_by = actor_id
        m.promoted_at = datetime.now(UTC)
        m.promotion_reason = reason
        m.version = (m.version or 1) + 1
        await self.session.flush()
        return m
