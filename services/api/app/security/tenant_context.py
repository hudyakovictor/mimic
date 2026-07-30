"""Tenant context — JWT-driven tenant scoping."""
from __future__ import annotations

import uuid
from contextvars import ContextVar

_tenant_id_var: ContextVar[uuid.UUID | None] = ContextVar("tenant_id", default=None)


class TenantContext:
    @staticmethod
    def set(tenant_id: uuid.UUID) -> None:
        _tenant_id_var.set(tenant_id)

    @staticmethod
    def get() -> uuid.UUID | None:
        return _tenant_id_var.get()

    @staticmethod
    def reset(token) -> None:
        _tenant_id_var.reset(token)


def get_current_tenant_id() -> uuid.UUID | None:
    return _tenant_id_var.get()
