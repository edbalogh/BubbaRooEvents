import hashlib
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import cast, func, select, update as sa_update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import (
    CACHE_TTL_EVENT_SEARCH,
    CACHE_TTL_TONIGHT,
    cache_get,
    cache_set,
    event_search_key,
    tonight_key,
)
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.canonical_event import CanonicalEvent
from app.models.event import RawEvent
from app.schemas.event import CanonicalEventResponse, EventListResponse, FlagDuplicateRequest
from app.services.event_service import get_event_by_id, get_tonight_events, search_events

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=EventListResponse)
async def list_events(
    q: str | None = Query(None, description="Search keyword"),
    city: str | None = Query(None, description="City name"),
    category: str | None = Query(None, description="Category slug"),
    date_from: date | None = Query(None, description="Start date"),
    date_to: date | None = Query(None, description="End date"),
    price_max: float | None = Query(None, description="Max price"),
    sort: str = Query("date", description="Sort by: date, price"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    # Check cache
    params_str = f"{q}:{category}:{date_from}:{date_to}:{price_max}:{sort}:{page}:{per_page}"
    params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]
    cache_key = event_search_key(city or "all", params_hash)

    cached = await cache_get(cache_key)
    if cached:
        return cached

    events, total = await search_events(
        db, q=q, city=city, category=category,
        date_from=date_from, date_to=date_to,
        price_max=price_max, sort=sort,
        page=page, per_page=per_page,
    )
    result = EventListResponse(
        events=[CanonicalEventResponse.model_validate(e) for e in events],
        total=total,
        page=page,
        per_page=per_page,
    )
    await cache_set(cache_key, result.model_dump(), CACHE_TTL_EVENT_SEARCH)
    return result


@router.get("/tonight", response_model=list[CanonicalEventResponse])
async def tonight_events(
    city: str = Query(..., description="City name"),
    db: AsyncSession = Depends(get_db),
):
    cache_key = tonight_key(city)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    events = await get_tonight_events(db, city)
    result = [CanonicalEventResponse.model_validate(e).model_dump() for e in events]
    await cache_set(cache_key, result, CACHE_TTL_TONIGHT)
    return result


@router.get("/duplicates")
async def list_flagged_duplicates(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List canonical events with user-flagged duplicates."""
    result = await db.execute(
        select(CanonicalEvent).where(
            CanonicalEvent.conflicts["user_flagged_duplicate"].as_string().isnot(None),
            CanonicalEvent.status == "active",
        )
    )
    events = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "title": e.title,
            "flagged_duplicate": e.conflicts.get("user_flagged_duplicate") if e.conflicts else None,
        }
        for e in events
    ]


@router.get("/{event_id}", response_model=CanonicalEventResponse)
async def get_event(event_id: UUID, db: AsyncSession = Depends(get_db)):
    event = await get_event_by_id(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return CanonicalEventResponse.model_validate(event)


@router.post("/duplicates")
async def flag_duplicate(
    request: FlagDuplicateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """User flags two canonical events as duplicates for review."""
    for event_id in [request.event_a_id, request.event_b_id]:
        result = await db.execute(select(CanonicalEvent).where(CanonicalEvent.id == event_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    await db.execute(
        sa_update(CanonicalEvent)
        .where(CanonicalEvent.id == request.event_a_id)
        .values(
            conflicts=func.coalesce(CanonicalEvent.conflicts, cast({}, JSONB)).op("||")(
                cast({"user_flagged_duplicate": str(request.event_b_id)}, JSONB)
            )
        )
    )
    await db.commit()
    return {"status": "flagged", "event_a": str(request.event_a_id), "event_b": str(request.event_b_id)}


@router.post("/duplicates/{event_a_id}/merge/{event_b_id}")
async def merge_duplicates(
    event_a_id: UUID,
    event_b_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Merge event_b into event_a. event_b is hidden; its raw_events relink to event_a."""
    for event_id in [event_a_id, event_b_id]:
        check = await db.execute(select(CanonicalEvent).where(CanonicalEvent.id == event_id))
        if not check.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    await db.execute(
        sa_update(RawEvent)
        .where(RawEvent.canonical_event_id == event_b_id)
        .values(canonical_event_id=event_a_id)
    )
    await db.execute(
        sa_update(CanonicalEvent)
        .where(CanonicalEvent.id == event_b_id)
        .values(status="merged", is_duplicate_of=event_a_id)
    )
    await db.commit()
    try:
        from worker.tasks.dedup import dedup_events
        dedup_events.delay(limit=50)
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).debug(f"[events] Could not dispatch dedup task after merge: {e}")
    return {"status": "merged", "canonical": str(event_a_id), "merged": str(event_b_id)}
