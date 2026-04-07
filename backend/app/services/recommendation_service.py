"""Recommendation engine combining category affinity, embedding similarity, and popularity."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.event import EventCategory, RawEvent
from app.models.interaction import UserEventInteraction, UserSavedEvent
from app.models.user import User, UserPreference

# Tunable weights for the scoring model
W_CATEGORY = 0.4
W_EMBEDDING = 0.3
W_POPULARITY = 0.2
DISTANCE_DECAY_FACTOR = 0.1  # penalty per mile beyond preferred radius


@dataclass
class ScoredEvent:
    event: RawEvent
    score: float
    category_affinity: float = 0.0
    embedding_similarity: float = 0.0
    popularity: float = 0.0
    distance_penalty: float = 0.0
    categories: list[str] | None = None


async def get_user_category_weights(db: AsyncSession, user_id: UUID) -> dict[int, float]:
    """Get the user's category preference weights as {category_id: weight}."""
    result = await db.execute(
        select(UserPreference.category_id, UserPreference.weight)
        .where(UserPreference.user_id == user_id)
    )
    return {row.category_id: row.weight for row in result.all()}


async def get_event_categories(db: AsyncSession, event_ids: list[UUID]) -> dict[UUID, list[str]]:
    """Get category names for a batch of events."""
    if not event_ids:
        return {}

    result = await db.execute(
        select(EventCategory.event_id, Category.name, Category.slug)
        .join(Category, EventCategory.category_id == Category.id)
        .where(EventCategory.event_id.in_(event_ids))
    )

    event_cats: dict[UUID, list[str]] = {}
    for row in result.all():
        event_cats.setdefault(row.event_id, []).append(row.slug)
    return event_cats


async def get_event_category_ids(db: AsyncSession, event_ids: list[UUID]) -> dict[UUID, list[int]]:
    """Get category IDs for a batch of events."""
    if not event_ids:
        return {}

    result = await db.execute(
        select(EventCategory.event_id, EventCategory.category_id)
        .where(EventCategory.event_id.in_(event_ids))
    )

    event_cat_ids: dict[UUID, list[int]] = {}
    for row in result.all():
        event_cat_ids.setdefault(row.event_id, []).append(row.category_id)
    return event_cat_ids


async def get_popularity_scores(db: AsyncSession, event_ids: list[UUID]) -> dict[UUID, float]:
    """Get popularity scores based on saves and clicks across all users."""
    if not event_ids:
        return {}

    # Count positive interactions (saved, clicked, attended)
    result = await db.execute(
        select(
            UserEventInteraction.event_id,
            func.count().label("interaction_count"),
        )
        .where(
            UserEventInteraction.event_id.in_(event_ids),
            UserEventInteraction.interaction.in_(["saved", "clicked", "attended"]),
        )
        .group_by(UserEventInteraction.event_id)
    )

    raw_scores = {row.event_id: row.interaction_count for row in result.all()}
    if not raw_scores:
        return {eid: 0.0 for eid in event_ids}

    # Normalize to 0-1 range
    max_score = max(raw_scores.values()) if raw_scores else 1
    return {
        eid: raw_scores.get(eid, 0) / max(max_score, 1)
        for eid in event_ids
    }


def calculate_distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine formula to calculate distance in miles."""
    R = 3959  # Earth's radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def compute_distance_penalty(
    event: RawEvent, user: User, max_distance: float = 25.0
) -> float:
    """Returns a penalty (negative value) for events beyond the user's preferred radius."""
    if not (user.home_latitude and user.home_longitude and event.latitude and event.longitude):
        return 0.0

    distance = calculate_distance_miles(
        user.home_latitude, user.home_longitude,
        event.latitude, event.longitude,
    )

    if distance <= max_distance:
        return 0.0

    # Gradual penalty beyond preferred radius
    overshoot = distance - max_distance
    return -min(overshoot * DISTANCE_DECAY_FACTOR, 1.0)


async def get_dismissed_event_ids(db: AsyncSession, user_id: UUID) -> set[UUID]:
    """Get IDs of events the user has dismissed."""
    result = await db.execute(
        select(UserEventInteraction.event_id)
        .where(
            UserEventInteraction.user_id == user_id,
            UserEventInteraction.interaction == "dismissed",
        )
    )
    return {row.event_id for row in result.all()}


async def get_user_source_preferences(db: AsyncSession, user_id: UUID) -> dict[str, str]:
    """Get user source preferences as {source_slug: preference}.

    Returns dict like {"ticketmaster": "liked", "meetup": "disabled"}.
    """
    from app.models.source import EventSource, UserSourcePreference

    result = await db.execute(
        select(EventSource.slug, UserSourcePreference.preference)
        .join(EventSource, UserSourcePreference.source_id == EventSource.id)
        .where(UserSourcePreference.user_id == user_id)
    )
    return {row.slug: row.preference for row in result.all()}


