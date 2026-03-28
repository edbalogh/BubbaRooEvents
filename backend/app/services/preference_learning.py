"""Advanced preference learning with time decay and confidence scoring.

Enhances the basic weight-update approach with:
1. Time decay - older interactions have less influence
2. Confidence scoring - more interactions = more confident weights
3. Exploration bonus - slight boost to underexplored categories
4. Periodic recomputation via Celery task
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.event import EventCategory
from app.models.interaction import UserEventInteraction
from app.models.user import User, UserPreference

# Interaction weights (how much each type contributes)
INTERACTION_WEIGHTS = {
    "attended": 1.0,
    "saved": 0.7,
    "clicked": 0.3,
    "viewed": 0.05,
    "dismissed": -0.5,
}

# Time decay: half-life in days (interactions lose half their weight after this many days)
HALF_LIFE_DAYS = 60

# Minimum interactions for a "confident" weight
CONFIDENCE_THRESHOLD = 5


def _time_decay_factor(interaction_date: datetime, now: datetime) -> float:
    """Exponential decay based on age of interaction."""
    age_days = (now - interaction_date).total_seconds() / 86400
    return math.pow(0.5, age_days / HALF_LIFE_DAYS)


async def recompute_user_preferences(db: AsyncSession, user: User) -> dict[int, float]:
    """Recompute all category weights for a user from interaction history.

    Uses time-decayed interaction weights to build a preference profile.
    Returns {category_id: new_weight} dict.
    """
    now = datetime.now(UTC)

    # Fetch all interactions with their event categories and timestamps
    result = await db.execute(
        select(
            UserEventInteraction.interaction,
            UserEventInteraction.created_at,
            EventCategory.category_id,
        )
        .join(EventCategory, UserEventInteraction.event_id == EventCategory.event_id)
        .where(UserEventInteraction.user_id == user.id)
        .order_by(UserEventInteraction.created_at.desc())
    )
    rows = result.all()

    if not rows:
        return {}

    # Accumulate weighted scores per category
    category_scores: dict[int, float] = {}
    category_counts: dict[int, int] = {}

    for interaction_type, created_at, category_id in rows:
        weight = INTERACTION_WEIGHTS.get(interaction_type, 0)
        if weight == 0:
            continue

        decay = _time_decay_factor(created_at, now)
        weighted_score = weight * decay

        category_scores[category_id] = category_scores.get(category_id, 0) + weighted_score
        category_counts[category_id] = category_counts.get(category_id, 0) + 1

    # Get all categories for exploration bonus
    all_cats_result = await db.execute(select(Category.id))
    all_cat_ids = {row.id for row in all_cats_result.all()}

    # Normalize and apply confidence
    new_weights: dict[int, float] = {}

    for cat_id in all_cat_ids:
        raw_score = category_scores.get(cat_id, 0)
        count = category_counts.get(cat_id, 0)

        if count == 0:
            # Exploration bonus: slightly above neutral for unexplored categories
            new_weights[cat_id] = 1.1
            continue

        # Confidence factor: sigmoid approaching 1.0 as interactions increase
        confidence = 1.0 / (1.0 + math.exp(-0.5 * (count - CONFIDENCE_THRESHOLD)))

        # Scale raw score to [-1, 5] range
        # Raw scores typically range from about -5 to +10 depending on activity
        normalized = max(-1.0, min(5.0, raw_score))

        # Blend with neutral (1.0) based on confidence
        blended = confidence * normalized + (1 - confidence) * 1.0

        new_weights[cat_id] = round(blended, 3)

    # Update database
    for cat_id, weight in new_weights.items():
        existing = await db.execute(
            select(UserPreference)
            .where(UserPreference.user_id == user.id, UserPreference.category_id == cat_id)
        )
        pref = existing.scalar_one_or_none()

        if pref:
            pref.weight = weight
        else:
            db.add(UserPreference(user_id=user.id, category_id=cat_id, weight=weight))

    await db.flush()
    return new_weights


async def recompute_all_user_preferences(db: AsyncSession) -> int:
    """Recompute preferences for all users. Run periodically via Celery."""
    result = await db.execute(select(User))
    users = result.scalars().all()

    updated = 0
    for user in users:
        weights = await recompute_user_preferences(db, user)
        if weights:
            updated += 1

    await db.commit()
    return updated


async def get_preference_stats(db: AsyncSession, user_id: UUID) -> dict:
    """Get preference learning stats for a user (useful for debugging/display)."""
    # Count total interactions
    interaction_count = await db.execute(
        select(func.count())
        .select_from(UserEventInteraction)
        .where(UserEventInteraction.user_id == user_id)
    )
    total = interaction_count.scalar() or 0

    # Count by type
    type_counts = await db.execute(
        select(
            UserEventInteraction.interaction,
            func.count().label("count"),
        )
        .where(UserEventInteraction.user_id == user_id)
        .group_by(UserEventInteraction.interaction)
    )

    # Get top categories
    top_prefs = await db.execute(
        select(Category.name, UserPreference.weight)
        .join(Category, UserPreference.category_id == Category.id)
        .where(UserPreference.user_id == user_id)
        .order_by(UserPreference.weight.desc())
        .limit(5)
    )

    return {
        "total_interactions": total,
        "interactions_by_type": {row.interaction: row.count for row in type_counts.all()},
        "top_categories": [
            {"name": row.name, "weight": round(row.weight, 2)}
            for row in top_prefs.all()
        ],
        "confidence": "high" if total >= 20 else "medium" if total >= 5 else "low",
    }
