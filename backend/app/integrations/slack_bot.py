"""Slack bot integration for BubbaRoo Events.

Handles slash commands and interactive messages via Slack's HTTP API.
Deployed as FastAPI routes that receive Slack webhook payloads.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/slack", tags=["slack"])


def _verify_slack_signature(
    body: bytes,
    timestamp: str,
    signature: str,
) -> bool:
    """Verify that the request came from Slack."""
    signing_secret = getattr(settings, "slack_signing_secret", "")
    if not signing_secret:
        return False

    # Prevent replay attacks
    if abs(time.time() - float(timestamp)) > 300:
        return False

    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    my_signature = "v0=" + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(my_signature, signature)


@router.post("/commands")
async def handle_slash_command(
    request: Request,
    x_slack_request_timestamp: str = Header(""),
    x_slack_signature: str = Header(""),
):
    """Handle Slack slash commands.

    Supported commands:
    - /bubbaroo tonight [city] - Events happening tonight
    - /bubbaroo recommend [city] - Personalized recommendations
    - /bubbaroo search <query> - Search for events
    - /bubbaroo trip <city> <dates> - Trip planning
    """
    body = await request.body()

    # Verify Slack signature
    if not _verify_slack_signature(body, x_slack_request_timestamp, x_slack_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    form_data = await request.form()
    text = form_data.get("text", "").strip()
    user_id = form_data.get("user_id", "")
    response_url = form_data.get("response_url", "")

    parts = text.split(maxsplit=1)
    subcommand = parts[0].lower() if parts else "help"
    args = parts[1] if len(parts) > 1 else ""

    if subcommand == "tonight":
        return _tonight_response(args or "Austin")
    elif subcommand == "recommend":
        return _recommend_response(args or "Austin")
    elif subcommand == "search":
        return _search_response(args)
    elif subcommand == "trip":
        return _trip_response(args)
    else:
        return _help_response()


@router.post("/interactions")
async def handle_interaction(request: Request):
    """Handle interactive message actions (button clicks, etc.)."""
    form_data = await request.form()
    payload_str = form_data.get("payload", "{}")
    payload = json.loads(payload_str)

    action_type = payload.get("type")
    if action_type == "block_actions":
        actions = payload.get("actions", [])
        for action in actions:
            action_id = action.get("action_id", "")
            value = action.get("value", "")

            if action_id == "save_event":
                return {
                    "response_type": "ephemeral",
                    "text": f"Event saved! We'll remind you when it's coming up.",
                }
            elif action_id == "dismiss_event":
                return {
                    "response_type": "ephemeral",
                    "text": "Got it, we'll show you fewer events like this.",
                }
            elif action_id == "more_events":
                return {
                    "response_type": "ephemeral",
                    "text": "Loading more events...",
                }

    return {"response_type": "ephemeral", "text": "Action received!"}


def _tonight_response(city: str) -> dict:
    """Build response for /bubbaroo tonight."""
    return {
        "response_type": "in_channel",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Tonight in {city}"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Searching for events in {city} tonight...\n"
                        "_Results will appear shortly. "
                        "Use the web app for the full experience!_"
                    ),
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Powered by BubbaRoo Events",
                    }
                ],
            },
        ],
    }


def _recommend_response(city: str) -> dict:
    """Build response for /bubbaroo recommend."""
    return {
        "response_type": "ephemeral",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Recommended for You in {city}"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "Fetching your personalized recommendations...\n"
                        "_Based on your interests and past interactions._"
                    ),
                },
            },
        ],
    }


def _search_response(query: str) -> dict:
    """Build response for /bubbaroo search."""
    if not query:
        return {
            "response_type": "ephemeral",
            "text": "Usage: `/bubbaroo search <query>`\nExample: `/bubbaroo search jazz concerts`",
        }

    return {
        "response_type": "ephemeral",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Searching for *{query}*...",
                },
            },
        ],
    }


def _trip_response(args: str) -> dict:
    """Build response for /bubbaroo trip."""
    if not args:
        return {
            "response_type": "ephemeral",
            "text": (
                "Usage: `/bubbaroo trip <city> <dates>`\n"
                "Example: `/bubbaroo trip Denver March 15-17`"
            ),
        }

    return {
        "response_type": "ephemeral",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Planning your trip: *{args}*\n_Searching for events..._",
                },
            },
        ],
    }


def _help_response() -> dict:
    """Build help response."""
    return {
        "response_type": "ephemeral",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "BubbaRoo Events"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "*Available commands:*\n\n"
                        "`/bubbaroo tonight [city]` - What's happening tonight\n"
                        "`/bubbaroo recommend [city]` - Personalized event picks\n"
                        "`/bubbaroo search <query>` - Search for events\n"
                        "`/bubbaroo trip <city> <dates>` - Plan a trip\n"
                        "`/bubbaroo help` - Show this message"
                    ),
                },
            },
        ],
    }


def build_event_blocks(events: list[dict]) -> list[dict]:
    """Build Slack Block Kit blocks for a list of events.

    Reusable by any Slack response that needs to render events.
    """
    blocks: list[dict] = []

    for event in events[:5]:
        title = event.get("title", "Untitled")
        venue = event.get("venue_name", "TBD")
        date = event.get("starts_at", "TBD")
        price_min = event.get("price_min")
        price_str = "Free" if price_min == 0 else f"${price_min}+" if price_min else "TBD"
        url = event.get("url", "")
        image_url = event.get("image_url")
        score = event.get("score")

        text = f"*{title}*\n{date} at {venue}\nPrice: {price_str}"
        if score is not None:
            text += f" | Match: {int(score * 100)}%"

        section: dict = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": text},
        }
        if image_url:
            section["accessory"] = {
                "type": "image",
                "image_url": image_url,
                "alt_text": title,
            }
        blocks.append(section)

        # Action buttons
        elements = []
        if url:
            elements.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "Get Tickets"},
                "url": url,
                "style": "primary",
            })
        elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Save"},
            "action_id": "save_event",
            "value": event.get("id", ""),
        })
        elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Not for me"},
            "action_id": "dismiss_event",
            "value": event.get("id", ""),
        })

        blocks.append({"type": "actions", "elements": elements})
        blocks.append({"type": "divider"})

    return blocks