# Source preference modifiers for scoring
SOURCE_PREF_MODIFIERS = {
    "liked": 0.15,      # boost liked sources
    "disliked": -0.15,   # reduce disliked sources
    "disabled": None,    # filter out entirely
    # "neutral" = no modifier (not stored in DB)
}


async def recommend_events(
    db: AsyncSession,
    user: User,
    city: str | None = None,
    limit: int = 20,
    max_distance_miles: float = 25.0,
) -> list[ScoredEvent]:
    """
    Generate personalized event recommendations using four signals:
    1. Category affinity (user preference weights)
    2. Embedding similarity (placeholder until embeddings are generated)
    3. Popularity (cross-user interaction counts)
    4. Source preference (liked/disliked/disabled sources)
    + Distance penalty
    """
    # Fetch candidate events (active, upcoming)
    query = (
        select(RawEvent)
        .where(RawEvent.status == "active", RawEvent.starts_at > datetime.now(UTC))
        .order_by(RawEvent.starts_at.asc())
        .limit(200)  # candidate pool
    )

    if city:
        query = query.where(func.lower(RawEvent.city) == city.lower())

    result = await db.execute(query)
    candidates = list(result.scalars().all())

    if not candidates:
        return []

    # Filter out dismissed events
    dismissed = await get_dismissed_event_ids(db, user.id)
    candidates = [e for e in candidates if e.id not in dismissed]

    # Filter out events from disabled sources
    source_prefs = await get_user_source_preferences(db, user.id)
    disabled_sources = {slug for slug, pref in source_prefs.items() if pref == "disabled"}
    if disabled_sources:
        candidates = [e for e in candidates if e.source not in disabled_sources]

    event_ids = [e.id for e in candidates]

    # Batch-fetch supporting data
    user_weights = await get_user_category_weights(db, user.id)
    event_cat_ids = await get_event_category_ids(db, event_ids)
    event_cats = await get_event_categories(db, event_ids)
    popularity = await get_popularity_scores(db, event_ids)

    # Score each event
    scored: list[ScoredEvent] = []
    for event in candidates:
        # Signal 1: Category affinity
        cat_ids = event_cat_ids.get(event.id, [])
        if cat_ids and user_weights:
            cat_score = sum(user_weights.get(cid, 0.0) for cid in cat_ids) / len(cat_ids)
            # Normalize: weights range from -1 to ~5, map to 0-1
            cat_score = max(0.0, min(cat_score / 3.0, 1.0))
        else:
            cat_score = 0.5  # neutral for new users (cold start)

        # Signal 2: Embedding similarity (placeholder - returns 0.5 until embeddings are generated)
        embedding_score = 0.5

        # Signal 3: Popularity
        pop_score = popularity.get(event.id, 0.0)

        # Distance penalty
        dist_penalty = compute_distance_penalty(event, user, max_distance_miles)

        # Signal 4: Source preference modifier
        source_modifier = 0.0
        source_pref = source_prefs.get(event.source)
        if source_pref and source_pref in SOURCE_PREF_MODIFIERS:
            mod = SOURCE_PREF_MODIFIERS[source_pref]
            if mod is not None:
                source_modifier = mod

        # Combined score
        total = (
            W_CATEGORY * cat_score
            + W_EMBEDDING * embedding_score
            + W_POPULARITY * pop_score
            + dist_penalty
            + source_modifier
        )

        scored.append(ScoredEvent(
            event=event,
            score=round(total, 4),
            category_affinity=round(cat_score, 4),
            embedding_similarity=round(embedding_score, 4),
            popularity=round(pop_score, 4),
            distance_penalty=round(dist_penalty, 4),
            categories=event_cats.get(event.id, []),
        ))

    # Sort by score descending
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:limit]


async def update_preference_from_interaction(
    db: AsyncSession, user_id: UUID, event_id: UUID, interaction: str
) -> None:
    """Auto-adjust user preference weights based on interactions."""
    WEIGHT_DELTAS = {
        "saved": 0.15,
        "clicked": 0.1,
        "attended": 0.25,
        "dismissed": -0.1,
        "viewed": 0.02,
    }

    delta = WEIGHT_DELTAS.get(interaction, 0.0)
    if delta == 0.0:
        return

    # Get categories for this event
    result = await db.execute(
        select(EventCategory.category_id).where(EventCategory.event_id == event_id)
    )
    cat_ids = [row.category_id for row in result.all()]

    for cat_id in cat_ids:
        # Upsert preference
        existing = await db.execute(
            select(UserPreference)
            .where(UserPreference.user_id == user_id, UserPreference.category_id == cat_id)
        )
        pref = existing.scalar_one_or_none()

        if pref:
            pref.weight = max(-1.0, min(5.0, pref.weight + delta))  # clamp to [-1, 5]
        else:
            pref = UserPreference(
                user_id=user_id,
                category_id=cat_id,
                weight=max(-1.0, min(5.0, 1.0 + delta)),  # start at 1.0 + delta
            )
            db.add(pref)

    await db.flush()
