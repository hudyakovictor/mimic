"""Domain error types and exception handlers.

All errors raised by services/repositories should be subclasses of ApiError.
Handlers convert them to RFC 7807-style JSON responses with correlationId.
"""
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from .observability import get_logger

log = get_logger(__name__)


class ApiError(Exception):
    """Base exception for all domain errors."""

    code: str = "internal_error"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(
        self,
        message: str = "Internal error",
        *,
        code: str | None = None,
        status_code: int | None = None,
        field_errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.field_errors = field_errors or []


class NotFoundError(ApiError):
    code = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class PermissionDeniedError(ApiError):
    code = "permission_denied"
    status_code = status.HTTP_403_FORBIDDEN


class UnauthorizedError(ApiError):
    code = "unauthorized"
    status_code = status.HTTP_401_UNAUTHORIZED


class ValidationFailedError(ApiError):
    code = "validation_failed"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class ConflictError(ApiError):
    code = "conflict"
    status_code = status.HTTP_409_CONFLICT


class RateLimitError(ApiError):
    code = "rate_limited"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class IdempotencyKeyRequiredError(ApiError):
    code = "idempotency_key_required"
    status_code = status.HTTP_400_BAD_REQUEST


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    body = {
        "code": exc.code,
        "message": exc.message,
        "correlationId": _correlation_id(request),
        "fieldErrors": exc.field_errors,
    }
    return JSONResponse(status_code=exc.status_code, content=body)


async def request_validation_handler(
    request: Request, exc: RequestValidationError | PydanticValidationError
) -> JSONResponse:
    field_errors = []
    errors = exc.errors() if hasattr(exc, "errors") else []
    for e in errors:
        field_errors.append(
            {
                "field": ".".join(str(p) for p in e.get("loc", [])),
                "message": e.get("msg", "invalid"),
                "type": e.get("type"),
            }
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "validation_failed",
            "message": "Request validation failed",
            "correlationId": _correlation_id(request),
            "fieldErrors": field_errors,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_exception", path=request.url.path, exc_type=type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "internal_error",
            "message": "Internal server error",
            "correlationId": _correlation_id(request),
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all error handlers on the FastAPI app."""
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(PydanticValidationError, request_validation_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
