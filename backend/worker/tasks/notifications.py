"""Celery tasks for notification dispatch."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.services.notification_service import (
    notify_new_matches,
    notify_ticket_alerts,
    notify_tonight_events,
    send_weekly_digest,
)
from worker.celery_app import celery_app

_engine = create_async_engine(settings.database_url)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _run_tonight():
    async with _session_factory() as db:
        return await notify_tonight_events(db)


async def _run_ticket_alerts():
    async with _session_factory() as db:
        return await notify_ticket_alerts(db)


async def _run_new_matches():
    async with _session_factory() as db:
        return await notify_new_matches(db)


async def _run_weekly_digest():
    async with _session_factory() as db:
        return await send_weekly_digest(db)


@celery_app.task(name="worker.tasks.notifications.send_tonight_notifications")
def send_tonight_notifications():
    """Send 'happening tonight' notifications to all users."""
    count = asyncio.run(_run_tonight())
    return f"Sent tonight notifications to {count} users"


@celery_app.task(name="worker.tasks.notifications.send_ticket_alerts")
def send_ticket_alerts():
    """Send ticket alert notifications for newly on-sale events."""
    count = asyncio.run(_run_ticket_alerts())
    return f"Sent ticket alerts for {count} user-event pairs"


@celery_app.task(name="worker.tasks.notifications.send_new_match_notifications")
def send_new_match_notifications():
    """Send notifications for new high-score event matches."""
    count = asyncio.run(_run_new_matches())
    return f"Sent new match notifications to {count} users"


@celery_app.task(name="worker.tasks.notifications.send_weekly_digest")
def send_weekly_digest_task():
    """Send weekly digest emails to all users."""
    count = asyncio.run(_run_weekly_digest())
    return f"Sent weekly digest to {count} users"
