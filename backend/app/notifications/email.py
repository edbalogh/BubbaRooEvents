"""Email notification channel via Resend API."""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.notifications.base import NotificationPayload

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
FROM_ADDRESS = "BubbaRoo Events <events@bubbaroo.app>"


class EmailChannel:
    channel_type = "email"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or getattr(settings, "resend_api_key", "")

    async def send(
        self, recipient: str, payload: NotificationPayload, metadata: dict | None = None,
    ) -> bool:
        if not self.api_key:
            logger.warning("Resend API key not configured, skipping email")
            return False

        html = payload.html_body or self._build_html(payload)

        data = {
            "from": FROM_ADDRESS,
            "to": [recipient],
            "subject": payload.subject,
            "html": html,
            "text": payload.body,
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    RESEND_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=data,
                )
                response.raise_for_status()
                logger.info(f"Email sent to {recipient}: {payload.subject}")
                return True
        except Exception as e:
            logger.error(f"Email send failed to {recipient}: {e}")
            return False

    def _build_html(self, payload: NotificationPayload) -> str:
        image_section = ""
        if payload.event_image_url:
            image_section = f'<img src="{payload.event_image_url}" alt="" style="width:100%;max-width:600px;border-radius:8px;margin-bottom:16px;" />'

        event_details = ""
        if payload.event_title:
            event_details = f"""
            <h2 style="margin:0 0 8px;color:#1a1a1a;">{payload.event_title}</h2>
            {f'<p style="color:#666;margin:0 0 4px;">{payload.event_date}</p>' if payload.event_date else ''}
            {f'<p style="color:#666;margin:0 0 12px;">{payload.event_venue}</p>' if payload.event_venue else ''}
            """

        cta = ""
        if payload.event_url:
            cta = f'<a href="{payload.event_url}" style="display:inline-block;background:#0284c7;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin-top:12px;">View Event</a>'

        return f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:24px;">
            <div style="text-align:center;margin-bottom:24px;">
                <span style="font-size:24px;font-weight:700;color:#0284c7;">BubbaRoo</span>
                <span style="color:#999;font-size:14px;"> Events</span>
            </div>
            {image_section}
            {event_details}
            <div style="color:#333;line-height:1.6;">
                {payload.body}
            </div>
            <div style="text-align:center;margin-top:16px;">
                {cta}
            </div>
            <hr style="border:none;border-top:1px solid #eee;margin:32px 0 16px;" />
            <p style="color:#999;font-size:12px;text-align:center;">
                You received this because you're subscribed to BubbaRoo Events notifications.
                <a href="#" style="color:#999;">Unsubscribe</a>
            </p>
        </div>
        """
