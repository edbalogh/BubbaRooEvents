"""LLM-powered tools for source discovery and event extraction."""

from __future__ import annotations

import json
import logging

from app.services.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

_SCORE_SYSTEM = (
    "You are evaluating URLs to find local event calendars. "
    "Score each URL 0.0-1.0 on how likely it is to be a city-specific event calendar. "
    "Penalize: national ticket resellers (Ticketmaster, StubHub, Vivid Seats), social media, "
    "news sites without event sections. "
    "Reward: city/neighborhood event listings, local venue calendars, "
    "arts council sites, parks & rec calendars, local newspapers with events sections."
)

_CONFIRM_SYSTEM = (
    "You analyze web page content to determine if it is a local event listing site."
)

_EXTRACT_SYSTEM = (
    "You extract structured event data from web page content. "
    "Return only events you are confident about. Do not invent data."
)


def _parse_json(raw: str) -> list | dict | None:
    """Try to parse JSON from LLM output. Returns None if unparseable."""
    raw = raw.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def score_source_candidates(
    llm: LLMProvider,
    city: str,
    candidates: list[dict],
    threshold: float = 0.7,
) -> list[dict]:
    """
    Score a list of {url, snippet} candidates for likelihood of being a local event calendar.
    Returns candidates with score >= threshold.
    """
    if not candidates:
        return []

    candidate_text = "\n".join(
        f"- URL: {c['url']}\n  Snippet: {c.get('snippet', '')}" for c in candidates
    )
    user_prompt = (
        f"Score these URLs for {city}. "
        f"Return ONLY a JSON array: "
        f'[{{"url": "...", "score": 0.0, "reason": "..."}}]\n\n{candidate_text}'
    )

    raw = await llm.complete(_SCORE_SYSTEM, user_prompt, max_tokens=1000)
    parsed = _parse_json(raw)

    if parsed is None:
        # Retry with stricter prompt
        strict_prompt = user_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON array. No explanation."
        raw = await llm.complete(_SCORE_SYSTEM, strict_prompt, max_tokens=1000)
        parsed = _parse_json(raw)

    if not isinstance(parsed, list):
        logger.warning(f"[discovery] score_source_candidates: could not parse LLM response for {city}")
        return []

    return [item for item in parsed if isinstance(item, dict) and item.get("score", 0) >= threshold]


async def confirm_source(llm: LLMProvider, markdown: str) -> dict:
    """
    Confirm whether a page is a local event site.
    Returns dict with keys: is_event_site, site_name, event_count_estimate, city.
    """
    user_prompt = (
        "Does this page list local events with dates and times? "
        'Return ONLY JSON: {"is_event_site": bool, "site_name": "str", '
        '"event_count_estimate": int, "city": "str"}\n\n'
        f"Page content (first 3000 chars):\n{markdown[:3000]}"
    )

    raw = await llm.complete(_CONFIRM_SYSTEM, user_prompt, max_tokens=200)
    parsed = _parse_json(raw)

    if not isinstance(parsed, dict):
        strict_prompt = user_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON object. No explanation."
        raw = await llm.complete(_CONFIRM_SYSTEM, strict_prompt, max_tokens=200)
        parsed = _parse_json(raw)

    if not isinstance(parsed, dict):
        logger.warning("[discovery] confirm_source: could not parse LLM response")
        return {"is_event_site": False, "site_name": "", "event_count_estimate": 0, "city": None}

    return parsed


async def extract_events_from_markdown(
    llm: LLMProvider,
    markdown: str,
    source_url: str,
) -> list[dict]:
    """
    Extract events from page markdown. Returns list of raw event dicts.
    Each dict has: title, date, time, venue, address, price, url, description.
    """
    user_prompt = (
        "Extract all events from this page. "
        "Return ONLY a JSON array: "
        '[{"title": "str", "date": "YYYY-MM-DD", "time": "HH:MM", '
        '"venue": "str", "address": "str", "price": "str", '
        '"url": "str", "description": "str"}]. '
        "Use null for missing fields. Only include events with at least a title and date.\n\n"
        f"Source URL: {source_url}\n\n"
        f"Page content (first 6000 chars):\n{markdown[:6000]}"
    )

    raw = await llm.complete(_EXTRACT_SYSTEM, user_prompt, max_tokens=2000)
    parsed = _parse_json(raw)

    if parsed is None:
        strict_prompt = user_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON array. No explanation."
        raw = await llm.complete(_EXTRACT_SYSTEM, strict_prompt, max_tokens=2000)
        parsed = _parse_json(raw)

    if not isinstance(parsed, list):
        logger.warning(f"[discovery] extract_events: could not parse LLM response for {source_url}")
        return []

    return [item for item in parsed if isinstance(item, dict) and item.get("title") and item.get("date")]
