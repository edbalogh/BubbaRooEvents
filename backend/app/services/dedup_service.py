"""Venue resolution and cross-source event deduplication."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from thefuzz import fuzz

from app.services.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

# Source priority for field selection (lower index = higher priority).
# Sources not in this list (unknown local venues) rank at the same tier as
# "scraper" — i.e., they beat national ticket APIs but not explicit venue sources.
_SOURCE_PRIORITY = [
    "venue",        # any source containing "venue" has highest priority
    "scraper",      # local scrapers over national APIs
    "ticketmaster",
    "eventbrite",
    "meetup",
    "seatgeek",
    "bandsintown",
    "discovered",
]

# Rank assigned to unknown sources (local venue sites, etc.) — same tier as
# "scraper", so unknown local sources beat national APIs like Ticketmaster.
_UNKNOWN_SOURCE_RANK = 1  # same index as "scraper" in _SOURCE_PRIORITY

# Fields where "longest wins" instead of source priority
_LONGEST_WINS_FIELDS = {"description", "title"}


def make_venue_slug(name: str, city: str) -> str:
    """Create a unique slug for a venue from its name and city."""
    combined = f"{name}-{city}".lower()
    combined = re.sub(r"[^a-z0-9\s-]", "", combined)
    combined = re.sub(r"\s+", "-", combined.strip())
    combined = re.sub(r"-+", "-", combined)
    return combined[:350]


def fuzzy_match_venue_name(
    name: str,
    city: str,
    candidates: list[dict],
    threshold: int = 85,
) -> dict | None:
    """
    Find the best matching venue from candidates using fuzzy string matching.
    Only matches within the same city. Returns None if no match above threshold.
    """
    best_score = 0
    best_match = None

    for candidate in candidates:
        if candidate.get("city", "").lower() != city.lower():
            continue
        score = fuzz.token_sort_ratio(name.lower(), candidate["name"].lower())
        if score > best_score and score >= threshold:
            best_score = score
            best_match = candidate

    return best_match


def _source_rank(source: str) -> int:
    """Lower number = higher priority. Unknown sources (local venue sites) rank
    above national aggregators like Ticketmaster."""
    source_lower = source.lower()
    for i, keyword in enumerate(_SOURCE_PRIORITY):
        if keyword in source_lower:
            return i
    # Unknown source: treat as a local/direct venue source, higher priority
    # than national aggregators.
    return _UNKNOWN_SOURCE_RANK


def pick_best_field(field_name: str, values: list[dict]) -> Any:
    """
    Pick the best value for a field from multiple source values.
    For description/title: pick the longest non-null value.
    For everything else: pick by source priority order.
    """
    non_null = [v for v in values if v.get("value") is not None]
    if not non_null:
        return None

    if field_name in _LONGEST_WINS_FIELDS:
        return max(non_null, key=lambda v: len(str(v["value"])))["value"]

    return min(non_null, key=lambda v: _source_rank(v["source"]))["value"]


def merge_canonical_event_fields(raw_events: list[dict]) -> dict:
    """
    Merge fields from multiple raw event dicts into a single canonical event.
    Returns dict with merged fields plus 'conflicts' and 'field_sources' metadata.
    """
    fields = ["title", "description", "price_min", "price_max", "currency",
              "url", "image_url", "starts_at", "ends_at"]

    merged: dict = {}
    conflicts: dict = {}
    field_sources: dict = {}

    for field in fields:
        values = [
            {"source": e["source"], "value": e.get(field)}
            for e in raw_events
            if e.get(field) is not None
        ]
        if not values:
            merged[field] = None
            continue

        best = pick_best_field(field, values)
        merged[field] = best

        winner_source = next(
            (v["source"] for v in values if v["value"] == best), values[0]["source"]
        )
        field_sources[field] = winner_source

        # Record conflicts (values that differ from the winner)
        differing = [v for v in values if v["value"] != best]
        if differing:
            conflicts[field] = [{"source": winner_source, "value": best}] + [
                {"source": v["source"], "value": v["value"]} for v in differing
            ]

    merged["conflicts"] = conflicts if conflicts else None
    merged["field_sources"] = field_sources if field_sources else None
    return merged


async def are_duplicate_events(
    llm: LLMProvider,
    event_a: dict,
    event_b: dict,
    confidence_threshold: float = 0.8,
) -> bool:
    """
    Use LLM to determine if two events are the same real-world event.
    Used when fuzzy venue match alone is ambiguous.
    """
    system = "You determine if two event listings describe the same real-world event."
    user = (
        "Are these two event listings the same real-world event? "
        "Venue names may differ slightly. "
        'Return ONLY JSON: {"is_duplicate": bool, "confidence": 0.0, "reason": "str"}\n\n'
        f"Event A: {json.dumps(event_a)}\n\nEvent B: {json.dumps(event_b)}"
    )

    try:
        raw = await llm.complete(system, user, max_tokens=200)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        return (
            result.get("is_duplicate", False) is True
            and result.get("confidence", 0) >= confidence_threshold
        )
    except Exception as e:
        logger.warning(f"[dedup] LLM duplicate check failed: {type(e).__name__}: {e}")
        return False
