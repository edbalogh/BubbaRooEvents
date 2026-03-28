"""Unified notification dispatcher.

Routes notifications to the appropriate channel adapters based on
user preferences. Handles deduplication, throttling, and quiet hours.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, time
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, UserChannel
from app.models.user import User
from app.notifications.base import NotificationPayload
from app.notifications.email import EmailChannel
from app.notifications.push import PushChannel
from app.notifications.slack import SlackChannel
from app.notifications.sms import SMSChannel

logger = logging.getLogger(__name__)

# Channel adapter instances
CHANNEL_ADAPTERS = {
    "email": EmailChannel(),
    "sms": SMSChannel(),
    "slack": SlackChannel(),
    "push": PushChannel(),
}


async def dispatch_notification(
    db: AsyncSession,
    user: User,
    payload: NotificationPayload,
    event_id: UUID | None = None,
    force: bool = False,
) -> list[str]:
    """
    Send a notification to a user through all their active channels.

    Checks:
    1. Deduplication (don't re-notify same user about same event)
    2. Throttling (max N notifications per day)
    3. Quiet hours (respect user's quiet time)
    4. Channel availability (only send to active channels)

    Returns list of channels that were successfully notified.
    """
    prefs = user.notification_preferences or {}

    if not force:
        # Check quiet hours
        if _in_quiet_hours(prefs, user.timezone):
            logger.debug(f"Skipping notification for {user.id}: quiet hours")
            return []

        # Check deduplication
        if event_id and await _already_notified(db, user.id, event_id):
            logger.debug(f"Skipping notification for {user.id}: already notified about event")
            return []

        # Check daily throttle
        max_per_day = prefs.get("max_per_day", 5)
        if await _daily_count(db, user.id) >= max_per_day:
            logger.debug(f"Skipping notification for {user.id}: daily limit reached")
            return []

        # Check if this notification type is enabled
        enabled_types = prefs.get("enabled_types", ["ticket_alert", "tonight", "weekly_digest", "new_match"])
        if payload.notification_type not in enabled_types:
            logger.debug(f"Skipping {payload.notification_type} for {user.id}: type disabled")
            return []

    # Get user's active channels
    result = await db.execute(
        select(UserChannel)
        .where(UserChannel.user_id == user.id, UserChannel.is_active == True)
    )
    channels = result.scalars().all()

    if not channels:
        logger.debug(f"No active channels for user {user.id}")
        return []

    # Send through each channel
    sent_channels: list[str] = []
    for channel in channels:
        adapter = CHANNEL_ADAPTERS.get(channel.channel_type)
        if not adapter:
            logger.warning(f"Unknown channel type: {channel.channel_type}")
            continue

        success = await adapter.send(channel.channel_address, payload)

        # Log notification
        notification = Notification(
            user_id=user.id,
            event_id=event_id,
            channel=channel.channel_type,
            notification_type=payload.notification_type,
            payload={
                "subject": payload.subject,
                "body": payload.body[:500],
                "event_title": payload.event_title,
            },
            status="sent" if success else "failed",
            sent_at=datetime.now(UTC) if success else None,
        )
        db.add(notification)

        if success:
            sent_channels.append(channel.channel_type)

    await db.flush()
    return sent_channels


def _in_quiet_hours(prefs: dict, timezone: str) -> bool:
    """Check if current time is within user's quiet hours."""
    quiet_start_str = prefs.get("quiet_hours_start")
    quiet_end_str = prefs.get("quiet_hours_end")

    if not quiet_start_str or not quiet_end_str:
        return False

    try:
        now = datetime.now(UTC)
        quiet_start = time.fromisoformat(quiet_start_str)
        quiet_end = time.fromisoformat(quiet_end_str)
        current_time = now.time()

        # Handle overnight quiet hours (e.g., 22:00 - 08:00)
        if quiet_start > quiet_end:
            return current_time >= quiet_start or current_time <= quiet_end
        else:
            return quiet_start <= current_time <= quiet_end
    except (ValueError, TypeError):
        return False


async def _already_notified(db: AsyncSession, user_id: UUID, event_id: UUID) -> bool:
    """Check if we already sent a notification about this event to this user."""
    result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.event_id == event_id,
            Notification.status == "sent",
        )
    )
    count = result.scalar() or 0
    return count > 0


async def _daily_count(db: AsyncSession, user_id: UUID) -> int:
    """Count notifications sent to user today."""
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.status == "sent",
            Notification.sent_at >= today_start,
        )
    )
    return result.scalar() or 0
