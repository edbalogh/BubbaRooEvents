from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.recommendation_service import recommend_events

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("")
async def get_recommendations(
    city: str | None = Query(None, description="City to find events in (defaults to user home city)"),
    limit: int = Query(20, ge=1, le=50),
    max_distance_miles: float = Query(25.0, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_city = city or user.home_city

    scored_events = await recommend_events(
        db, user, city=target_city, limit=limit, max_distance_miles=max_distance_miles,
    )

    return [
        {
            "id": str(se.event.id),
            "title": se.event.title,
            "description": se.event.description,
            "venue_name": se.event.venue_name,
            "city": se.event.city,
            "state": se.event.state,
            "starts_at": se.event.starts_at.isoformat(),
            "price_min": float(se.event.price_min) if se.event.price_min else None,
            "price_max": float(se.event.price_max) if se.event.price_max else None,
            "currency": se.event.currency,
            "url": se.event.url,
            "image_url": se.event.image_url,
            "categories": se.categories or [],
            "score": se.score,
            "score_breakdown": {
                "category_affinity": se.category_affinity,
                "embedding_similarity": se.embedding_similarity,
                "popularity": se.popularity,
                "distance_penalty": se.distance_penalty,
            },
        }
        for se in scored_events
    ]
