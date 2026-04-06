"""
Conftest for worker task tests.

worker.tasks.ingestion has module-level side-effects that require a live
database (asyncpg), Redis, and Celery. We stub those out before any test
in this package imports the module.
"""
import sys
from unittest.mock import MagicMock


def pytest_configure(config):
    """Stub heavy dependencies before any test collection imports them."""
    # Stub asyncpg so SQLAlchemy asyncpg dialect doesn't blow up
    sys.modules.setdefault("asyncpg", MagicMock())

    # Stub redis so redis_lib.Redis.from_url doesn't blow up
    redis_stub = MagicMock()
    sys.modules.setdefault("redis", redis_stub)

    # Stub celery so worker.celery_app can be imported without a broker
    sys.modules.setdefault("celery", MagicMock())
    sys.modules.setdefault("celery.app", MagicMock())
    sys.modules.setdefault("celery.schedules", MagicMock())
