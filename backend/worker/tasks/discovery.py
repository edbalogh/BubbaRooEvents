"""Celery tasks for automated source discovery and event scraping."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx
from duckduckgo_search import DDGS
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.ingestion.base import NormalizedEvent
from app.ingestion.crawler import fetch_page_markdown
from app.ingestion.ingest_service import upsert_events
from app.models.source import EventSource
from app.models.user import User
from app.services.discovery_service import (
    confirm_source,
    extract_events_from_markdown,
    score_source_candidates,
)
from app.services.llm_provider import OllamaProvider
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_engine = create_async_engine(settings.database_url)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

_DISCOVERY_QUERIES = [
    "{city} events calendar",
    "{city} local events this weekend",
    "{city} events listing site",
    "{city} arts events calendar",
    "{city} community events",
]

_BLOCKLIST = {
    "ticketmaster.com", "stubhub.com", "vividseats.com", "seatgeek.com",
    "eventbrite.com", "facebook.com", "instagram.com", "twitter.com",
    "yelp.com", "tripadvisor.com", "bandsintown.com", "songkick.com",
}


def _is_blocklisted(url: str) -> bool:
    return any(blocked in url.lower() for blocked in _BLOCKLIST)


async def _detect_ical_feed(page_url: str) -> str | None:
    """Probe a page's HTML for iCal/ICS feed links. Returns the feed URL or None."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(page_url, headers={"User-Agent": "BubbaRooEvents/1.0"})
            resp.raise_for_status()
            html = resp.text

        # 1. <link rel="alternate" type="text/calendar" href="...">
        import re as _re
        link_match = _re.search(
            r'<link[^>]+type=["\']text/calendar["\'][^>]+href=["\']([^"\']+)["\']',
            html, _re.IGNORECASE
        )
        if not link_match:
            link_match = _re.search(
                r'<link[^>]+href=["\']([^"\']+)["\'][^>]+type=["\']text/calendar["\']',
                html, _re.IGNORECASE
            )
        if link_match:
            return urljoin(page_url, link_match.group(1))

        # 2. Any href ending in .ics
        ics_match = _re.search(r'href=["\']([^"\']+\.ics(?:\?[^"\']*)?)["\']', html, _re.IGNORECASE)
        if ics_match:
            return urljoin(page_url, ics_match.group(1))

        # 3. Common well-known paths — probe /calendar.ics, /events.ics, /feed.ics
        base = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"
        for path in ("/calendar.ics", "/events.ics", "/feed.ics", "/calendar/ical"):
            try:
                probe = await client.head(f"{base}{path}", timeout=5)
                ct = probe.headers.get("content-type", "")
                if probe.status_code == 200 and ("calendar" in ct or path.endswith(".ics")):
                    return f"{base}{path}"
            except Exception:
                pass

    except Exception as e:
        logger.debug(f"[discovery] iCal probe failed for {page_url}: {e}")

    return None


async def _get_active_cities() -> list[str]:
    async with _session_factory() as db:
        result = await db.execute(
            select(User.home_city).where(User.home_city.isnot(None)).distinct()
        )
        return result.scalars().all()


async def _get_known_urls() -> set[str]:
    async with _session_factory() as db:
        result = await db.execute(select(EventSource.url).where(EventSource.url.isnot(None)))
        return {row[0].lower() for row in result.fetchall()}


