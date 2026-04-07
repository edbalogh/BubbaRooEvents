"""Eventbrite ingestion adapter — DISABLED.

Eventbrite permanently removed public location-based event search in February
2020. The /v3/events/search/ endpoint returns 404. No replacement was provided.
The remaining v3 endpoints are org/venue/event-ID-scoped (not useful for
discovery). Returning empty.
"""

from __future__ import annotations

import logging
from datetime import date

from app.ingestion.base import NormalizedEvent

logger = logging.getLogger(__name__)


class EventbriteAdapter:
    source_name = "eventbrite"
    _warned = False

    async def fetch_events(
        self, city: str, date_from: date, date_to: date,
        lat: float = 30.27, lon: float = -97.74,
    ) -> list[NormalizedEvent]:
        if not EventbriteAdapter._warned:
            logger.warning(
                "Eventbrite adapter disabled: location-based search API was "
                "permanently removed in 2020. No public replacement exists. "
                "Returning empty."
            )
            EventbriteAdapter._warned = True
        return []
