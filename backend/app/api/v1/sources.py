"""API endpoints for event sources and user source preferences."""

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.ingestion.local_discovery import discover_sources_for_city, get_known_cities
from app.models.source import EventSource, UserSourcePreference
from app.models.user import User

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
async def list_sources(
    city: str | None = Query(None, description="Filter sources by city"),
    db: AsyncSession = Depends(get_db),
):
    """List all registered event sources, optionally filtered by city."""
    query = select(EventSource).where(EventSource.is_active == True).order_by(EventSource.name)

    if city:
        # Match sources that cover this city or are nationwide (coverage_cities is null)
        query = query.where(
            (EventSource.coverage_cities.is_(None))
            | (EventSource.coverage_cities.ilike(f"%{city}%"))
        )

    result = await db.execute(query)
    sources = result.scalars().all()
    return [
        {
            "id": s.id,
            "slug": s.slug,
            "name": s.name,
            "source_type": s.source_type,
            "description": s.description,
            "url": s.url,
            "is_local": s.is_local,
            "coverage_cities": s.coverage_cities,
        }
        for s in sources
    ]


@router.get("/discover")
async def discover_local_sources(
    city: str = Query(..., description="City to discover sources for"),
    state: str | None = Query(None, description="State code"),
):
    """Discover local event sources for a given city.

    Returns known local aggregators, venue websites, city calendars,
    and alternative newspapers that cover this location.
    """
    sources = await discover_sources_for_city(city, state)
    return [
        {
            "name": s.name,
            "url": s.url,
            "source_type": s.source_type,
            "description": s.description,
            "city": s.city,
            "state": s.state,
            "likely_categories": s.likely_categories,
            "has_ical_feed": s.has_ical_feed,
            "has_api": s.has_api,
        }
        for s in sources
    ]


@router.get("/discover/cities")
async def list_supported_cities():
    """List cities with curated local source data."""
    return {"cities": get_known_cities()}


@router.get("/me/preferences")
async def get_source_preferences(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the user's source preferences (liked, disliked, disabled)."""
    result = await db.execute(
        select(UserSourcePreference, EventSource)
        .join(EventSource, UserSourcePreference.source_id == EventSource.id)
        .where(UserSourcePreference.user_id == user.id)
    )
    prefs = []
    for row in result.all():
        pref, source = row
        prefs.append({
            "source_id": source.id,
            "source_slug": source.slug,
            "source_name": source.name,
            "source_type": source.source_type,
            "is_local": source.is_local,
            "preference": pref.preference,
        })
    return prefs


@router.put("/me/preferences")
async def update_source_preference(
    source_id: int = Body(...),
    preference: str = Body(..., description="One of: liked, disliked, disabled, neutral"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set a user's preference for a specific event source.

    - **liked**: Boost events from this source in recommendations
    - **disliked**: Reduce events from this source (still shown, lower ranked)
    - **disabled**: Completely hide events from this source
    - **neutral**: Remove any preference (reset to default)
    """
    valid = {"liked", "disliked", "disabled", "neutral"}
    if preference not in valid:
        return {"error": f"Invalid preference. Must be one of: {valid}"}

    # Remove existing preference
    existing = await db.execute(
        select(UserSourcePreference).where(
            UserSourcePreference.user_id == user.id,
            UserSourcePreference.source_id == source_id,
        )
    )
    old = existing.scalar_one_or_none()

    if preference == "neutral":
        if old:
            await db.delete(old)
        return {"status": "preference removed"}

    if old:
        old.preference = preference
    else:
        db.add(UserSourcePreference(
            user_id=user.id, source_id=source_id, preference=preference,
        ))

    await db.flush()
    return {"status": "updated", "preference": preference}


@router.post("/register")
async def register_source(
    slug: str = Body(...),
    name: str = Body(...),
    source_type: str = Body(..., description="api, scraper, ical, manual"),
    description: str | None = Body(None),
    url: str | None = Body(None),
    is_local: bool = Body(False),
    coverage_cities: str | None = Body(None, description="Comma-separated city names, null for nationwide"),
    db: AsyncSession = Depends(get_db),
):
    """Register a new event source (admin/system use)."""
    source = EventSource(
        slug=slug,
        name=name,
        source_type=source_type,
        description=description,
        url=url,
        is_local=is_local,
        coverage_cities=coverage_cities,
    )
    db.add(source)
    await db.flush()
    return {"status": "created", "id": source.id, "slug": source.slug}
