# Local Source Discovery: Phase 2 — Discovery & Scraping Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement automated weekly source discovery (DuckDuckGo + Gemma 4 scoring) and daily per-source event scraping (Crawl4AI + Gemma 4 extraction) as Celery tasks.

**Architecture:** Two new Celery tasks live in `worker/tasks/discovery.py`. LLM tool logic lives in `app/services/discovery_service.py` (pure async functions, easily testable). Crawl4AI handles fetching + markdown conversion. DuckDuckGo search finds candidate source URLs. Gemma 4 via the existing `OllamaProvider` scores candidates and extracts events from markdown. The existing `generic_jsonld.py` scraper remains as a fast path.

**Tech Stack:** Crawl4AI, duckduckgo-search, thefuzz, python-levenshtein, Celery, Ollama/Gemma 4, pytest, respx (HTTP mocking)

**Prerequisite:** Phase 1 (data model) must be complete.

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `backend/pyproject.toml` | Add crawl4ai, duckduckgo-search, thefuzz, python-levenshtein |
| Create | `backend/app/services/discovery_service.py` | LLM tools: score_sources, confirm_source, extract_events_from_markdown |
| Create | `backend/app/ingestion/crawler.py` | Crawl4AI wrapper: fetch_page_markdown(url) → str |
| Create | `backend/worker/tasks/discovery.py` | Celery tasks: discover_sources, scrape_source |
| Modify | `backend/worker/celery_app.py` | Register new tasks in beat schedule |
| Modify | `backend/app/core/config.py` | Add crawl4ai / discovery config settings |
| Create | `backend/tests/services/test_discovery_service.py` | Tests for LLM tool functions (mocked Ollama) |
| Create | `backend/tests/ingestion/test_crawler.py` | Tests for crawler wrapper (mocked HTTP) |

---

### Task 1: Add dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add new dependencies**

In `backend/pyproject.toml`, add to the `dependencies` list:

```toml
"crawl4ai>=0.4",
"duckduckgo-search>=6.0",
"thefuzz>=0.22",
"python-levenshtein>=0.25",
```

- [ ] **Step 2: Install in the container**

```bash
docker compose -f /Users/edbalogh/LiveProjects/BubbaRooEvents/docker-compose.yml build worker api
docker compose -f /Users/edbalogh/LiveProjects/BubbaRooEvents/docker-compose.yml up -d worker api
```

- [ ] **Step 3: Verify imports work**

```bash
docker exec bubbarooevents-api-1 python -c "import crawl4ai; import duckduckgo_search; from thefuzz import fuzz; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore: add crawl4ai, duckduckgo-search, thefuzz dependencies"
```

---

### Task 2: Add config settings for discovery

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Add settings**

In `backend/app/core/config.py`, add to the `Settings` class after the Ollama settings:

```python
# Discovery & scraping
discovery_search_model: str = "gemma4:26b"
discovery_extract_model: str = "gemma4:26b"
discovery_source_score_threshold: float = 0.7
discovery_dedup_confidence_threshold: float = 0.8
crawl4ai_timeout: int = 30
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/core/config.py
git commit -m "chore: add discovery and scraping config settings"
```

---

### Task 3: Create Crawl4AI wrapper

**Files:**
- Create: `backend/app/ingestion/crawler.py`
- Create: `backend/tests/ingestion/__init__.py`
- Create: `backend/tests/ingestion/test_crawler.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ingestion/__init__.py` (empty).

