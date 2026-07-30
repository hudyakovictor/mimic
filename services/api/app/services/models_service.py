"""Model registry service."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import User
from ..events.outbox import OutboxRepository
from ..repositories.models_registry import ModelVersionRepository


class ModelService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID, actor: User):
        self.session = session
        self.tenant_id = tenant_id
        self.actor = actor
        self.repo = ModelVersionRepository(session, tenant_id)
        self.outbox = OutboxRepository(session)

    async def list(
        self,
        kind: str | None = None,
        state: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[dict], str | None]:
        items, nc = await self.repo.list_filtered(kind, state, cursor, limit)
        return [self._to_dict(m) for m in items], nc

    async def get(self, model_id: uuid.UUID) -> dict:
        m = await self.repo.get(model_id)
        if m is None:
            from ..errors import NotFoundError

            raise NotFoundError("Model not found")
        return self._to_dict(m)

    async def promote(self, model_id: uuid.UUID, to_state: str, reason: str) -> dict:
        m = await self.repo.transition_state(model_id, to_state, self.actor.id, reason)
        await self.outbox.create(
            event_name="model.promoted.v1",
            payload={
                "model_id": str(m.id),
                "kind": m.kind,
                "to_state": to_state,
                "actor_id": str(self.actor.id),
                "reason": reason,
            },
        )
        return self._to_dict(m)

    def _to_dict(self, m) -> dict:
        return {
            "id": str(m.id),
            "kind": m.kind,
            "version": m.version,
            "artifact_checksum": m.artifact_checksum,
            "code_commit": m.code_commit,
            "feature_schema": m.feature_schema,
            "state": m.state,
            "intended_use": m.intended_use,
            "known_limitations": m.known_limitations,
            "evaluation_report": m.evaluation_report or {},
            "calibration_profile": m.calibration_profile or {},
            "approver_id": str(m.approver_id) if m.approver_id else None,
            "approved_at": m.approved_at,
            "promoted_by": str(m.promoted_by) if m.promoted_by else None,
            "promoted_at": m.promoted_at,
            "created_at": m.created_at,
        }
