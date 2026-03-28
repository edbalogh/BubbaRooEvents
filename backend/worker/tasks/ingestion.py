"""Celery tasks for event ingestion from various sources."""

import asyncio
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.ingestion.ingest_service import upsert_events
from app.ingestion.mock_data import generate_mock_events
from app.ingestion.ticketmaster import TicketmasterAdapter
from worker.celery_app import celery_app

# Create a separate engine for celery workers
_engine = create_async_engine(settings.database_url)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

INGEST_CITIES = ["Austin", "Nashville", "Denver", "Portland", "Seattle"]


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
                print(f"Error ingesting Ticketmaster events for {city}: {e}")
    return total


async def _run_mock_ingestion():
    total = 0
    async with _session_factory() as db:
        for city in INGEST_CITIES:
            events = generate_mock_events(city)
            count = await upsert_events(db, events)
            total += count
    return total


@celery_app.task(name="worker.tasks.ingestion.ingest_ticketmaster")
def ingest_ticketmaster():
    """Ingest events from Ticketmaster API."""
    if not settings.ticketmaster_api_key:
        return "Skipped: No Ticketmaster API key configured"
    count = asyncio.run(_run_ticketmaster_ingestion())
    return f"Ingested {count} events from Ticketmaster"


@celery_app.task(name="worker.tasks.ingestion.ingest_mock_events")
def ingest_mock_events():
    """Ingest mock events for development."""
    if not settings.use_mock_data:
        return "Skipped: Mock data disabled"
    count = asyncio.run(_run_mock_ingestion())
    return f"Ingested {count} mock events"
