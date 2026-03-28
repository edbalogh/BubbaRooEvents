from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.interaction import UserEventInteraction, UserSavedEvent
from app.models.user import User

router = APIRouter(prefix="/me", tags=["preferences"])


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
    interaction_type: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    valid_types = {"viewed", "clicked", "dismissed", "attended"}
    if interaction_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid interaction type. Must be one of: {valid_types}",
        )
    interaction = UserEventInteraction(
        user_id=user.id, event_id=event_id, interaction=interaction_type
    )
    db.add(interaction)
    await db.flush()
    return {"status": "recorded"}


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
    return [{"event_id": str(s.event_id), "notes": s.notes, "created_at": s.created_at} for s in saved]
