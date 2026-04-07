"""Celery tasks for event ingestion from various sources."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.ingestion.ingest_service import upsert_events
from app.ingestion.ticketmaster import TicketmasterAdapter
from app.models.user import User
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_engine = create_async_engine(settings.database_url)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

# Default always-on cities (used even if no users registered)
_DEFAULT_CITIES = {
    "Nashville": (36.1627, -86.7816),
}


async def _get_active_cities() -> dict[str, tuple[float, float]]:
    """Return merged dict of default cities + all user home_cities."""
    cities = dict(_DEFAULT_CITIES)

    async with _session_factory() as db:
        result = await db.execute(
            select(User.home_city).where(User.home_city.isnot(None)).distinct()
        )
        user_cities = result.scalars().all()

    for city in user_cities:
        if city not in cities:
            # Unknown city: use (0, 0) coords — adapters that don't need coords will work fine;
            # geo-based adapters will skip gracefully
            cities[city] = (0.0, 0.0)

    return cities



async def _run_ticketmaster_ingestion():
    adapter = TicketmasterAdapter()
    today = datetime.now(UTC).date()
    date_to = today + timedelta(days=30)
    cities = await _get_active_cities()

    total = 0
    async with _session_factory() as db:
        for city in cities:
            try:
                events = await adapter.fetch_events(city, today, date_to)
                count = await upsert_events(db, events)
                total += count
            except Exception as e:
                logger.error(f"[ticketmaster] {city} failed: {e}")
    return total



# --- Celery Tasks ---


@celery_app.task(name="worker.tasks.ingestion.ingest_ticketmaster")
def ingest_ticketmaster():
    """Ingest events from Ticketmaster API."""
    if not settings.ticketmaster_api_key:
        return "Skipped: No Ticketmaster API key configured"
    count = asyncio.run(_run_ticketmaster_ingestion())
    return f"Ingested {count} events from Ticketmaster"


@celery_app.task(name="worker.tasks.ingestion.ingest_meetup")
def ingest_meetup():
    """Meetup public API is defunct — disabled."""
    return "Skipped: Meetup public API shut down in 2023"


@celery_app.task(name="worker.tasks.ingestion.ingest_eventbrite")
def ingest_eventbrite():
    """Eventbrite location search API removed in 2020 — disabled."""
    return "Skipped: Eventbrite location search API permanently removed"


@celery_app.task(name="worker.tasks.ingestion.ingest_bandsintown")
def ingest_bandsintown():
    """Bandsintown location API requires partnership key — disabled."""
    return "Skipped: Bandsintown location search requires partnership key"


@celery_app.task(name="worker.tasks.ingestion.ingest_seatgeek")
def ingest_seatgeek():
    """SeatGeek public API program shut down — disabled."""
    return "Skipped: SeatGeek public API program shut down"


async def _run_ingest_city_now(city: str) -> int:
    """Async implementation of on-demand city ingestion (extracted for testability)."""
    lat, lon = _DEFAULT_CITIES.get(city, (0.0, 0.0))

    today = datetime.now(UTC).date()
    date_to = today + timedelta(days=30)
    total = 0

    # Ticketmaster
    if settings.ticketmaster_api_key:
        try:
            async with _session_factory() as db:
                adapter = TicketmasterAdapter()
                events = await adapter.fetch_events(city, today, date_to)
                total += await upsert_events(db, events)
                logger.info(f"[ingest_city_now][ticketmaster] {city}: {len(events)} events")
        except Exception as e:
            logger.error(f"[ingest_city_now][ticketmaster] {city} failed: {e}")

    return total


@celery_app.task(name="worker.tasks.ingestion.ingest_city_now")
def ingest_city_now(city: str):
    """On-demand ingestion for a single city across all adapters."""
    count = asyncio.run(_run_ingest_city_now(city))
    logger.info(f"[ingest_city_now] {city}: {count} total events ingested")
    return f"Ingested {count} events for {city}"

