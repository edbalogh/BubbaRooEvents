"""Base protocol and types for notification channels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class NotificationPayload:
    subject: str
    body: str
    html_body: str | None = None
    event_title: str | None = None
    event_url: str | None = None
    event_image_url: str | None = None
    event_date: str | None = None
    event_venue: str | None = None
    notification_type: str = "new_match"  # ticket_alert, tonight, weekly_digest, new_match


class NotificationChannel(Protocol):
    channel_type: str

    async def send(
        self, recipient: str, payload: NotificationPayload, metadata: dict | None = None,
    ) -> bool:
        """Send a notification. Returns True if successful."""
        ...
