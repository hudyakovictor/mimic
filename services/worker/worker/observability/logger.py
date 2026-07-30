"""Worker-side observability utilities."""
from __future__ import annotations

import structlog


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[return-value]
