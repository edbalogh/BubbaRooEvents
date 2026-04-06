from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.category import Category
from app.models.interaction import UserEventInteraction, UserSavedEvent
from app.models.user import User, UserPreference
from app.schemas.recommendation import InteractionCreate, PreferenceUpdate
from app.core.cache import invalidate_user_recommendations
from app.services.preference_learning import get_preference_stats
from app.services.recommendation_service import update_preference_from_interaction
from app.services.user_service import update_user_city

router = APIRouter(prefix="/me", tags=["preferences"])


# --- Preference Management ---


@router.get("/preferences")
async def get_preferences(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the user's category preference weights."""
    result = await db.execute(
        select(UserPreference, Category)
        .join(Category, UserPreference.category_id == Category.id)
        .where(UserPreference.user_id == user.id)
        .order_by(UserPreference.weight.desc())
    )

    prefs = []
    for row in result.all():
        pref, cat = row
        prefs.append({
            "category_id": cat.id,
            "category_name": cat.name,
            "category_slug": cat.slug,
            "weight": round(pref.weight, 2),
        })

    return {
        "categories": prefs,
        "max_distance_miles": user.notification_preferences.get("max_distance_miles", 25.0),
    }


@router.put("/preferences")
async def update_preferences(
    updates: list[PreferenceUpdate] = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set explicit preference weights for categories."""
    for update in updates:
        # Look up category by slug
        cat_result = await db.execute(
            select(Category).where(Category.slug == update.category_slug)
        )
        cat = cat_result.scalar_one_or_none()
        if not cat:
            continue

        # Upsert
        existing = await db.execute(
            select(UserPreference)
            .where(UserPreference.user_id == user.id, UserPreference.category_id == cat.id)
        )
        pref = existing.scalar_one_or_none()

        clamped = max(-1.0, min(5.0, update.weight))
        if pref:
            pref.weight = clamped
        else:
            db.add(UserPreference(user_id=user.id, category_id=cat.id, weight=clamped))

    await db.flush()
    await invalidate_user_recommendations(str(user.id))
    return {"status": "updated"}


@router.get("/preferences/stats")
async def get_learning_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get preference learning statistics (interaction counts, confidence)."""
    return await get_preference_stats(db, user.id)


@router.put("/preferences/distance")
async def update_distance_preference(
    max_distance_miles: float = Body(..., ge=1, le=500),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update preferred max distance for recommendations."""
    prefs = dict(user.notification_preferences) if user.notification_preferences else {}
    prefs["max_distance_miles"] = max_distance_miles
    user.notification_preferences = prefs
    await db.flush()
    return {"status": "updated", "max_distance_miles": max_distance_miles}


# --- Event Interactions ---


@router.post("/events/{event_id}/save", status_code=status.HTTP_201_CREATED)
async def save_event(
    event_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    saved = UserSavedEvent(user_id=user.id, event_id=event_id)
    db.add(saved)
    interaction = UserEventInteraction(
        user_id=user.id, event_id=event_id, interaction="saved"
    )
    db.add(interaction)
    await db.flush()

    # Auto-learn preferences
    await update_preference_from_interaction(db, user.id, event_id, "saved")

    return {"status": "saved"}


@router.delete("/events/{event_id}/save", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_event(
    event_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(UserSavedEvent).where(
            UserSavedEvent.user_id == user.id,
            UserSavedEvent.event_id == event_id,
        )
    )


@router.post("/events/{event_id}/interact")
async def log_interaction(
    event_id: UUID,
    body: InteractionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    valid_types = {"viewed", "clicked", "dismissed", "attended"}
    if body.interaction_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid interaction type. Must be one of: {valid_types}",
        )
    interaction = UserEventInteraction(
        user_id=user.id, event_id=event_id, interaction=body.interaction_type
    )
    db.add(interaction)
    await db.flush()

    # Auto-learn preferences from this interaction
    await update_preference_from_interaction(db, user.id, event_id, body.interaction_type)

    return {"status": "recorded", "interaction": body.interaction_type}


@router.get("/saved-events")
async def list_saved_events(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserSavedEvent)
        .where(UserSavedEvent.user_id == user.id)
        .order_by(UserSavedEvent.created_at.desc())
    )
    saved = result.scalars().all()
    return [
        {"event_id": str(s.event_id), "notes": s.notes, "created_at": s.created_at}
        for s in saved
    ]


class UpdateCityRequest(BaseModel):
    city: str = Field(min_length=1, max_length=100)

    model_config = {"str_strip_whitespace": True}


@router.put("/city")
async def update_home_city(
    body: UpdateCityRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the user's home city and queue ingestion for it."""
    await update_user_city(db, user, body.city)
    return {"home_city": body.city}
