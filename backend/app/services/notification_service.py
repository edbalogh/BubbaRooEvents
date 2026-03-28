"""Notification engine - generates and dispatches event notifications.

Determines which events to notify which users about, then routes
through the dispatcher for delivery.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.user import User
from app.notifications.base import NotificationPayload
from app.notifications.dispatcher import dispatch_notification
from app.services.recommendation_service import recommend_events

logger = logging.getLogger(__name__)


def _format_event_date(dt: datetime) -> str:
    return dt.strftime("%A, %B %d at %I:%M %p")


def _build_event_payload(
    event: Event, notification_type: str, extra_body: str = "",
) -> NotificationPayload:
    """Build a notification payload from an event."""
    price_str = ""
    if event.price_min is not None:
        if event.price_min == 0:
            price_str = "Free"
        elif event.price_max and event.price_max != event.price_min:
            price_str = f"${event.price_min} - ${event.price_max}"
        else:
            price_str = f"${event.price_min}"

    body_parts = []
    if extra_body:
        body_parts.append(extra_body)
    body_parts.append(event.title)
    if event.venue_name:
        body_parts.append(f"at {event.venue_name}")
    body_parts.append(_format_event_date(event.starts_at))
    if price_str:
        body_parts.append(price_str)

    subject_map = {
        "ticket_alert": f"Tickets available: {event.title}",
        "tonight": f"Tonight: {event.title}",
        "new_match": f"You might like: {event.title}",
        "weekly_digest": "Your weekly events roundup",
    }

    return NotificationPayload(
        subject=subject_map.get(notification_type, f"Event: {event.title}"),
        body="\n".join(body_parts),
        event_title=event.title,
        event_url=event.url,
        event_image_url=event.image_url,
        event_date=_format_event_date(event.starts_at),
        event_venue=f"{event.venue_name}, {event.city}" if event.venue_name else event.city,
        notification_type=notification_type,
    )


async def notify_tonight_events(db: AsyncSession) -> int:
    """Send 'tonight' notifications for events happening today.

    For each user, find top events happening today that match their
    preferences and send a notification.
    """
    sent_count = 0
    now = datetime.now(UTC)
    end_of_day = now.replace(hour=23, minute=59, second=59)

    # Get all users
    users_result = await db.execute(select(User))
    users = users_result.scalars().all()

    for user in users:
        city = user.home_city
        if not city:
            continue

        # Get tonight's events scored for this user
        try:
            scored = await recommend_events(db, user, city=city, limit=3)
        except Exception as e:
            logger.error(f"Failed to get recommendations for user {user.id}: {e}")
            continue

        # Filter to events happening today
        tonight = [
            s for s in scored
            if s.event and s.event.starts_at and now <= s.event.starts_at <= end_of_day
        ]

        if not tonight:
            continue

        # Send notification for top event
        top = tonight[0]
        payload = _build_event_payload(
            top.event, "tonight",
            extra_body=f"Happening tonight in {city}!",
        )

        channels = await dispatch_notification(db, user, payload, event_id=top.event.id)
        if channels:
            sent_count += 1
            logger.info(f"Tonight notification sent to {user.email} via {channels}")

    await db.commit()
    return sent_count


async def notify_ticket_alerts(db: AsyncSession) -> int:
    """Send ticket alert notifications for events that just went on sale.

    Checks for events where on_sale_at is within the last ingestion cycle
    (last 30 minutes) and notifies users who would be interested.
    """
    sent_count = 0
    cutoff = datetime.now(UTC) - timedelta(minutes=30)

    # Find events that recently went on sale
    result = await db.execute(
        select(Event)
        .where(
            Event.status == "active",
            Event.on_sale_at.is_not(None),
            Event.on_sale_at >= cutoff,
            Event.starts_at > datetime.now(UTC),
        )
    )
    new_on_sale = result.scalars().all()

    if not new_on_sale:
        return 0

    # Get all users
    users_result = await db.execute(select(User))
    users = users_result.scalars().all()

    for event in new_on_sale:
        for user in users:
            # Quick relevance check: same city
            if user.home_city and event.city:
                if user.home_city.lower() != event.city.lower():
                    continue

            payload = _build_event_payload(
                event, "ticket_alert",
                extra_body="Tickets just went on sale!",
            )

            channels = await dispatch_notification(db, user, payload, event_id=event.id)
            if channels:
                sent_count += 1

    await db.commit()
    return sent_count


async def notify_new_matches(db: AsyncSession) -> int:
    """Send notifications for new high-score events.

    For each user, find recently ingested events that score above
    a threshold and notify them.
    """
    sent_count = 0
    SCORE_THRESHOLD = 0.65

    users_result = await db.execute(select(User))
    users = users_result.scalars().all()

    for user in users:
        city = user.home_city
        if not city:
            continue

        try:
            scored = await recommend_events(db, user, city=city, limit=5)
        except Exception:
            continue

        # Only notify about high-scoring events
        high_scorers = [s for s in scored if s.score >= SCORE_THRESHOLD]

        if not high_scorers:
            continue

        # Send notification for the top match
        top = high_scorers[0]
        payload = _build_event_payload(
            top.event, "new_match",
            extra_body=f"We think you'll love this ({int(top.score * 100)}% match)!",
        )

        channels = await dispatch_notification(db, user, payload, event_id=top.event.id)
        if channels:
            sent_count += 1

    await db.commit()
    return sent_count


async def send_weekly_digest(db: AsyncSession) -> int:
    """Send weekly digest email with top upcoming events for each user."""
    sent_count = 0

    users_result = await db.execute(select(User))
    users = users_result.scalars().all()

    for user in users:
        city = user.home_city
        if not city:
            continue

        try:
            scored = await recommend_events(db, user, city=city, limit=10)
        except Exception:
            continue

        if not scored:
            continue

        # Build digest body
        lines = [f"Here are your top events this week in {city}:\n"]
        for i, s in enumerate(scored[:10], 1):
            e = s.event
            date_str = _format_event_date(e.starts_at) if e.starts_at else "TBD"
            price = ""
            if e.price_min is not None:
                price = " (Free)" if e.price_min == 0 else f" (${e.price_min}+)"
            lines.append(f"{i}. {e.title}{price}")
            lines.append(f"   {date_str} at {e.venue_name or 'TBD'}")
            lines.append("")

        payload = NotificationPayload(
            subject=f"Your weekly events in {city}",
            body="\n".join(lines),
            notification_type="weekly_digest",
        )

        channels = await dispatch_notification(db, user, payload, force=True)
        if channels:
            sent_count += 1

    await db.commit()
    return sent_count