async def _run_discover_sources() -> int:
    llm = OllamaProvider(base_url=settings.ollama_base_url, model=settings.discovery_search_model)
    cities = await _get_active_cities()
    known_urls = await _get_known_urls()
    new_sources = 0

    for city in cities:
        logger.info(f"[discovery] Searching for sources in {city}")
        candidates: list[dict] = []

        with DDGS() as ddgs:
            for query_template in _DISCOVERY_QUERIES:
                query = query_template.format(city=city)
                try:
                    results = list(ddgs.text(query, max_results=5))
                    for r in results:
                        url = r.get("href", "")
                        if url and not _is_blocklisted(url) and url.lower() not in known_urls:
                            candidates.append({"url": url, "snippet": r.get("body", "")})
                except Exception as e:
                    logger.warning(f"[discovery] DDG search failed for '{query}': {e}")

        # Deduplicate candidates
        seen: set[str] = set()
        unique_candidates = []
        for c in candidates:
            if c["url"] not in seen:
                seen.add(c["url"])
                unique_candidates.append(c)

        if not unique_candidates:
            continue

        scored = await score_source_candidates(
            llm, city, unique_candidates, threshold=settings.discovery_source_score_threshold
        )
        logger.info(f"[discovery] {city}: {len(scored)}/{len(unique_candidates)} candidates passed scoring")

        for candidate in scored:
            url = candidate["url"]
            try:
                markdown = await fetch_page_markdown(url)
                if not markdown:
                    continue

                confirmation = await confirm_source(llm, markdown)
                if not confirmation.get("is_event_site"):
                    continue

                site_name = confirmation.get("site_name") or url
                # Sanitize to [a-z0-9-] and append URL hash to prevent slug collisions
                url_hash = hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()[:6]
                slug_base = re.sub(r"[^a-z0-9-]", "-", site_name.lower())[:43].strip("-")
                slug = f"{slug_base}-{url_hash}"

                # Probe for an iCal feed on this site
                ical_url = await _detect_ical_feed(url)
                if ical_url:
                    logger.info(f"[discovery] Found iCal feed for {site_name}: {ical_url}")
                scrape_config = {"ical_url": ical_url} if ical_url else None

                async with _session_factory() as db:
                    stmt = insert(EventSource).values(
                        slug=slug,
                        name=site_name,
                        source_type="discovered",
                        url=url,
                        is_active=True,
                        is_local=True,
                        coverage_cities=city,
                        default_trust_score=candidate["score"],
                        scrape_status="active",
                        discovery_confidence=candidate["score"],
                        discovered_by="llm_discovery",
                        last_discovery_at=datetime.now(UTC),
                        scrape_config=scrape_config,
                    ).on_conflict_do_nothing(index_elements=["slug"])
                    await db.execute(stmt)
                    await db.commit()

                known_urls.add(url.lower())
                new_sources += 1
                logger.info(f"[discovery] Added new source: {site_name} ({url}) for {city}")

                scrape_source.delay(slug)

            except Exception as e:
                logger.error(f"[discovery] Error processing candidate {url}: {e}")

    return new_sources


async def _run_scrape_source(source_slug: str) -> int:
    llm = OllamaProvider(base_url=settings.ollama_base_url, model=settings.discovery_extract_model)

    async with _session_factory() as db:
        result = await db.execute(
            select(EventSource).where(EventSource.slug == source_slug)
        )
        source = result.scalar_one_or_none()

    if not source or not source.url or source.scrape_status != "active":
        logger.warning(f"[scraper] Source not found or inactive: {source_slug}")
        return 0

    logger.info(f"[scraper] Scraping {source_slug} ({source.url})")

    events: list[NormalizedEvent] = []

    # Fast path 1: iCal feed (most reliable — structured, no LLM needed)
    ical_url = (source.scrape_config or {}).get("ical_url")
    if ical_url:
        try:
            from app.ingestion.venue_scraper import ICalScraperBase

            class _DynamicICalScraper(ICalScraperBase):
                source_name = source_slug
                feed_url = ical_url
                default_city = source.coverage_cities or ""

            scraper = _DynamicICalScraper()
            ical_events = await scraper.fetch_events()
            if ical_events:
                events = ical_events
                logger.info(f"[scraper] {source_slug}: {len(events)} events via iCal feed")
        except Exception as e:
            logger.warning(f"[scraper] iCal fast path failed for {source_slug}: {e}")

    # Fast path 2: try JSON-LD structured data via HTML fetch (independent of Crawl4AI)
    if not events:
        try:
            from app.ingestion.scrapers.generic_jsonld import GenericJsonLdScraper
            scraper = GenericJsonLdScraper()
            scraper.source_name = source_slug
            scraper.base_url = source.url
            jsonld_events = await scraper.fetch_events()
            if jsonld_events:
                events = jsonld_events
                logger.info(f"[scraper] {source_slug}: {len(events)} events via JSON-LD fast path")
        except Exception as e:
            logger.debug(f"[scraper] JSON-LD fast path failed for {source_slug}: {e}")

    # Slow path: Crawl4AI markdown fetch + LLM extraction
    if not events:
        markdown = await fetch_page_markdown(source.url)
        if not markdown:
            await _mark_source_error(source_slug, "Empty page returned by Crawl4AI")
            return 0
        raw_events = await extract_events_from_markdown(llm, markdown, source.url)
        events = [_normalize_extracted_event(e, source_slug) for e in raw_events]
        events = [e for e in events if e is not None]
        logger.info(f"[scraper] {source_slug}: {len(events)} events via LLM extraction")

    try:
        if events:
            async with _session_factory() as db:
                await upsert_events(db, events)
    except Exception as e:
        await _mark_source_error(source_slug, f"upsert failed: {e}")
        return 0

    await _update_source_scraped_at(source_slug)
    return len(events)


