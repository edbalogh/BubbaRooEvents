"""AI-powered services using local Ollama models.

Provides recommendation explanations and trip planning through
natural language generation. Errors propagate — no silent fallbacks.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.llm_provider import OllamaProvider

_recommend_provider = OllamaProvider(
    base_url=settings.ollama_base_url,
    model=settings.ollama_recommend_model,
)

_trip_provider = OllamaProvider(
    base_url=settings.ollama_base_url,
    model=settings.ollama_trip_model,
)


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
    """Generate a natural language explanation of why an event was recommended."""
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

    return await _recommend_provider.complete(system_prompt, user_message, max_tokens=500)


async def plan_trip(
    destination_city: str,
    travel_dates: str,
    interests: list[str],
    events_context: list[dict],
) -> str:
    """Generate an AI-powered trip plan based on available events."""
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

    return await _trip_provider.complete(system_prompt, user_message, max_tokens=1000)
