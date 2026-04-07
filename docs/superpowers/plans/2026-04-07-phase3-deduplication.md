# Local Source Discovery: Phase 3 — Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement venue resolution and cross-source event deduplication: raw events get linked to canonical venues and canonical events, with conflicts stored for UI display.

**Architecture:** A `dedup_service.py` contains pure functions for venue resolution (fuzzy match via thefuzz) and duplicate detection (fuzzy + LLM fallback). A Celery task `dedup_events` runs after each scrape batch and on a schedule. `ingest_service.py` is updated to trigger dedup after upserting. The `CanonicalEvent` merge logic picks best field values by source priority and stores conflicts in JSONB.

**Tech Stack:** thefuzz, python-levenshtein, SQLAlchemy async, Ollama/Gemma 4, pytest

**Prerequisite:** Phase 1 (data model) and Phase 2 (discovery/scraping) must be complete.

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Create | `backend/app/services/dedup_service.py` | Venue resolution, duplicate detection, canonical event merging |
| Create | `backend/worker/tasks/dedup.py` | Celery task: dedup_events |
| Modify | `backend/worker/celery_app.py` | Register dedup task in beat schedule |
| Modify | `backend/app/ingestion/ingest_service.py` | Trigger dedup after upsert |
| Modify | `backend/app/services/event_service.py` | Query canonical_events instead of raw_events |
| Create | `backend/tests/services/test_dedup_service.py` | Tests for dedup logic |

---

### Task 1: Implement venue resolution

**Files:**
- Create: `backend/app/services/dedup_service.py`
- Create: `backend/tests/services/test_dedup_service.py`

- [ ] **Step 1: Write failing tests for venue resolution**

Create `backend/tests/services/test_dedup_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.dedup_service import (
    make_venue_slug,
    fuzzy_match_venue_name,
    merge_canonical_event_fields,
    pick_best_field,
)


def test_make_venue_slug_basic():
    assert make_venue_slug("3rd & Lindsley", "Nashville") == "3rd-lindsley-nashville"


def test_make_venue_slug_normalizes():
    assert make_venue_slug("The Ryman Auditorium", "Nashville") == "the-ryman-auditorium-nashville"


def test_make_venue_slug_truncates():
    long_name = "A" * 400
    slug = make_venue_slug(long_name, "Nashville")
    assert len(slug) <= 350


def test_fuzzy_match_venue_name_exact():
    candidates = [
        {"name": "Bluebird Cafe", "city": "Nashville"},
        {"name": "Ryman Auditorium", "city": "Nashville"},
    ]
    match = fuzzy_match_venue_name("Bluebird Cafe", "Nashville", candidates, threshold=85)
    assert match is not None
    assert match["name"] == "Bluebird Cafe"


def test_fuzzy_match_venue_name_close():
    candidates = [{"name": "3rd and Lindsley", "city": "Nashville"}]
    match = fuzzy_match_venue_name("3rd & Lindsley", "Nashville", candidates, threshold=85)
    assert match is not None


def test_fuzzy_match_venue_name_no_match():
    candidates = [{"name": "Ryman Auditorium", "city": "Nashville"}]
    match = fuzzy_match_venue_name("Completely Different Place", "Nashville", candidates, threshold=85)
    assert match is None


def test_fuzzy_match_venue_name_wrong_city():
    candidates = [{"name": "Bluebird Cafe", "city": "Denver"}]
    match = fuzzy_match_venue_name("Bluebird Cafe", "Nashville", candidates, threshold=85)
    assert match is None


def test_pick_best_field_venue_wins_over_ticketmaster():
    values = [
        {"source": "ticketmaster", "value": 45.0},
        {"source": "nashville-venue-scraper", "value": 40.0},
    ]
    result = pick_best_field("price_min", values)
    assert result == 40.0


def test_pick_best_field_longest_description_wins():
    values = [
        {"source": "ticketmaster", "value": "Short desc"},
        {"source": "nashville-scraper", "value": "A much longer and more detailed description of this event"},
    ]
    result = pick_best_field("description", values)
    assert result == "A much longer and more detailed description of this event"


def test_merge_canonical_event_fields_picks_best():
    raw_events = [
        {
            "source": "ticketmaster",
            "title": "Jazz Night",
            "description": "Short",
            "price_min": 45.0,
            "url": "https://ticketmaster.com/jazz",
            "image_url": "https://tm.com/img.jpg",
            "starts_at": "2026-05-01T20:00:00",
        },
        {
            "source": "bluebird-cafe",
            "title": "Jazz Night at Bluebird",
            "description": "A wonderful evening of jazz featuring local musicians in an intimate setting",
            "price_min": 40.0,
            "url": "https://bluebirdcafe.com/events/jazz",
            "image_url": None,
            "starts_at": "2026-05-01T20:00:00",
        },
    ]
    merged = merge_canonical_event_fields(raw_events)
    # Venue scraper wins on price
    assert merged["price_min"] == 40.0
    # Longer description wins
    assert "intimate" in merged["description"]
    # Venue URL wins
    assert "bluebirdcafe.com" in merged["url"]
    # Conflicts stored
    assert "price_min" in merged["conflicts"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/services/test_dedup_service.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.dedup_service'`

