"""Trip planning and AI recommendation explanation endpoints."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.event import RawEvent
from app.models.user import User, UserPreference
from app.models.category import Category
from app.services.ai_service import explain_recommendation, plan_trip
from app.services.recommendation_service import recommend_events

router = APIRouter(tags=["ai"])


# --- Recommendation Explanation ---


@router.get("/recommendations/explain/{event_id}")
async def explain_event_recommendation(
    event_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a Claude-powered explanation of why an event was recommended."""
    # Fetch the event
    result = await db.execute(select(RawEvent).where(RawEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Get user's top categories
    pref_result = await db.execute(
        select(UserPreference, Category)
        .join(Category, UserPreference.category_id == Category.id)
        .where(UserPreference.user_id == user.id)
        .order_by(UserPreference.weight.desc())
        .limit(5)
    )
    user_top_categories = [row[1].name for row in pref_result.all()]

    # Score this event for the user
    scored = await recommend_events(db, user, city=event.city, limit=50)
    event_score = None
    for s in scored:
        if s.event.id == event_id:
            event_score = s
            break

    score = event_score.score if event_score else 0.5
    breakdown = {
        "category_affinity": event_score.category_affinity if event_score else 0,
        "embedding_similarity": event_score.embedding_similarity if event_score else 0,
        "popularity": event_score.popularity if event_score else 0,
        "distance_penalty": event_score.distance_penalty if event_score else 0,
    }

    explanation = await explain_recommendation(
        event_title=event.title,
        event_description=event.description,
        event_categories=[c.name for c in getattr(event, "categories", [])] or [],
        event_venue=event.venue_name,
        event_city=event.city,
        event_date=event.starts_at.strftime("%A, %B %d at %I:%M %p") if event.starts_at else None,
        event_price_min=float(event.price_min) if event.price_min else None,
        score=score,
        score_breakdown=breakdown,
        user_top_categories=user_top_categories,
    )

    return {
        "event_id": str(event_id),
        "event_title": event.title,
        "explanation": explanation,
        "score": score,
        "score_breakdown": breakdown,
    }


# --- Trip Planning ---


class TripPlanRequest(BaseModel):
    city: str
    date_from: str  # ISO date string
    date_to: str  # ISO date string
    interests: list[str] = []


@router.post("/trips/explore")
async def explore_trip(
    body: TripPlanRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Plan a trip by exploring events in a destination city.

    Returns AI-curated trip plan plus raw event list.
    """
    try:
        date_from = datetime.fromisoformat(body.date_from).replace(tzinfo=timezone.utc)
        date_to = datetime.fromisoformat(body.date_to).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format (YYYY-MM-DD).")

    if date_to < date_from:
        raise HTTPException(status_code=400, detail="date_to must be after date_from")

    if (date_to - date_from).days > 14:
        raise HTTPException(status_code=400, detail="Trip planning limited to 14 days")

    # Get scored events in the destination city for the date range
    scored = await recommend_events(db, user, city=body.city, limit=20)

    # Filter to events within the date range
    trip_events = []
    for s in scored:
        if s.event.starts_at and date_from <= s.event.starts_at <= date_to + timedelta(days=1):
            trip_events.append(s)

    # Build context for AI
    events_context = []
    for s in trip_events[:15]:
        e = s.event
        events_context.append({
            "id": str(e.id),
            "title": e.title,
            "description": e.description,
            "venue": e.venue_name,
            "date": e.starts_at.strftime("%A, %B %d at %I:%M %p") if e.starts_at else "TBD",
            "price_min": float(e.price_min) if e.price_min else None,
            "url": e.url,
            "score": s.score,
        })

    # Determine interests from user preferences or request
    interests = body.interests
    if not interests:
        pref_result = await db.execute(
            select(UserPreference, Category)
            .join(Category, UserPreference.category_id == Category.id)
            .where(UserPreference.user_id == user.id, UserPreference.weight > 1.0)
            .order_by(UserPreference.weight.desc())
            .limit(5)
        )
        interests = [row[1].name for row in pref_result.all()]

    travel_dates = f"{date_from.strftime('%B %d')} - {date_to.strftime('%B %d, %Y')}"
    ai_plan = await plan_trip(body.city, travel_dates, interests, events_context)

    # Build event list for response
    events_response = []
    for s in trip_events:
        e = s.event
        events_response.append({
            "id": str(e.id),
            "title": e.title,
            "description": e.description,
            "venue_name": e.venue_name,
            "city": e.city,
            "starts_at": e.starts_at.isoformat() if e.starts_at else None,
            "price_min": float(e.price_min) if e.price_min else None,
            "price_max": float(e.price_max) if e.price_max else None,
            "url": e.url,
            "image_url": e.image_url,
            "score": s.score,
            "categories": s.categories or [],
        })

    return {
        "city": body.city,
        "dates": travel_dates,
        "plan": ai_plan,
        "events": events_response,
        "total_events": len(events_response),
    }
