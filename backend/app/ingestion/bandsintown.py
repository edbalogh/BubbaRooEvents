"""Bandsintown ingestion adapter — DISABLED.

Bandsintown's location-based event search (the /artists/events endpoint with
lat/lon) now returns 403. Their API is artist-centric and requires a partnership
key for location browsing. Returning empty until we have a viable replacement
for local live music discovery.
"""

from __future__ import annotations

import logging
from datetime import date

from app.ingestion.base import NormalizedEvent

logger = logging.getLogger(__name__)


class BandsintownAdapter:
    source_name = "bandsintown"
    _warned = False

    async def fetch_events(
        self, city: str, date_from: date, date_to: date,
        lat: float = 30.27, lon: float = -97.74,
    ) -> list[NormalizedEvent]:
        if not BandsintownAdapter._warned:
            logger.warning(
                "Bandsintown adapter disabled: location-based search requires a "
                "partnership key (returns 403). Returning empty."
            )
            BandsintownAdapter._warned = True
        return []

    async def fetch_artist_events(self, artist_name: str) -> list[NormalizedEvent]:
        return []
