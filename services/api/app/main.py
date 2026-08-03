"""FastAPI composition root.

MG-STUB: final — wires middleware, routers, error handlers, startup/shutdown.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from .db import close_db
from .errors import register_exception_handlers
from .observability import (
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_IN_FLIGHT,
    HTTP_REQUESTS_TOTAL,
    configure_logging,
    configure_tracing,
    get_logger,
)
from .routers import assets as assets_mod
from .routers import audit as audit_mod
from .routers import auth as auth_mod
from .routers import dashboard as dashboard_mod
from .routers import jobs as jobs_mod
from .routers import models as models_mod
from .routers import reviews as reviews_mod
from .routers import subjects as subjects_mod
from .routers import system as system_mod
from .routers import words as words_mod
from .security.tenant_context import TenantContext
from .settings import get_settings
from .storage import init_buckets

log = get_logger(__name__)


async def _outbox_relay_loop() -> None:
    """Continuously deliver transactional outbox rows after DB commit."""
    from .db.session import session_scope
    from .dependencies import get_redis
    from .events.publisher import get_publisher

    settings = get_settings()
    publisher = get_publisher(await get_redis())
    while True:
        try:
            async with session_scope() as session:
                await publisher.publish_pending_outbox(
                    session,
                    batch_size=settings.outbox_batch_size,
                    max_attempts=settings.outbox_max_attempts,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("outbox.relay_iteration_failed", error=str(exc))
        await asyncio.sleep(settings.outbox_poll_interval_ms / 1000)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_file)
    configure_tracing(settings.service_name, settings.otel_exporter_otlp_endpoint)
    log.info("api.startup", env=settings.env)

    # Initialize storage
    try:
        from .dependencies import get_s3_client

        s3 = get_s3_client(settings)
        await init_buckets(s3)
    except Exception as e:
        log.warning("api.startup.storage_init_failed", error=str(e))

    relay_task = asyncio.create_task(_outbox_relay_loop(), name="outbox-relay")
    try:
        yield
    finally:
        relay_task.cancel()
        try:
            await relay_task
        except asyncio.CancelledError:
            pass
        log.info("api.shutdown")
        await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="MimicGuard API",
        version="0.1.0",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # Middlewares
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        from structlog.contextvars import bind_contextvars, clear_contextvars

        clear_contextvars()
        bind_contextvars(request_id=request_id, service="api")
        TenantContext.set(None)  # clear
        start = time.perf_counter()
        HTTP_REQUESTS_IN_FLIGHT.inc()
        try:
            response = await call_next(request)
        except Exception:
            HTTP_REQUESTS_IN_FLIGHT.dec()
            log.exception(
                "http.request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
            )
            raise
        duration = time.perf_counter() - start
        HTTP_REQUESTS_IN_FLIGHT.dec()
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        method = request.method
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=str(status_code)).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(duration)
        log.info(
            "http.request_completed",
            method=method,
            path=path,
            status=status_code,
            duration_ms=round(duration * 1000, 2),
        )
        return response

    register_exception_handlers(app)

    # Routers
    app.include_router(system_mod.router)
    app.include_router(auth_mod.router)
    app.include_router(assets_mod.router)
    app.include_router(jobs_mod.router)
    app.include_router(subjects_mod.router)
    app.include_router(words_mod.router)
    app.include_router(reviews_mod.router)
    app.include_router(models_mod.router)
    app.include_router(audit_mod.router)
    app.include_router(dashboard_mod.router)

    return app


app = create_app()
