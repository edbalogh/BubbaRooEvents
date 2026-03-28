"""Notification channel management and preferences API."""

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.notification import Notification, UserChannel
from app.models.user import User

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


# --- Schemas ---


class ChannelCreate(BaseModel):
    channel_type: str  # email, sms, slack, push
    channel_address: str  # email addr, phone #, webhook URL, FCM token


class ChannelResponse(BaseModel):
    id: str
    channel_type: str
    channel_address: str
    is_active: bool


class NotificationPrefsUpdate(BaseModel):
    quiet_hours_start: str | None = None  # "22:00"
    quiet_hours_end: str | None = None  # "08:00"
    max_per_day: int | None = None  # 1-20
    enabled_types: list[str] | None = None  # ticket_alert, tonight, weekly_digest, new_match


# --- Channel Management ---


@router.get("/channels")
async def list_channels(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's notification channels."""
    result = await db.execute(
        select(UserChannel)
        .where(UserChannel.user_id == user.id)
        .order_by(UserChannel.created_at.desc())
    )
    channels = result.scalars().all()
    return [
        {
            "id": str(ch.id),
            "channel_type": ch.channel_type,
            "channel_address": _mask_address(ch.channel_type, ch.channel_address),
            "is_active": ch.is_active,
        }
        for ch in channels
    ]


@router.post("/channels", status_code=status.HTTP_201_CREATED)
async def add_channel(
    body: ChannelCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a notification channel (email, SMS, Slack webhook, push token)."""
    valid_types = {"email", "sms", "slack", "push"}
    if body.channel_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel type. Must be one of: {valid_types}",
        )

    # Check for duplicate
    existing = await db.execute(
        select(UserChannel).where(
            UserChannel.user_id == user.id,
            UserChannel.channel_type == body.channel_type,
            UserChannel.channel_address == body.channel_address,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This channel is already registered",
        )

    channel = UserChannel(
        user_id=user.id,
        channel_type=body.channel_type,
        channel_address=body.channel_address,
        is_active=True,
    )
    db.add(channel)
    await db.flush()

    return {
        "id": str(channel.id),
        "channel_type": channel.channel_type,
        "channel_address": _mask_address(channel.channel_type, channel.channel_address),
        "is_active": channel.is_active,
    }


@router.put("/channels/{channel_id}/toggle")
async def toggle_channel(
    channel_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle a notification channel on/off."""
    result = await db.execute(
        select(UserChannel).where(
            UserChannel.id == channel_id,
            UserChannel.user_id == user.id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    channel.is_active = not channel.is_active
    await db.flush()
    return {"id": str(channel.id), "is_active": channel.is_active}


@router.delete("/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_channel(
    channel_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a notification channel."""
    result = await db.execute(
        delete(UserChannel).where(
            UserChannel.id == channel_id,
            UserChannel.user_id == user.id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Channel not found")


# --- Notification Preferences ---


@router.get("/preferences")
async def get_notification_preferences(
    user: User = Depends(get_current_user),
):
    """Get notification preferences (quiet hours, throttle, enabled types)."""
    prefs = user.notification_preferences or {}
    return {
        "quiet_hours_start": prefs.get("quiet_hours_start"),
        "quiet_hours_end": prefs.get("quiet_hours_end"),
        "max_per_day": prefs.get("max_per_day", 5),
        "enabled_types": prefs.get(
            "enabled_types", ["ticket_alert", "tonight", "weekly_digest", "new_match"]
        ),
    }


@router.put("/preferences")
async def update_notification_preferences(
    body: NotificationPrefsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update notification preferences."""
    prefs = dict(user.notification_preferences) if user.notification_preferences else {}

    if body.quiet_hours_start is not None:
        prefs["quiet_hours_start"] = body.quiet_hours_start
    if body.quiet_hours_end is not None:
        prefs["quiet_hours_end"] = body.quiet_hours_end
    if body.max_per_day is not None:
        prefs["max_per_day"] = max(1, min(20, body.max_per_day))
    if body.enabled_types is not None:
        valid = {"ticket_alert", "tonight", "weekly_digest", "new_match"}
        prefs["enabled_types"] = [t for t in body.enabled_types if t in valid]

    user.notification_preferences = prefs
    await db.flush()
    return {
        "quiet_hours_start": prefs.get("quiet_hours_start"),
        "quiet_hours_end": prefs.get("quiet_hours_end"),
        "max_per_day": prefs.get("max_per_day", 5),
        "enabled_types": prefs.get(
            "enabled_types", ["ticket_alert", "tonight", "weekly_digest", "new_match"]
        ),
    }


# --- Notification History ---


@router.get("/history")
async def get_notification_history(
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent notification history."""
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(min(limit, 50))
    )
    notifications = result.scalars().all()
    return [
        {
            "id": str(n.id),
            "channel": n.channel,
            "notification_type": n.notification_type,
            "status": n.status,
            "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            "payload": {
                "subject": n.payload.get("subject", ""),
                "event_title": n.payload.get("event_title"),
            },
        }
        for n in notifications
    ]


# --- Helpers ---


def _mask_address(channel_type: str, address: str) -> str:
    """Mask sensitive parts of channel addresses for display."""
    if channel_type == "email" and "@" in address:
        local, domain = address.split("@", 1)
        return f"{local[:2]}***@{domain}"
    if channel_type == "sms" and len(address) > 4:
        return f"***{address[-4:]}"
    if channel_type == "push":
        return f"{address[:8]}..." if len(address) > 8 else address
    if channel_type == "slack":
        return "Slack webhook configured"
    return address
