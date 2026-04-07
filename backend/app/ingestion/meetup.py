"""Meetup.com ingestion adapter — DISABLED.

Meetup killed their public GraphQL API in 2023. Access now requires a paid
Pro account with OAuth. Until we have a Pro account or a replacement source,
this adapter returns empty and logs a single warning on startup.
"""

from __future__ import annotations

import logging
from datetime import date

from app.ingestion.base import NormalizedEvent

logger = logging.getLogger(__name__)


class MeetupAdapter:
    source_name = "meetup"
    _warned = False

    async def fetch_events(
        self, city: str, date_from: date, date_to: date,
        lat: float = 30.27, lon: float = -97.74,
    ) -> list[NormalizedEvent]:
        if not MeetupAdapter._warned:
            logger.warning(
                "Meetup adapter disabled: their public API was shut down in 2023. "
                "A paid Pro account is required. Returning empty."
            )
            MeetupAdapter._warned = True
        return []
