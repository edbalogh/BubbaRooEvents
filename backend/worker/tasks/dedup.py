"""Celery task for cross-source event deduplication."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
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

    result = await db.execute(select(Venue).where(Venue.city == raw.city))
    city_venues = [{"id": v.id, "name": v.name, "city": v.city} for v in result.scalars().all()]

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
        result = await db.execute(select(Venue).where(Venue.slug == slug))
        existing = result.scalar_one_or_none()
        return existing.id if existing else None


async def _find_duplicate_candidates(db: AsyncSession, raw: RawEvent) -> list[CanonicalEvent]:
    """Find canonical events within a 4-hour window of this raw event."""
    if not raw.starts_at:
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


async def _run_dedup_events(limit: int = 500) -> int:
    """Process unlinked raw events: resolve venues, find/create canonical events."""
    llm = OllamaProvider(base_url=settings.ollama_base_url, model=settings.discovery_search_model)
    processed = 0

    async with _session_factory() as db:
        result = await db.execute(
            select(RawEvent).where(RawEvent.canonical_event_id.is_(None)).limit(limit)
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
                    # Strong match: same venue and title similarity
                    if venue_id and candidate.venue_id == venue_id:
                        canonical_id = candidate.id
                        break

                    # Weaker match: LLM check
                    event_a = {
                        "title": raw.title,
                        "venue_name": raw.venue_name,
                        "starts_at": str(raw.starts_at),
                    }
                    event_b = {
                        "title": candidate.title,
                        "starts_at": str(candidate.starts_at),
                    }
                    is_dup = await are_duplicate_events(
                        llm, event_a, event_b,
                        confidence_threshold=settings.discovery_dedup_confidence_threshold,
                    )
                    if is_dup:
                        canonical_id = candidate.id
                        break

                if canonical_id:
                    await db.execute(
                        update(RawEvent).where(RawEvent.id == raw.id).values(canonical_event_id=canonical_id)
                    )
                    # Re-merge all raw events for this canonical
                    siblings_result = await db.execute(
                        select(RawEvent).where(RawEvent.canonical_event_id == canonical_id)
                    )
                    all_raws = list(siblings_result.scalars().all()) + [raw]
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
                        title=merged.get("title") or raw.title,
                        description=merged.get("description"),
                        venue_id=venue_id,
                        starts_at=raw.starts_at,
                        ends_at=raw.ends_at,
                        price_min=merged.get("price_min"),
                        price_max=merged.get("price_max"),
                        currency=raw.currency or "USD",
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
                        update(RawEvent).where(RawEvent.id == raw.id).values(canonical_event_id=new_canonical.id)
                    )

                await db.commit()
                processed += 1

        except Exception as e:
            logger.error(f"[dedup] Failed to process raw_event {raw.id}: {e}")

    return processed


@celery_app.task(name="worker.tasks.dedup.dedup_events")
def dedup_events(limit: int = 500):
    """Process unlinked raw events: resolve venues and create/link canonical events."""
    count = asyncio.run(_run_dedup_events(limit=limit))
    return f"Deduplication complete: {count} raw events processed"
