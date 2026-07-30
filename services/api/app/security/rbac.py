"""Role-based access control.

MG-STUB: final. 5 базовых ролей: operator, reviewer, model_admin, auditor, system_admin.
"""
from __future__ import annotations

from enum import StrEnum

from fastapi import Depends

from ..db.models import User
from ..errors import PermissionDeniedError
from .current_user import get_current_user


class Permission(StrEnum):
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    ROLE_ASSIGN = "user:role_assign"
    ASSET_READ = "asset:read"
    ASSET_WRITE = "asset:write"
    ASSET_DOWNLOAD = "asset:download"
    VIDEO_READ = "video:read"
    BIOMETRIC_EXPORT = "biometric:export"
    SUBJECT_READ = "subject:read"
    SUBJECT_WRITE = "subject:write"
    SUBJECT_DELETE = "subject:delete"
    JOB_READ = "job:read"
    JOB_WRITE = "job:write"
    JOB_RETRY = "job:retry"
    DECISION_READ = "decision:read"
    REVIEW_WRITE = "review:write"
    MODEL_READ = "model:read"
    MODEL_PROMOTE = "model:promote"
    MODEL_ROLLBACK = "model:rollback"
    BASELINE_READ = "baseline:read"
    BASELINE_REBUILD = "baseline:rebuild"
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    SYSTEM_ADMIN = "system:admin"


RolePermissionMatrix: dict[str, set[Permission]] = {
    "operator": {
        Permission.ASSET_READ,
        Permission.ASSET_WRITE,
        Permission.ASSET_DOWNLOAD,
        Permission.VIDEO_READ,
        Permission.SUBJECT_READ,
        Permission.SUBJECT_WRITE,
        Permission.JOB_READ,
        Permission.JOB_WRITE,
        Permission.JOB_RETRY,
        Permission.DECISION_READ,
        Permission.BASELINE_READ,
    },
    "reviewer": {
        Permission.ASSET_READ,
        Permission.ASSET_DOWNLOAD,
        Permission.VIDEO_READ,
        Permission.SUBJECT_READ,
        Permission.JOB_READ,
        Permission.DECISION_READ,
        Permission.REVIEW_WRITE,
        Permission.BASELINE_READ,
    },
    "model_admin": {
        Permission.MODEL_READ,
        Permission.MODEL_PROMOTE,
        Permission.MODEL_ROLLBACK,
        Permission.BASELINE_READ,
        Permission.BASELINE_REBUILD,
    },
    "auditor": {
        Permission.USER_READ,
        Permission.AUDIT_READ,
        Permission.AUDIT_EXPORT,
    },
    "system_admin": set(Permission),  # all
}


def has_permission(user: User, perm: Permission) -> bool:
    if not user.is_active:
        return False
    if Permission.SYSTEM_ADMIN.value in user.roles:
        return True
    for role in user.roles:
        if perm in RolePermissionMatrix.get(role, set()):
            return True
    return False


def has_role(user: User, *roles: str) -> bool:
    return any(r in user.roles for r in roles)


def require_permission(perm: Permission):
    """FastAPI dependency factory: enforces permission."""

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user, perm):
            raise PermissionDeniedError(
                f"User lacks permission {perm.value}",
                code="permission_denied",
            )
        return user

    return _checker


def require_role(*roles: str):
    """FastAPI dependency factory: enforces role membership."""

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if not has_role(user, *roles):
            raise PermissionDeniedError(
                f"User must have one of roles: {','.join(roles)}",
                code="permission_denied",
            )
        return user

    return _checker
