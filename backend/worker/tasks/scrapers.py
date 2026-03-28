"""Celery tasks for venue scraping."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.ingestion.ingest_service import upsert_events
from app.ingestion.scrapers.generic_jsonld import VENUE_SCRAPERS
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_engine = create_async_engine(settings.database_url)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _run_venue_scraping():
    """Scrape all configured venue websites."""
    total = 0

    async with _session_factory() as db:
        for name, factory in VENUE_SCRAPERS.items():
            try:
                scraper = factory()
                events = await scraper.fetch_events()
                if events:
                    count = await upsert_events(db, events)
                    total += count
                    logger.info(f"[scraper:{name}] Ingested {count} events")
            except Exception as e:
                logger.error(f"[scraper:{name}] Failed: {e}")

    return total


@celery_app.task(name="worker.tasks.scrapers.scrape_venues")
def scrape_venues():
    """Scrape events from configured venue websites."""
    count = asyncio.run(_run_venue_scraping())
    return f"Scraped {count} events from venue websites"
