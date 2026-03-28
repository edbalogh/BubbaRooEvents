"""SMS notification channel via Twilio."""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.notifications.base import NotificationPayload

logger = logging.getLogger(__name__)


class SMSChannel:
    channel_type = "sms"

    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        from_number: str | None = None,
    ):
        self.account_sid = account_sid or getattr(settings, "twilio_account_sid", "")
        self.auth_token = auth_token or getattr(settings, "twilio_auth_token", "")
        self.from_number = from_number or getattr(settings, "twilio_phone_number", "")

    async def send(
        self, recipient: str, payload: NotificationPayload, metadata: dict | None = None,
    ) -> bool:
        if not all([self.account_sid, self.auth_token, self.from_number]):
            logger.warning("Twilio credentials not configured, skipping SMS")
            return False

        # SMS body: keep it short (160 chars ideal, 1600 max)
        body = payload.body[:1500]
        if payload.event_url:
            body = f"{body}\n{payload.event_url}"

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    url,
                    auth=(self.account_sid, self.auth_token),
                    data={
                        "To": recipient,
                        "From": self.from_number,
                        "Body": body,
                    },
                )
                response.raise_for_status()
                logger.info(f"SMS sent to {recipient}")
                return True
        except Exception as e:
            logger.error(f"SMS send failed to {recipient}: {e}")
            return False
