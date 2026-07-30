"""Dramatiq worker composition root.

Run with::

    PYTHONPATH=services/api:services/worker:. dramatiq worker.__main__ -p 2 -t 4
"""

from __future__ import annotations

from worker.broker import setup

# The Redis broker must be installed before decorators register actors.
broker = setup()

# Import side effects: register actors on the configured broker.
from worker.actors import pipeline as pipeline  # noqa: E402