Create `backend/tests/ingestion/test_crawler.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.ingestion.crawler import fetch_page_markdown


@pytest.mark.asyncio
async def test_fetch_page_markdown_returns_string():
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.markdown = "# Test Page\n\nSome events here"

    mock_crawler = AsyncMock()
    mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler.__aexit__ = AsyncMock(return_value=False)
    mock_crawler.arun = AsyncMock(return_value=mock_result)

    with patch("app.ingestion.crawler.AsyncWebCrawler", return_value=mock_crawler):
        result = await fetch_page_markdown("https://example.com/events")

    assert isinstance(result, str)
    assert "Test Page" in result


@pytest.mark.asyncio
async def test_fetch_page_markdown_returns_empty_on_failure():
    mock_result = MagicMock()
    mock_result.success = False
    mock_result.markdown = None

    mock_crawler = AsyncMock()
    mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler.__aexit__ = AsyncMock(return_value=False)
    mock_crawler.arun = AsyncMock(return_value=mock_result)

    with patch("app.ingestion.crawler.AsyncWebCrawler", return_value=mock_crawler):
        result = await fetch_page_markdown("https://example.com/broken")

    assert result == ""
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/ingestion/test_crawler.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.ingestion.crawler'`

- [ ] **Step 3: Implement the crawler wrapper**

Create `backend/app/ingestion/crawler.py`:

```python
"""Crawl4AI wrapper for fetching page content as clean markdown."""

from __future__ import annotations

import logging

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

from app.core.config import settings

logger = logging.getLogger(__name__)


async def fetch_page_markdown(url: str) -> str:
    """Fetch a URL and return its content as clean markdown. Returns empty string on failure."""
    config = CrawlerRunConfig(
        page_timeout=settings.crawl4ai_timeout * 1000,  # ms
        word_count_threshold=10,
        remove_overlay_elements=True,
    )
    try:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url, config=config)
            if result.success and result.markdown:
                return result.markdown
            logger.warning(f"[crawler] Failed to fetch {url}: success={result.success}")
            return ""
    except Exception as e:
        logger.error(f"[crawler] Error fetching {url}: {e}")
        return ""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/ingestion/test_crawler.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingestion/crawler.py backend/tests/ingestion/
git commit -m "feat: add Crawl4AI wrapper for fetching page markdown"
```

---

### Task 4: Implement LLM discovery tools

**Files:**
- Create: `backend/app/services/discovery_service.py`
- Create: `backend/tests/services/test_discovery_service.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/services/test_discovery_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.services.discovery_service import (
    score_source_candidates,
    confirm_source,
    extract_events_from_markdown,
)


@pytest.mark.asyncio
async def test_score_source_candidates_filters_by_threshold():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value='''[
        {"url": "https://nashvillearts.com/events", "score": 0.9, "reason": "local arts calendar"},
        {"url": "https://ticketmaster.com", "score": 0.1, "reason": "national reseller"}
    ]''')

    results = await score_source_candidates(
        mock_llm,
        city="Nashville",
        candidates=[
            {"url": "https://nashvillearts.com/events", "snippet": "Nashville arts events"},
            {"url": "https://ticketmaster.com", "snippet": "Buy tickets"},
        ],
        threshold=0.7,
    )

    assert len(results) == 1
    assert results[0]["url"] == "https://nashvillearts.com/events"
    assert results[0]["score"] == 0.9


@pytest.mark.asyncio
async def test_score_source_candidates_handles_malformed_json():
    mock_llm = AsyncMock()
    # First call returns bad JSON, second returns valid
    mock_llm.complete = AsyncMock(side_effect=[
        "Sorry I can't do that",
        '[{"url": "https://example.com", "score": 0.8, "reason": "ok"}]',
    ])

    results = await score_source_candidates(
        mock_llm,
        city="Nashville",
        candidates=[{"url": "https://example.com", "snippet": "events"}],
        threshold=0.7,
    )
    assert len(results) == 1


@pytest.mark.asyncio
async def test_confirm_source_returns_true_for_event_site():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value='''
        {"is_event_site": true, "site_name": "Nashville Arts", "event_count_estimate": 25, "city": "Nashville"}
    ''')

    result = await confirm_source(mock_llm, markdown="# Upcoming Events\n- Concert on May 1...")
    assert result["is_event_site"] is True
    assert result["site_name"] == "Nashville Arts"


@pytest.mark.asyncio
async def test_confirm_source_returns_false_for_non_event_site():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value='''
        {"is_event_site": false, "site_name": "Random Blog", "event_count_estimate": 0, "city": null}
    ''')

    result = await confirm_source(mock_llm, markdown="# My Blog\nToday I ate a sandwich")
    assert result["is_event_site"] is False


@pytest.mark.asyncio
async def test_extract_events_from_markdown_returns_list():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value='''[
        {"title": "Jazz Night", "date": "2026-05-01", "time": "20:00",
         "venue": "Bluebird Cafe", "address": "4104 Hillsboro Pike",
         "price": "$15", "url": "https://example.com/jazz", "description": "Live jazz"},
        {"title": "Art Walk", "date": "2026-05-03", "time": "18:00",
         "venue": "5th Ave Gallery", "address": null,
         "price": "free", "url": null, "description": null}
    ]''')

    events = await extract_events_from_markdown(
        mock_llm, markdown="# May Events\n...", source_url="https://example.com"
    )

    assert len(events) == 2
    assert events[0]["title"] == "Jazz Night"
    assert events[1]["price"] == "free"


@pytest.mark.asyncio
async def test_extract_events_returns_empty_on_failure():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value="I cannot find any events")

    events = await extract_events_from_markdown(
        mock_llm, markdown="# Page with no events", source_url="https://example.com"
    )
    assert events == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/services/test_discovery_service.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.discovery_service'`

