"""
Embedding generation for events using sentence-transformers.

Uses all-MiniLM-L6-v2 (384 dimensions) to create semantic vectors
from event title + description + categories + venue + city.

The pgvector extension stores these in the events.embedding column
for cosine similarity search.

NOTE: sentence-transformers is an optional dependency. If not installed,
the embedding pipeline gracefully skips (logged as a warning).
"""

from __future__ import annotations

import logging

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import RawEvent

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Lazy-loaded model singleton
_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(MODEL_NAME)
            logger.info(f"Loaded embedding model: {MODEL_NAME}")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            return None
    return _model


def build_embedding_text(event: RawEvent) -> str:
    """Build the text string to embed for an event."""
    parts = [event.title]
    if event.description:
        parts.append(event.description[:500])  # truncate long descriptions
    if event.venue_name:
        parts.append(f"at {event.venue_name}")
    if event.city:
        parts.append(f"in {event.city}")
        if event.state:
            parts.append(event.state)
    return " ".join(parts)


async def generate_embeddings_batch(db: AsyncSession, batch_size: int = 100) -> int:
    """
    Generate embeddings for events that don't have them yet.
    Returns the number of events processed.
    """
    model = _get_model()
    if model is None:
        return 0

    # Find events without embeddings
    # We use raw SQL to check for NULL on the vector column
    result = await db.execute(
        select(RawEvent)
        .where(text("embedding IS NULL"))
        .where(RawEvent.status == "active")
        .limit(batch_size)
    )
    events = list(result.scalars().all())

    if not events:
        return 0

    # Build texts and generate embeddings
    texts = [build_embedding_text(e) for e in events]
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    # Store embeddings
    for event, vector in zip(events, vectors):
        vector_list = vector.tolist()
        await db.execute(
            text(
                "UPDATE raw_events SET embedding = :vec WHERE id = :event_id"
            ).bindparams(
                vec=str(vector_list),
                event_id=str(event.id),
            )
        )

    await db.commit()
    logger.info(f"Generated embeddings for {len(events)} events")
    return len(events)


async def compute_user_taste_vector(
    db: AsyncSession, user_id, limit: int = 50
) -> list[float] | None:
    """
    Compute a user's taste vector as the weighted average of embeddings
    from events they've interacted positively with (saved, clicked, attended).

    Returns a 384-dim vector or None if insufficient data.
    """
    from app.models.interaction import UserEventInteraction

    # Get recent positive interactions
    result = await db.execute(
        text("""
            SELECT e.embedding
            FROM user_event_interactions uei
            JOIN raw_events e ON e.id = uei.event_id
            WHERE uei.user_id = :user_id
              AND uei.interaction IN ('saved', 'clicked', 'attended')
              AND e.embedding IS NOT NULL
            ORDER BY uei.created_at DESC
            LIMIT :limit
        """).bindparams(user_id=str(user_id), limit=limit)
    )

    rows = result.all()
    if not rows:
        return None

    # Average the vectors
    import numpy as np
    vectors = []
    for row in rows:
        if row[0] is not None:
            vectors.append(row[0])

    if not vectors:
        return None

    avg = np.mean(vectors, axis=0)
    # Normalize
    norm = np.linalg.norm(avg)
    if norm > 0:
        avg = avg / norm

    return avg.tolist()
