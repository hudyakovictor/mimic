"""Dramatiq broker + setup.

MG-STUB: final.
"""
from __future__ import annotations

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import (
    AgeLimit,
    Prometheus,
    Retries,
    TimeLimit,
)
from dramatiq.results import Results
from dramatiq.results.backends.redis import RedisBackend

from app.settings import get_settings

_broker: RedisBroker | None = None
_results: RedisBackend | None = None


def get_broker() -> RedisBroker:
    global _broker
    if _broker is None:
        settings = get_settings()
        _broker = RedisBroker(url=settings.redis_broker_url)
        dramatiq.set_broker(_broker)
    return _broker


def get_results() -> RedisBackend:
    global _results
    if _results is None:
        settings = get_settings()
        _results = RedisBackend(url=settings.redis_broker_url)
    return _results


def setup() -> RedisBroker:
    settings = get_settings()
    broker = get_broker()
    broker.add_middleware(Prometheus())
    broker.add_middleware(Retries(max_retries=settings.worker_retry_default))
    broker.add_middleware(AgeLimit(max_age=3_600_000))
    broker.add_middleware(TimeLimit())
    broker.add_middleware(Results(backend=get_results()))
    return broker
