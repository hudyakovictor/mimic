"""Worker entrypoint.

Run with:
    PYTHONPATH=services/api:. dramatiq services.worker.worker.broker -p 2 -t 4
or
    python -m services.worker.worker
"""
from __future__ import annotations

# Import side effects: register actors
from worker.actors import pipeline  # noqa: F401
from worker.broker import setup

broker = setup()
