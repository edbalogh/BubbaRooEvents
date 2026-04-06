"""Celery tasks for event ingestion from various sources."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.ingestion.bandsintown import BandsintownAdapter
from app.ingestion.eventbrite import EventbriteAdapter
from app.ingestion.ingest_service import upsert_events
from app.ingestion.meetup import MeetupAdapter
from app.ingestion.seatgeek import SeatGeekAdapter
from app.ingestion.ticketmaster import TicketmasterAdapter
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_engine = create_async_engine(settings.database_url)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

# Cities and their approximate coordinates for geo-based APIs
INGEST_CITIES = {
    "Austin": (30.2672, -97.7431),
    "Nashville": (36.1627, -86.7816),
    "Denver": (39.7392, -104.9903),
    "Portland": (45.5152, -122.6784),
    "Seattle": (47.6062, -122.3321),
}


async def _run_adapter_ingestion(adapter, adapter_name: str):
    """Generic ingestion runner for any adapter."""
    today = datetime.now(UTC).date()
    date_to = today + timedelta(days=30)

    total = 0
    async with _session_factory() as db:
        for city, (lat, lon) in INGEST_CITIES.items():
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

    total = 0
    async with _session_factory() as db:
        for city in INGEST_CITIES:
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

    total = 0
    async with _session_factory() as db:
        for city in INGEST_CITIES:
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