- [ ] **Step 3: Implement dedup_service.py**

Create `backend/app/services/dedup_service.py`:

```python
"""Venue resolution and cross-source event deduplication."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, UTC
from typing import Any

from thefuzz import fuzz

from app.services.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

# Source priority for field selection (lower index = higher priority)
_SOURCE_PRIORITY = [
    "venue",  # any source containing "venue" or "scraper" has priority
    "scraper",
    "ticketmaster",
    "discovered",
]

# Fields where "longest wins" instead of source priority
_LONGEST_WINS_FIELDS = {"description", "title"}


def make_venue_slug(name: str, city: str) -> str:
    """Create a unique slug for a venue from its name and city."""
    combined = f"{name}-{city}".lower()
    combined = re.sub(r"[^a-z0-9\s-]", "", combined)
    combined = re.sub(r"\s+", "-", combined.strip())
    combined = re.sub(r"-+", "-", combined)
    return combined[:350]


def fuzzy_match_venue_name(
    name: str,
    city: str,
    candidates: list[dict],
    threshold: int = 85,
) -> dict | None:
    """
    Find the best matching venue from candidates using fuzzy string matching.
    Only matches within the same city. Returns None if no match above threshold.
    """
    best_score = 0
    best_match = None

    for candidate in candidates:
        if candidate.get("city", "").lower() != city.lower():
            continue
        score = fuzz.token_sort_ratio(name.lower(), candidate["name"].lower())
        if score > best_score and score >= threshold:
            best_score = score
            best_match = candidate

    return best_match


def _source_rank(source: str) -> int:
    """Lower number = higher priority. Unknown sources rank last."""
    source_lower = source.lower()
    for i, keyword in enumerate(_SOURCE_PRIORITY):
        if keyword in source_lower:
            return i
    return len(_SOURCE_PRIORITY)


def pick_best_field(field_name: str, values: list[dict]) -> Any:
    """
    Pick the best value for a field from multiple source values.
    For description/title: pick the longest non-null value.
    For everything else: pick by source priority order.
    """
    non_null = [v for v in values if v.get("value") is not None]
    if not non_null:
        return None

    if field_name in _LONGEST_WINS_FIELDS:
        return max(non_null, key=lambda v: len(str(v["value"])))["value"]

    return min(non_null, key=lambda v: _source_rank(v["source"]))["value"]


def merge_canonical_event_fields(raw_events: list[dict]) -> dict:
    """
    Merge fields from multiple raw event dicts into a single canonical event.
    Returns dict with merged fields plus 'conflicts' and 'field_sources' metadata.
    """
    fields = ["title", "description", "price_min", "price_max", "currency",
              "url", "image_url", "starts_at", "ends_at"]

    merged: dict = {}
    conflicts: dict = {}
    field_sources: dict = {}

    for field in fields:
        values = [
            {"source": e["source"], "value": e.get(field)}
            for e in raw_events
            if e.get(field) is not None
        ]
        if not values:
            merged[field] = None
            continue

        best = pick_best_field(field, values)
        merged[field] = best

        winner_source = next(
            (v["source"] for v in values if v["value"] == best), values[0]["source"]
        )
        field_sources[field] = winner_source

        # Record conflicts (values that differ from the winner)
        differing = [v for v in values if v["value"] != best]
        if differing:
            conflicts[field] = [{"source": winner_source, "value": best}] + [
                {"source": v["source"], "value": v["value"]} for v in differing
            ]

    merged["conflicts"] = conflicts if conflicts else None
    merged["field_sources"] = field_sources if field_sources else None
    return merged


async def are_duplicate_events(
    llm: LLMProvider,
    event_a: dict,
    event_b: dict,
    confidence_threshold: float = 0.8,
) -> bool:
    """
    Use LLM to determine if two events are the same real-world event.
    Used when fuzzy venue match is ambiguous.
    """
    import json

    system = "You determine if two event listings describe the same real-world event."
    user = (
        "Are these two event listings the same real-world event? "
        "Venue names may differ slightly. "
        'Return ONLY JSON: {"is_duplicate": bool, "confidence": 0.0, "reason": "str"}\n\n'
        f"Event A: {json.dumps(event_a)}\n\nEvent B: {json.dumps(event_b)}"
    )

    try:
        raw = await llm.complete(system, user, max_tokens=200)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        import json as _json
        result = _json.loads(raw)
        return (
            result.get("is_duplicate", False) is True
            and result.get("confidence", 0) >= confidence_threshold
        )
    except Exception as e:
        logger.warning(f"[dedup] LLM duplicate check failed: {e}")
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/services/test_dedup_service.py -v
```

Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/dedup_service.py backend/tests/services/test_dedup_service.py
git commit -m "feat: add dedup_service with venue resolution, fuzzy matching, and field merging"
```

---

### Task 2: Implement dedup Celery task

**Files:**
- Create: `backend/worker/tasks/dedup.py`

- [ ] **Step 1: Create the dedup task**

Create `backend/worker/tasks/dedup.py`:

```python
"""Celery task for cross-source event deduplication."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.canonical_event import CanonicalEvent
from app.models.event import RawEvent
from app.models.venue import Venue
from app.services.dedup_service import (
    are_duplicate_events,
    fuzzy_match_venue_name,
    make_venue_slug,
    merge_canonical_event_fields,
)
from app.services.llm_provider import OllamaProvider
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_engine = create_async_engine(settings.database_url)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _resolve_venue(db: AsyncSession, raw: RawEvent) -> uuid.UUID | None:
    """Find or create a venue for a raw event. Returns venue_id or None."""
    if not raw.venue_name or not raw.city:
        return None

    # Load all venues for this city
    result = await db.execute(
        select(Venue).where(Venue.city == raw.city)
    )
    city_venues = [{"id": v.id, "name": v.name, "city": v.city} for v in result.scalars().all()]

    # Try fuzzy match
    match = fuzzy_match_venue_name(raw.venue_name, raw.city, city_venues, threshold=85)
    if match:
        return match["id"]

    # Create new venue
    slug = make_venue_slug(raw.venue_name, raw.city)
    new_venue = Venue(
        id=uuid.uuid4(),
        name=raw.venue_name,
        slug=slug,
        address=raw.venue_address,
        city=raw.city,
        state=raw.state,
        lat=raw.latitude,
        lon=raw.longitude,
        source_slugs=[raw.source],
    )
    try:
        db.add(new_venue)
        await db.flush()
        return new_venue.id
    except Exception:
        await db.rollback()
        # Slug conflict — venue was inserted concurrently; re-query
        result = await db.execute(select(Venue).where(Venue.slug == slug))
        existing = result.scalar_one_or_none()
        return existing.id if existing else None


async def _find_duplicate_candidates(
    db: AsyncSession, raw: RawEvent
) -> list[CanonicalEvent]:
    """Find canonical events that could be duplicates of this raw event."""
    if not raw.starts_at or not raw.city:
        return []

    window_start = raw.starts_at - timedelta(hours=4)
    window_end = raw.starts_at + timedelta(hours=4)

    result = await db.execute(
        select(CanonicalEvent).where(
            CanonicalEvent.starts_at.between(window_start, window_end),
            CanonicalEvent.status == "active",
        )
    )
    return result.scalars().all()


async def _run_dedup_events(limit: int = 500) -> int:
    """Process unlinked raw events: resolve venues, find/create canonical events."""
    llm = OllamaProvider(base_url=settings.ollama_base_url, model=settings.discovery_search_model)
    processed = 0

    async with _session_factory() as db:
        result = await db.execute(
            select(RawEvent)
            .where(RawEvent.canonical_event_id.is_(None))
            .limit(limit)
        )
        unlinked = result.scalars().all()

    for raw in unlinked:
        try:
            async with _session_factory() as db:
                # Resolve venue
                venue_id = await _resolve_venue(db, raw)
                if venue_id:
                    await db.execute(
                        update(RawEvent).where(RawEvent.id == raw.id).values(venue_id=venue_id)
                    )
                    await db.flush()

                # Find duplicate candidates
                candidates = await _find_duplicate_candidates(db, raw)

                canonical_id = None

                for candidate in candidates:
                    # Strong match: same venue_id
                    if venue_id and candidate.venue_id == venue_id:
                        canonical_id = candidate.id
                        break

                    # Weaker match: LLM check
                    event_a = {
                        "title": raw.title,
                        "venue_name": raw.venue_name,
                        "starts_at": str(raw.starts_at),
                        "city": raw.city,
                    }
                    event_b = {
                        "title": candidate.title,
                        "venue_name": None,  # canonical doesn't store raw venue name
                        "starts_at": str(candidate.starts_at),
                        "city": raw.city,
                    }
                    is_dup = await are_duplicate_events(
                        llm, event_a, event_b,
                        confidence_threshold=settings.discovery_dedup_confidence_threshold,
                    )
                    if is_dup:
                        canonical_id = candidate.id
                        break

                if canonical_id:
                    # Link to existing canonical event, refresh its merged fields
                    await db.execute(
                        update(RawEvent)
                        .where(RawEvent.id == raw.id)
                        .values(canonical_event_id=canonical_id)
                    )
                    # Re-merge all raw events for this canonical
                    siblings_result = await db.execute(
                        select(RawEvent).where(RawEvent.canonical_event_id == canonical_id)
                    )
                    all_raws = siblings_result.scalars().all() + [raw]
                    raw_dicts = [_raw_to_dict(r) for r in all_raws]
                    merged = merge_canonical_event_fields(raw_dicts)
                    await db.execute(
                        update(CanonicalEvent)
                        .where(CanonicalEvent.id == canonical_id)
                        .values(
                            description=merged.get("description"),
                            price_min=merged.get("price_min"),
                            price_max=merged.get("price_max"),
                            url=merged.get("url"),
                            image_url=merged.get("image_url"),
                            conflicts=merged.get("conflicts"),
                            field_sources=merged.get("field_sources"),
                            venue_id=venue_id or candidate.venue_id,
                        )
                    )
                else:
                    # Create new canonical event
                    raw_dict = _raw_to_dict(raw)
                    merged = merge_canonical_event_fields([raw_dict])
                    new_canonical = CanonicalEvent(
                        id=uuid.uuid4(),
                        title=merged["title"] or raw.title,
                        description=merged.get("description"),
                        venue_id=venue_id,
                        starts_at=raw.starts_at,
                        ends_at=raw.ends_at,
                        price_min=merged.get("price_min"),
                        price_max=merged.get("price_max"),
                        currency=raw.currency,
                        url=merged.get("url"),
                        image_url=merged.get("image_url"),
                        categories=raw.raw_data.get("categories") if raw.raw_data else None,
                        field_sources=merged.get("field_sources"),
                        conflicts=None,
                        status="active",
                    )
                    db.add(new_canonical)
                    await db.flush()
                    await db.execute(
                        update(RawEvent)
                        .where(RawEvent.id == raw.id)
                        .values(canonical_event_id=new_canonical.id)
                    )

                await db.commit()
                processed += 1

        except Exception as e:
            logger.error(f"[dedup] Failed to process raw_event {raw.id}: {e}")

    return processed


def _raw_to_dict(raw: RawEvent) -> dict:
    return {
        "source": raw.source,
        "title": raw.title,
        "description": raw.description,
        "price_min": float(raw.price_min) if raw.price_min else None,
        "price_max": float(raw.price_max) if raw.price_max else None,
        "currency": raw.currency,
        "url": raw.url,
        "image_url": raw.image_url,
        "starts_at": str(raw.starts_at) if raw.starts_at else None,
        "ends_at": str(raw.ends_at) if raw.ends_at else None,
    }


@celery_app.task(name="worker.tasks.dedup.dedup_events")
def dedup_events(limit: int = 500):
    """Process unlinked raw events: resolve venues and create/link canonical events."""
    count = asyncio.run(_run_dedup_events(limit=limit))
    return f"Deduplication complete: {count} raw events processed"
```

- [ ] **Step 2: Register task in beat schedule**

In `backend/worker/celery_app.py`, add to the `beat_schedule` dict:

```python
"dedup-events-hourly": {
    "task": "worker.tasks.dedup.dedup_events",
    "schedule": crontab(minute=30),  # :30 past every hour
},
```

- [ ] **Step 3: Commit**

```bash
git add backend/worker/tasks/dedup.py backend/worker/celery_app.py
git commit -m "feat: add dedup_events Celery task with venue resolution and canonical event merging"
```

---

### Task 3: Trigger dedup from ingest_service

**Files:**
- Modify: `backend/app/ingestion/ingest_service.py`

- [ ] **Step 1: Add dedup trigger after upsert**

At the bottom of the `upsert_events` function in `backend/app/ingestion/ingest_service.py`, after the `await db.commit()` line, add:

```python
    # Trigger dedup for newly ingested events (non-blocking)
    try:
        from worker.tasks.dedup import dedup_events
        dedup_events.delay(limit=len(events))
    except Exception:
        pass  # Worker may not be available in all test contexts
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/ingestion/ingest_service.py
git commit -m "feat: trigger dedup task after each ingest batch"
```

---

### Task 4: Update event_service to query canonical_events

**Files:**
- Modify: `backend/app/services/event_service.py`

- [ ] **Step 1: Update build_event_query to use CanonicalEvent**

In `backend/app/services/event_service.py`, update the import:

```python
from app.models.canonical_event import CanonicalEvent
from app.models.event import RawEvent, EventCategory
```

Update `build_event_query` to query `CanonicalEvent` instead of `RawEvent`:

```python
def build_event_query(
    q: str | None = None,
    city: str | None = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    price_max: float | None = None,
    sort: str = "date",
) -> Select:
    query = select(CanonicalEvent).where(
        CanonicalEvent.status == "active",
        CanonicalEvent.is_duplicate_of.is_(None),
    )

    if q:
        query = query.where(CanonicalEvent.title.ilike(f"%{q}%"))

    if city:
        # Join through venue for city filtering
        from app.models.venue import Venue
        query = query.join(Venue, CanonicalEvent.venue_id == Venue.id, isouter=True).where(
            func.lower(Venue.city) == city.lower()
        )

    if date_from:
        query = query.where(
            CanonicalEvent.starts_at >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=UTC)
        )

    if date_to:
        query = query.where(
            CanonicalEvent.starts_at <= datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=UTC)
        )

    if price_max is not None:
        query = query.where(CanonicalEvent.price_min <= price_max)

    if sort == "date":
        query = query.order_by(CanonicalEvent.starts_at.asc())
    elif sort == "price":
        query = query.order_by(CanonicalEvent.price_min.asc().nullslast())

    return query
```

Note: category filtering via junction table is temporarily simplified (categories now stored in JSONB on CanonicalEvent). Update the `search_events` function similarly — replace all `Event` references with `CanonicalEvent`.

- [ ] **Step 2: Restart API and run a smoke test**

```bash
docker compose -f /Users/edbalogh/LiveProjects/BubbaRooEvents/docker-compose.yml up -d --force-recreate api
sleep 5
curl -s http://localhost:8000/api/v1/events?city=Nashville | python3 -m json.tool | head -20
```

Expected: valid JSON response with events from canonical_events table.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/event_service.py
git commit -m "feat: event_service now queries canonical_events instead of raw_events"
```

---

### Task 5: Add user-facing duplicate management API

**Files:**
- Modify: `backend/app/api/v1/events.py`

- [ ] **Step 1: Add duplicate flag and merge endpoints**

In `backend/app/api/v1/events.py`, add:

```python
from app.models.canonical_event import CanonicalEvent

@router.post("/duplicates")
async def flag_duplicate(
    event_a_id: uuid.UUID,
    event_b_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """User flags two canonical events as duplicates for review."""
    # Verify both events exist
    for event_id in [event_a_id, event_b_id]:
        result = await db.execute(select(CanonicalEvent).where(CanonicalEvent.id == event_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    # Store as a pending duplicate pair (reuse conflicts JSONB on event_a)
    from sqlalchemy import update
    await db.execute(
        update(CanonicalEvent)
        .where(CanonicalEvent.id == event_a_id)
        .values(conflicts={"user_flagged_duplicate": str(event_b_id)})
    )
    await db.commit()
    return {"status": "flagged", "event_a": str(event_a_id), "event_b": str(event_b_id)}


@router.post("/duplicates/{event_a_id}/merge/{event_b_id}")
async def merge_duplicates(
    event_a_id: uuid.UUID,
    event_b_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Merge event_b into event_a. event_b becomes hidden, its raw_events relink to event_a."""
    from sqlalchemy import update as sa_update
    # Relink raw_events from event_b to event_a
    await db.execute(
        sa_update(RawEvent)
        .where(RawEvent.canonical_event_id == event_b_id)
        .values(canonical_event_id=event_a_id)
    )
    # Mark event_b as merged
    await db.execute(
        sa_update(CanonicalEvent)
        .where(CanonicalEvent.id == event_b_id)
        .values(status="merged", is_duplicate_of=event_a_id)
    )
    await db.commit()
    # Re-run dedup merge for event_a with all its raw_events
    from worker.tasks.dedup import dedup_events
    dedup_events.delay(limit=50)
    return {"status": "merged", "canonical": str(event_a_id), "merged": str(event_b_id)}


