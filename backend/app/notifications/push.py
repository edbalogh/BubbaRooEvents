"""Push notification channel via Firebase Cloud Messaging (FCM)."""

from __future__ import annotations

import json
import logging

import httpx

from app.core.config import settings
from app.notifications.base import NotificationPayload

logger = logging.getLogger(__name__)

FCM_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"


class PushChannel:
    channel_type = "push"

    def __init__(self):
        self._credentials = None
        self._project_id = None

    def _load_credentials(self) -> bool:
        """Load Firebase credentials from file."""
        creds_path = getattr(settings, "firebase_credentials_path", "")
        if not creds_path:
            return False

        try:
            with open(creds_path) as f:
                creds = json.load(f)
                self._project_id = creds.get("project_id")
                self._credentials = creds
                return True
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Firebase credentials not available: {e}")
            return False

    async def send(
        self, recipient: str, payload: NotificationPayload, metadata: dict | None = None,
    ) -> bool:
        """Send a push notification via FCM.

        `recipient` should be an FCM device token.
        """
        if not self._credentials and not self._load_credentials():
            logger.warning("Firebase not configured, skipping push notification")
            return False

        message = {
            "message": {
                "token": recipient,
                "notification": {
                    "title": payload.subject[:100],
                    "body": payload.body[:500],
                },
                "data": {},
            }
        }

        if payload.event_url:
            message["message"]["data"]["url"] = payload.event_url
        if payload.event_image_url:
            message["message"]["notification"]["image"] = payload.event_image_url

        try:
            url = FCM_URL.format(project_id=self._project_id)
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    url,
                    json=message,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                logger.info(f"Push notification sent to device {recipient[:20]}...")
                return True
        except Exception as e:
            logger.error(f"Push send failed: {e}")
            return False
