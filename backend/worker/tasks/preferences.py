"""Celery tasks for preference recomputation."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.services.preference_learning import recompute_all_user_preferences
from worker.celery_app import celery_app

_engine = create_async_engine(settings.database_url)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _run_recomputation():
    async with _session_factory() as db:
        return await recompute_all_user_preferences(db)


@celery_app.task(name="worker.tasks.preferences.recompute_preferences")
def recompute_preferences():
    """Recompute preference weights for all users using time-decayed interactions."""
    count = asyncio.run(_run_recomputation())
    return f"Recomputed preferences for {count} users"