@router.get("/duplicates")
async def list_flagged_duplicates(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List canonical events with user-flagged duplicates."""
    result = await db.execute(
        select(CanonicalEvent).where(
            CanonicalEvent.conflicts["user_flagged_duplicate"].isnot(None),
            CanonicalEvent.status == "active",
        )
    )
    events = result.scalars().all()
    return [{"id": str(e.id), "title": e.title, "flagged_duplicate": e.conflicts.get("user_flagged_duplicate")} for e in events]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/v1/events.py
git commit -m "feat: add duplicate flag and merge API endpoints"
```

---

### Task 6: Backfill dedup for existing Ticketmaster events

- [ ] **Step 1: Trigger dedup for all existing unlinked raw events**

```bash
docker exec bubbarooevents-worker-1 celery -A worker.celery_app call worker.tasks.dedup.dedup_events --args='[1000]'
sleep 30
docker exec bubbarooevents-db-1 psql -U bubbaroo -d bubbaroo_events \
  -c "SELECT COUNT(*) FROM raw_events WHERE canonical_event_id IS NOT NULL;"
```

Expected: count grows (should match or approach total raw_events count after processing).

- [ ] **Step 2: Verify canonical events exist**

```bash
docker exec bubbarooevents-db-1 psql -U bubbaroo -d bubbaroo_events \
  -c "SELECT COUNT(*) FROM canonical_events WHERE status='active';"
```

Expected: similar count to raw_events.

- [ ] **Step 3: Commit (no code change — just verification)**

```bash
git commit --allow-empty -m "chore: verify dedup backfill complete for existing events"
```
