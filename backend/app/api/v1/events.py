import hashlib
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from app.schemas.event import CanonicalEventResponse, EventListResponse
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


@router.get("/{event_id}", response_model=CanonicalEventResponse)
async def get_event(event_id: UUID, db: AsyncSession = Depends(get_db)):
    event = await get_event_by_id(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return CanonicalEventResponse.model_validate(event)
