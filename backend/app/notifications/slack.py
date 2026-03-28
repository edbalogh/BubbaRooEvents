"""Slack notification channel via incoming webhooks."""

from __future__ import annotations

import logging

import httpx

from app.notifications.base import NotificationPayload

logger = logging.getLogger(__name__)


class SlackChannel:
    channel_type = "slack"

    async def send(
        self, recipient: str, payload: NotificationPayload, metadata: dict | None = None,
    ) -> bool:
        """Send a Slack notification via incoming webhook.

        `recipient` should be a Slack incoming webhook URL.
        """
        if not recipient.startswith("https://hooks.slack.com/"):
            logger.error(f"Invalid Slack webhook URL: {recipient[:50]}")
            return False

        blocks = self._build_blocks(payload)

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    recipient,
                    json={"blocks": blocks, "text": payload.subject},
                )
                response.raise_for_status()
                logger.info(f"Slack notification sent: {payload.subject}")
                return True
        except Exception as e:
            logger.error(f"Slack send failed: {e}")
            return False

    def _build_blocks(self, payload: NotificationPayload) -> list[dict]:
        blocks: list[dict] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": payload.subject[:150]},
            },
        ]

        if payload.event_title:
            text = f"*{payload.event_title}*"
            if payload.event_date:
                text += f"\n{payload.event_date}"
            if payload.event_venue:
                text += f"\n{payload.event_venue}"

            section: dict = {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
            }
            if payload.event_image_url:
                section["accessory"] = {
                    "type": "image",
                    "image_url": payload.event_image_url,
                    "alt_text": payload.event_title or "Event image",
                }
            blocks.append(section)

        if payload.body:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": payload.body[:3000]},
            })

        if payload.event_url:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Event"},
                        "url": payload.event_url,
                        "style": "primary",
                    },
                ],
            })

        return blocks
