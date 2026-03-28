"""AI-powered services using Claude API.

Provides recommendation explanations and trip planning through
natural language generation.
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-20250514"


async def _call_claude(system_prompt: str, user_message: str, max_tokens: int = 500) -> str | None:
    """Make a request to the Claude API."""
    api_key = getattr(settings, "anthropic_api_key", "")
    if not api_key:
        logger.warning("Anthropic API key not configured, skipping AI call")
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                CLAUDE_API_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": MODEL,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_message}],
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]
    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        return None


async def explain_recommendation(
    event_title: str,
    event_description: str | None,
    event_categories: list[str],
    event_venue: str | None,
    event_city: str | None,
    event_date: str | None,
    event_price_min: float | None,
    score: float,
    score_breakdown: dict,
    user_top_categories: list[str],
) -> str:
    """Generate a natural language explanation of why an event was recommended.

    Falls back to a template-based explanation if Claude API is unavailable.
    """
    system_prompt = (
        "You are a friendly events concierge for BubbaRoo Events. "
        "Explain in 2-3 sentences why this event is a great match for the user. "
        "Be enthusiastic but genuine. Reference specific details about the event "
        "and the user's interests. Don't mention scores or numbers."
    )

    user_message = f"""Event: {event_title}
Description: {event_description or 'N/A'}
Categories: {', '.join(event_categories) if event_categories else 'General'}
Venue: {event_venue or 'TBD'}
City: {event_city or 'N/A'}
Date: {event_date or 'TBD'}
Price: {'Free' if event_price_min == 0 else f'${event_price_min}+' if event_price_min else 'TBD'}

User's favorite categories: {', '.join(user_top_categories) if user_top_categories else 'Still learning'}

Match signals:
- Category match strength: {score_breakdown.get('category_affinity', 0):.0%}
- Taste similarity: {score_breakdown.get('embedding_similarity', 0):.0%}
- Popularity: {score_breakdown.get('popularity', 0):.0%}
- Overall match: {score:.0%}

Explain why this event is a great fit for this user."""

    result = await _call_claude(system_prompt, user_message)
    if result:
        return result

    # Fallback: template-based explanation
    return _template_explanation(
        event_title, event_categories, event_city, score, score_breakdown, user_top_categories,
    )


def _template_explanation(
    title: str,
    categories: list[str],
    city: str | None,
    score: float,
    breakdown: dict,
    user_categories: list[str],
) -> str:
    """Generate a simple template explanation when Claude API is unavailable."""
    parts = []

    cat_score = breakdown.get("category_affinity", 0)
    if cat_score > 0.5 and categories:
        matching = [c for c in categories if c.lower() in [uc.lower() for uc in user_categories]]
        if matching:
            parts.append(f"This matches your interest in {matching[0].lower()} events.")
        else:
            parts.append(f"This {categories[0].lower()} event fits your taste profile.")

    embed_score = breakdown.get("embedding_similarity", 0)
    if embed_score > 0.4:
        parts.append("It's similar to events you've liked before.")

    pop_score = breakdown.get("popularity", 0)
    if pop_score > 0.5:
        parts.append("It's trending with other users in your area.")

    if not parts:
        parts.append(f"We think you'll enjoy {title}!")

    if city:
        parts.append(f"Happening in {city}.")

    return " ".join(parts)


async def plan_trip(
    destination_city: str,
    travel_dates: str,
    interests: list[str],
    events_context: list[dict],
) -> str:
    """Generate an AI-powered trip plan based on available events.

    Args:
        destination_city: City the user is visiting
        travel_dates: Date range description (e.g., "March 15-17")
        interests: User's interest categories
        events_context: List of event dicts available during the trip
    """
    system_prompt = (
        "You are a friendly trip planning assistant for BubbaRoo Events. "
        "Help users plan an amazing trip by suggesting which events to attend "
        "and how to structure their time. Be specific about event details. "
        "Suggest a rough itinerary if multiple days. Keep it concise and fun. "
        "Use the events provided - don't make up events that aren't in the list."
    )

    events_text = ""
    for i, e in enumerate(events_context[:15], 1):
        price = "Free" if e.get("price_min") == 0 else f"${e.get('price_min', '?')}+" if e.get("price_min") else "TBD"
        events_text += (
            f"{i}. {e['title']}\n"
            f"   Date: {e.get('date', 'TBD')} | Venue: {e.get('venue', 'TBD')} | Price: {price}\n"
            f"   {e.get('description', '')[:150]}\n\n"
        )

    user_message = f"""I'm planning a trip to {destination_city} during {travel_dates}.

My interests: {', '.join(interests) if interests else 'Open to anything!'}

Here are the events happening during my trip:

{events_text if events_text else 'No events found for these dates yet.'}

Please suggest which events I should attend and help me plan my time there."""

    result = await _call_claude(system_prompt, user_message, max_tokens=1000)
    if result:
        return result

    # Fallback
    if not events_context:
        return (
            f"We don't have many events listed in {destination_city} for {travel_dates} yet. "
            "Check back closer to your trip dates as new events are added daily!"
        )

    lines = [f"Here are the top events in {destination_city} during {travel_dates}:\n"]
    for i, e in enumerate(events_context[:5], 1):
        lines.append(f"{i}. **{e['title']}**")
        if e.get("date"):
            lines.append(f"   {e['date']} at {e.get('venue', 'TBD')}")
        lines.append("")

    lines.append("Tip: Save the ones you like and we'll remind you when tickets go on sale!")
    return "\n".join(lines)