- [ ] **Step 3: Implement discovery_service.py**

Create `backend/app/services/discovery_service.py`:

```python
"""LLM-powered tools for source discovery and event extraction."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from app.services.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

_SCORE_SYSTEM = (
    "You are evaluating URLs to find local event calendars. "
    "Score each URL 0.0-1.0 on how likely it is to be a city-specific event calendar. "
    "Penalize: national ticket resellers (Ticketmaster, StubHub, Vivid Seats), social media, "
    "news sites without event sections. "
    "Reward: city/neighborhood event listings, local venue calendars, "
    "arts council sites, parks & rec calendars, local newspapers with events sections."
)

_CONFIRM_SYSTEM = (
    "You analyze web page content to determine if it is a local event listing site."
)

_EXTRACT_SYSTEM = (
    "You extract structured event data from web page content. "
    "Return only events you are confident about. Do not invent data."
)


def _parse_json_with_retry(raw: str, retry_prompt: str, llm: LLMProvider | None = None) -> list | dict | None:
    """Try to parse JSON from LLM output. Returns None if unparseable."""
    raw = raw.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def score_source_candidates(
    llm: LLMProvider,
    city: str,
    candidates: list[dict],
    threshold: float = 0.7,
) -> list[dict]:
    """
    Score a list of {url, snippet} candidates for likelihood of being a local event calendar.
    Returns candidates with score >= threshold.
    """
    if not candidates:
        return []

    candidate_text = "\n".join(
        f"- URL: {c['url']}\n  Snippet: {c.get('snippet', '')}" for c in candidates
    )
    user_prompt = (
        f"Score these URLs for {city}. "
        f"Return ONLY a JSON array: "
        f'[{{"url": "...", "score": 0.0, "reason": "..."}}]\n\n{candidate_text}'
    )

    raw = await llm.complete(_SCORE_SYSTEM, user_prompt, max_tokens=1000)
    parsed = _parse_json_with_retry(raw, user_prompt)

    if parsed is None:
        # Retry with stricter prompt
        strict_prompt = user_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON array. No explanation."
        raw = await llm.complete(_SCORE_SYSTEM, strict_prompt, max_tokens=1000)
        parsed = _parse_json_with_retry(raw, strict_prompt)

    if not isinstance(parsed, list):
        logger.warning(f"[discovery] score_source_candidates: could not parse LLM response for {city}")
        return []

    return [item for item in parsed if isinstance(item, dict) and item.get("score", 0) >= threshold]


async def confirm_source(llm: LLMProvider, markdown: str) -> dict:
    """
    Confirm whether a page is a local event site.
    Returns dict with keys: is_event_site, site_name, event_count_estimate, city.
    """
    user_prompt = (
        "Does this page list local events with dates and times? "
        'Return ONLY JSON: {"is_event_site": bool, "site_name": "str", '
        '"event_count_estimate": int, "city": "str"}\n\n'
        f"Page content (first 3000 chars):\n{markdown[:3000]}"
    )

    raw = await llm.complete(_CONFIRM_SYSTEM, user_prompt, max_tokens=200)
    parsed = _parse_json_with_retry(raw, user_prompt)

    if not isinstance(parsed, dict):
        strict_prompt = user_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON object. No explanation."
        raw = await llm.complete(_CONFIRM_SYSTEM, strict_prompt, max_tokens=200)
        parsed = _parse_json_with_retry(raw, strict_prompt)

    if not isinstance(parsed, dict):
        logger.warning("[discovery] confirm_source: could not parse LLM response")
        return {"is_event_site": False, "site_name": "", "event_count_estimate": 0, "city": None}

    return parsed


async def extract_events_from_markdown(
    llm: LLMProvider,
    markdown: str,
    source_url: str,
) -> list[dict]:
    """
    Extract events from page markdown. Returns list of raw event dicts.
    Each dict has: title, date, time, venue, address, price, url, description.
    """
    user_prompt = (
        "Extract all events from this page. "
        "Return ONLY a JSON array: "
        '[{"title": "str", "date": "YYYY-MM-DD", "time": "HH:MM", '
        '"venue": "str", "address": "str", "price": "str", '
        '"url": "str", "description": "str"}]. '
        "Use null for missing fields. Only include events with at least a title and date.\n\n"
        f"Source URL: {source_url}\n\n"
        f"Page content (first 6000 chars):\n{markdown[:6000]}"
    )

    raw = await llm.complete(_EXTRACT_SYSTEM, user_prompt, max_tokens=2000)
    parsed = _parse_json_with_retry(raw, user_prompt)

    if parsed is None:
        strict_prompt = user_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON array. No explanation."
        raw = await llm.complete(_EXTRACT_SYSTEM, strict_prompt, max_tokens=2000)
        parsed = _parse_json_with_retry(raw, strict_prompt)

    if not isinstance(parsed, list):
        logger.warning(f"[discovery] extract_events: could not parse LLM response for {source_url}")
        return []

    return [item for item in parsed if isinstance(item, dict) and item.get("title") and item.get("date")]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/services/test_discovery_service.py -v
```

Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/discovery_service.py backend/tests/services/test_discovery_service.py
git commit -m "feat: add LLM discovery tools (score_source_candidates, confirm_source, extract_events_from_markdown)"
```

---

### Task 5: Implement source discovery Celery task

**Files:**
- Create: `backend/worker/tasks/discovery.py`

- [ ] **Step 1: Create the discovery task**

Create `backend/worker/tasks/discovery.py`:

```python
"""Celery tasks for automated source discovery and event scraping."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from duckduckgo_search import DDGS
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.ingestion.base import NormalizedEvent
from app.ingestion.crawler import fetch_page_markdown
from app.ingestion.ingest_service import upsert_events
from app.ingestion.scrapers.generic_jsonld import GenericJsonLdScraper
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

# National sites to always exclude
_BLOCKLIST = {
    "ticketmaster.com", "stubhub.com", "vividseats.com", "seatgeek.com",
    "eventbrite.com", "facebook.com", "instagram.com", "twitter.com",
    "yelp.com", "tripadvisor.com", "bandsintown.com", "songkick.com",
}


def _is_blocklisted(url: str) -> bool:
    return any(blocked in url.lower() for blocked in _BLOCKLIST)


async def _get_active_cities() -> list[str]:
    cities = {"Nashville"}
    async with _session_factory() as db:
        result = await db.execute(
            select(User.home_city).where(User.home_city.isnot(None)).distinct()
        )
        cities.update(result.scalars().all())
    return list(cities)


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
        seen = set()
        unique_candidates = []
        for c in candidates:
            if c["url"] not in seen:
                seen.add(c["url"])
                unique_candidates.append(c)

        if not unique_candidates:
            continue

        # Score candidates
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
                slug = site_name.lower().replace(" ", "-").replace("/", "-")[:50]

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
                    ).on_conflict_do_nothing(index_elements=["slug"])
                    await db.execute(stmt)
                    await db.commit()

                known_urls.add(url.lower())
                new_sources += 1
                logger.info(f"[discovery] Added new source: {site_name} ({url}) for {city}")

                # Immediately queue a scrape for the new source
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
    markdown = await fetch_page_markdown(source.url)
    if not markdown:
        await _mark_source_error(source_slug, "Empty page returned")
        return 0

    # Fast path: try JSON-LD first
    events: list[NormalizedEvent] = []
    try:
        scraper = GenericJsonLdScraper(source_name=source_slug, url=source.url)
        jsonld_events = await scraper.scrape()
        if jsonld_events:
            events = jsonld_events
            logger.info(f"[scraper] {source_slug}: {len(events)} events via JSON-LD fast path")
    except Exception as e:
        logger.debug(f"[scraper] JSON-LD fast path failed for {source_slug}: {e}")

    # Slow path: LLM extraction
    if not events:
        raw_events = await extract_events_from_markdown(llm, markdown, source.url)
        events = [_normalize_extracted_event(e, source_slug) for e in raw_events if e]
        events = [e for e in events if e is not None]
        logger.info(f"[scraper] {source_slug}: {len(events)} events via LLM extraction")

    if events:
        async with _session_factory() as db:
            count = await upsert_events(db, events)

    await _update_source_scraped_at(source_slug)
    return len(events)


def _normalize_extracted_event(raw: dict, source_slug: str) -> NormalizedEvent | None:
    """Convert LLM-extracted event dict to NormalizedEvent."""
    from datetime import datetime as dt
    try:
        date_str = raw.get("date", "")
        time_str = raw.get("time") or "00:00"
        starts_at = dt.fromisoformat(f"{date_str}T{time_str}")

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
            city=None,  # Will be resolved during dedup
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
    from sqlalchemy import update
    async with _session_factory() as db:
        await db.execute(
            update(EventSource)
            .where(EventSource.slug == slug)
            .values(last_scraped_at=datetime.now(UTC), scrape_status="active")
        )
        await db.commit()


async def _mark_source_error(slug: str, reason: str) -> None:
    from sqlalchemy import update
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
    """Daily: scrape all active discovered/local sources."""
    import asyncio as _asyncio

    async def _run_all():
        async with _session_factory() as db:
            result = await db.execute(
                select(EventSource.slug).where(
                    EventSource.scrape_status == "active",
                    EventSource.source_type.in_(["discovered", "scraper"]),
                )
            )
            slugs = result.scalars().all()

        total = 0
        for slug in slugs:
            try:
                count = await _run_scrape_source(slug)
                total += count
            except Exception as e:
                logger.error(f"[scrape_all] {slug} failed: {e}")
        return total

    total = _asyncio.run(_run_all())
    return f"Scraped {total} total events across all sources"
```

- [ ] **Step 2: Commit**

```bash
git add backend/worker/tasks/discovery.py
git commit -m "feat: add discover_sources and scrape_source Celery tasks"
```

---

### Task 6: Register tasks in Celery Beat schedule

**Files:**
- Modify: `backend/worker/celery_app.py`

- [ ] **Step 1: Read the current beat schedule**

Open `backend/worker/celery_app.py` and find the `beat_schedule` dict.

- [ ] **Step 2: Add new tasks to beat schedule**

Add these entries to the `beat_schedule` dict:

```python
"discover-sources-weekly": {
    "task": "worker.tasks.discovery.discover_sources",
    "schedule": crontab(hour=2, minute=0, day_of_week=0),  # Sunday 2am
},
"scrape-all-sources-daily": {
    "task": "worker.tasks.discovery.scrape_all_sources",
    "schedule": crontab(hour=3, minute=0),  # Daily 3am
},
```

Make sure `crontab` is imported at the top — check for `from celery.schedules import crontab` and add it if missing.

- [ ] **Step 3: Restart worker and beat**

```bash
docker compose -f /Users/edbalogh/LiveProjects/BubbaRooEvents/docker-compose.yml up -d --force-recreate worker beat
sleep 8
docker logs bubbarooevents-beat-1 --tail=10
```

Expected: beat starts cleanly, no import errors, new tasks appear in schedule.

- [ ] **Step 4: Smoke test scrape_all_sources task**

```bash
docker exec bubbarooevents-worker-1 celery -A worker.celery_app call worker.tasks.discovery.scrape_all_sources
sleep 10
docker logs bubbarooevents-worker-1 --tail=10
```

Expected: task succeeds (possibly "Scraped 0 total events" if no discovered sources yet — that's fine).

- [ ] **Step 5: Commit**

```bash
git add backend/worker/celery_app.py
git commit -m "feat: register discover_sources and scrape_all_sources in Celery beat schedule"
```

---

### Task 7: Add on-demand refresh API endpoint

**Files:**
- Modify: `backend/app/api/v1/sources.py`

- [ ] **Step 1: Read the current sources.py**

Open `backend/app/api/v1/sources.py` and note the existing endpoints.

- [ ] **Step 2: Add refresh and discovery endpoints**

Add these endpoints to `backend/app/api/v1/sources.py`:

```python
from worker.tasks.discovery import discover_sources, scrape_source

@router.post("/{slug}/refresh")
async def refresh_source(slug: str, db: AsyncSession = Depends(get_db)):
    """Trigger immediate scrape of a specific source. Returns task ID for polling."""
    result = await db.execute(select(EventSource).where(EventSource.slug == slug))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail=f"Source '{slug}' not found")
    task = scrape_source.delay(slug)
    return {"job_id": task.id, "status": "queued", "source": slug}


@router.get("/{slug}/refresh/{job_id}")
async def get_refresh_status(slug: str, job_id: str):
    """Poll scrape job status."""
    from celery.result import AsyncResult
    from worker.celery_app import celery_app as _celery
    result = AsyncResult(job_id, app=_celery)
    return {
        "job_id": job_id,
        "status": result.status,
        "result": str(result.result) if result.ready() else None,
    }


@router.post("/discovery/run")
async def run_discovery():
    """Trigger source discovery now (admin use)."""
    task = discover_sources.delay()
    return {"job_id": task.id, "status": "queued"}


@router.get("/discovery/status")
async def discovery_status(db: AsyncSession = Depends(get_db)):
    """Last discovery run info."""
    result = await db.execute(
        select(func.max(EventSource.last_discovery_at)).where(
            EventSource.discovered_by == "llm_discovery"
        )
    )
    last_run = result.scalar_one_or_none()
    count_result = await db.execute(
        select(func.count()).where(EventSource.discovered_by == "llm_discovery")
    )
    total_discovered = count_result.scalar_one()
    return {"last_discovery_at": last_run, "total_discovered_sources": total_discovered}
```

- [ ] **Step 3: Verify API starts cleanly**

```bash
docker compose -f /Users/edbalogh/LiveProjects/BubbaRooEvents/docker-compose.yml up -d --force-recreate api
sleep 5
docker logs bubbarooevents-api-1 --tail=5
```

Expected: no import errors.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/sources.py
git commit -m "feat: add source refresh and discovery trigger API endpoints"
```