def _normalize_extracted_event(raw: dict, source_slug: str) -> NormalizedEvent | None:
    """Convert LLM-extracted event dict to NormalizedEvent."""
    try:
        date_str = raw.get("date", "")
        time_str = raw.get("time") or "00:00"
        starts_at = datetime.fromisoformat(f"{date_str}T{time_str}")

        price_str = str(raw.get("price") or "")
        price_min = None
        if price_str.lower() in ("free", "0", "$0"):
            price_min = 0.0
        elif price_str.startswith("$"):
            try:
                price_min = float(price_str.replace("$", "").split("-")[0].strip())
            except ValueError:
                pass

        return NormalizedEvent(
            external_id=f"{source_slug}-{raw['title'][:50]}-{date_str}",
            source=source_slug,
            title=raw["title"],
            description=raw.get("description"),
            venue_name=raw.get("venue"),
            venue_address=raw.get("address"),
            city=None,
            starts_at=starts_at,
            price_min=price_min,
            url=raw.get("url"),
            categories=["local"],
            raw_data=raw,
        )
    except Exception as e:
        logger.warning(f"[scraper] Failed to normalize extracted event: {e} — raw: {raw}")
        return None


async def _update_source_scraped_at(slug: str) -> None:
    async with _session_factory() as db:
        await db.execute(
            update(EventSource)
            .where(EventSource.slug == slug)
            .values(last_scraped_at=datetime.now(UTC), scrape_status="active")
        )
        await db.commit()


async def _mark_source_error(slug: str, reason: str) -> None:
    logger.error(f"[scraper] {slug} error: {reason}")
    async with _session_factory() as db:
        await db.execute(
            update(EventSource)
            .where(EventSource.slug == slug)
            .values(scrape_status="error")
        )
        await db.commit()


# --- Celery Tasks ---

@celery_app.task(name="worker.tasks.discovery.discover_sources")
def discover_sources():
    """Weekly: search web for new local event sources per city."""
    count = asyncio.run(_run_discover_sources())
    return f"Discovery complete: {count} new sources found"


@celery_app.task(name="worker.tasks.discovery.scrape_source")
def scrape_source(source_slug: str):
    """Scrape a single source for events. Can be triggered on-demand."""
    count = asyncio.run(_run_scrape_source(source_slug))
    return f"Scraped {count} events from {source_slug}"


@celery_app.task(name="worker.tasks.discovery.scrape_all_sources")
def scrape_all_sources():
    """Daily: fan-out scrape tasks for all active discovered/local sources.

    Dispatches individual scrape_source tasks rather than running serially,
    so scrapes can execute in parallel across workers and be individually retried.
    API-backed sources (ticketmaster, etc.) are excluded — they have their own tasks.
    """
    async def _get_slugs() -> list[str]:
        async with _session_factory() as db:
            result = await db.execute(
                select(EventSource.slug).where(
                    EventSource.scrape_status == "active",
                    EventSource.is_active == True,
                    EventSource.source_type.in_(["discovered", "scraper"]),
                )
            )
            return result.scalars().all()

    slugs = asyncio.run(_get_slugs())
    for slug in slugs:
        scrape_source.delay(slug)
    logger.info(f"[scrape_all] Dispatched {len(slugs)} scrape tasks")
    return f"Dispatched {len(slugs)} scrape tasks"
