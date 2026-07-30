"""Structured logging, Prometheus metrics, and OpenTelemetry setup.

MG-STUB: final — uses structlog, prometheus_client, opentelemetry.
No PII or biometric data is ever logged; only IDs, durations, statuses.
"""
from __future__ import annotations

import logging
import sys

import structlog
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# ----------------------------- Logging ----------------------------------


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog for JSON output to stdout."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    # Bridge stdlib logging (uvicorn, sqlalchemy, etc.)
    logging.basicConfig(level=log_level, format="%(message)s")


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[return-value]


# ----------------------------- Metrics ----------------------------------


# API
HTTP_REQUESTS_TOTAL = Counter(
    "mimicguard_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION = Histogram(
    "mimicguard_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
HTTP_REQUESTS_IN_FLIGHT = Gauge(
    "mimicguard_http_requests_in_flight", "In-flight HTTP requests"
)

# Worker / pipeline
WORKER_JOBS_IN_FLIGHT = Gauge(
    "mimicguard_worker_jobs_in_flight", "Worker jobs currently processing", ["stage"]
)
WORKER_STAGE_DURATION = Histogram(
    "mimicguard_worker_stage_duration_seconds",
    "Worker stage duration",
    ["stage", "outcome"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600, 900),
)
WORKER_RETRY_TOTAL = Counter(
    "mimicguard_worker_retry_total", "Worker stage retries", ["stage", "reason"]
)
WORKER_DLQ_TOTAL = Counter("mimicguard_worker_dlq_total", "Worker DLQ messages", ["stage"])

QUALITY_REJECTION_TOTAL = Counter(
    "mimicguard_quality_rejection_total",
    "Quality rejections by code",
    ["code"],
)
DECISIONS_TOTAL = Counter(
    "mimicguard_decisions_total",
    "Decisions emitted",
    ["label", "model_version"],
)
PHRASE_TEMPLATES_TOTAL = Gauge(
    "mimicguard_phrase_templates_total", "Total PhraseTemplates"
)
PHRASE_TEMPLATE_SAMPLES = Histogram(
    "mimicguard_phrase_template_samples",
    "Samples per PhraseTemplate",
    buckets=(1, 3, 5, 10, 20, 30, 50),
)

# Outbox
OUTBOX_LAG_SECONDS = Gauge(
    "mimicguard_outbox_lag_seconds", "Outbox relay lag (seconds)"
)
OUTBOX_PENDING_TOTAL = Gauge(
    "mimicguard_outbox_pending_total", "Outbox events pending publish"
)

# Storage
DB_POOL_IN_USE = Gauge("mimicguard_db_pool_in_use", "DB connections in use")
REDIS_POOL_IN_USE = Gauge("mimicguard_redis_pool_in_use", "Redis connections in use")


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


# ----------------------------- Tracing ----------------------------------


_OTEL_CONFIGURED = False


def configure_tracing(service_name: str, otlp_endpoint: str | None) -> None:
    """Initialize OpenTelemetry tracing. Safe to call multiple times."""
    global _OTEL_CONFIGURED
    if _OTEL_CONFIGURED:
        return
    _OTEL_CONFIGURED = True
    if not otlp_endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
    except Exception as e:  # pragma: no cover
        logging.warning("OTel tracing setup failed: %s", e)
