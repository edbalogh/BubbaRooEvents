"""Celery tasks for event ingestion from various sources."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.ingestion.bandsintown import BandsintownAdapter
from app.ingestion.eventbrite import EventbriteAdapter
from app.ingestion.ingest_service import upsert_events
from app.ingestion.meetup import MeetupAdapter
from app.ingestion.seatgeek import SeatGeekAdapter
from app.ingestion.ticketmaster import TicketmasterAdapter
from app.models.user import User
from worker.celery_app import celery_app
import redis as redis_lib

logger = logging.getLogger(__name__)

_engine = create_async_engine(settings.database_url)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

# Default always-on cities (used even if no users registered)
_DEFAULT_CITIES = {
    "Austin": (30.2672, -97.7431),
    "Nashville": (36.1627, -86.7816),
}

# Redis client for rate-limiting on-demand ingestion
_redis = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)


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


async def _run_adapter_ingestion(adapter, adapter_name: str):
    """Generic ingestion runner for any adapter."""
    today = datetime.now(UTC).date()
    date_to = today + timedelta(days=30)

    total = 0
    active_cities = await _get_active_cities()
    async with _session_factory() as db:
        for city, (lat, lon) in active_cities.items():
            try:
                events = await adapter.fetch_events(
                    city, today, date_to, lat=lat, lon=lon,
                )
                count = await upsert_events(db, events)
                total += count
                logger.info(f"[{adapter_name}] {city}: {count} events")
            except Exception as e:
                logger.error(f"[{adapter_name}] {city} failed: {e}")
    return total


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


async def _run_meetup_ingestion():
    adapter = MeetupAdapter()
    return await _run_adapter_ingestion(adapter, "meetup")


async def _run_eventbrite_ingestion():
    adapter = EventbriteAdapter()
    return await _run_adapter_ingestion(adapter, "eventbrite")


async def _run_bandsintown_ingestion():
    adapter = BandsintownAdapter()
    return await _run_adapter_ingestion(adapter, "bandsintown")


async def _run_seatgeek_ingestion():
    adapter = SeatGeekAdapter()
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
                logger.error(f"[seatgeek] {city} failed: {e}")
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
    """Ingest events from Meetup.com (community events, tech meetups, etc.)."""
    count = asyncio.run(_run_meetup_ingestion())
    return f"Ingested {count} events from Meetup"


@celery_app.task(name="worker.tasks.ingestion.ingest_eventbrite")
def ingest_eventbrite():
    """Ingest events from Eventbrite (workshops, classes, conferences, etc.)."""
    count = asyncio.run(_run_eventbrite_ingestion())
    return f"Ingested {count} events from Eventbrite"


@celery_app.task(name="worker.tasks.ingestion.ingest_bandsintown")
def ingest_bandsintown():
    """Ingest concert/live music events from Bandsintown."""
    count = asyncio.run(_run_bandsintown_ingestion())
    return f"Ingested {count} events from Bandsintown"


@celery_app.task(name="worker.tasks.ingestion.ingest_seatgeek")
def ingest_seatgeek():
    """Ingest events from SeatGeek API (concerts, sports, theatre)."""
    if not settings.seatgeek_client_id:
        return "Skipped: No SeatGeek client_id configured"
    count = asyncio.run(_run_seatgeek_ingestion())
    return f"Ingested {count} events from SeatGeek"


async def _run_ingest_city_now(city: str) -> int:
    """Async implementation of on-demand city ingestion (extracted for testability)."""
    rate_key = f"ingest:city:{city}:last_queued"
    if _redis.get(rate_key):
        logger.info(f"[ingest_city_now] {city}: skipped (rate-limited)")
        return 0
    _redis.setex(rate_key, 600, "1")

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

    # SeatGeek
    if settings.seatgeek_client_id:
        try:
            async with _session_factory() as db:
                adapter = SeatGeekAdapter()
                events = await adapter.fetch_events(city, today, date_to)
                total += await upsert_events(db, events)
                logger.info(f"[ingest_city_now][seatgeek] {city}: {len(events)} events")
        except Exception as e:
            logger.error(f"[ingest_city_now][seatgeek] {city} failed: {e}")

    # Bandsintown
    try:
        async with _session_factory() as db:
            adapter = BandsintownAdapter()
            events = await adapter.fetch_events(city, today, date_to, lat=0, lon=0)
            total += await upsert_events(db, events)
            logger.info(f"[ingest_city_now][bandsintown] {city}: {len(events)} events")
    except Exception as e:
        logger.error(f"[ingest_city_now][bandsintown] {city} failed: {e}")

    # Eventbrite
    try:
        async with _session_factory() as db:
            adapter = EventbriteAdapter()
            events = await adapter.fetch_events(city, today, date_to, lat=0, lon=0)
            total += await upsert_events(db, events)
            logger.info(f"[ingest_city_now][eventbrite] {city}: {len(events)} events")
    except Exception as e:
        logger.error(f"[ingest_city_now][eventbrite] {city} failed: {e}")

    # Meetup
    try:
        async with _session_factory() as db:
            adapter = MeetupAdapter()
            events = await adapter.fetch_events(city, today, date_to, lat=0, lon=0)
            total += await upsert_events(db, events)
            logger.info(f"[ingest_city_now][meetup] {city}: {len(events)} events")
    except Exception as e:
        logger.error(f"[ingest_city_now][meetup] {city} failed: {e}")

    return total


@celery_app.task(name="worker.tasks.ingestion.ingest_city_now")
def ingest_city_now(city: str):
    """On-demand ingestion for a single city across all adapters."""
    count = asyncio.run(_run_ingest_city_now(city))
    logger.info(f"[ingest_city_now] {city}: {count} total events ingested")
    return f"Ingested {count} events for {city}"

