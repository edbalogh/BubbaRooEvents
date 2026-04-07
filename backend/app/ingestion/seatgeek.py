"""SeatGeek ingestion adapter — DISABLED.

SeatGeek shut down their public developer API program. New API keys are no
longer issued; access is partner-only. Returning empty until a replacement
is found.
"""

from __future__ import annotations

import logging
from datetime import date

from app.ingestion.base import NormalizedEvent

logger = logging.getLogger(__name__)


class SeatGeekAdapter:
    source_name = "seatgeek"
    _warned = False

    async def fetch_events(
        self, city: str, date_from: date | None = None, date_to: date | None = None,
        lat: float = 30.27, lon: float = -97.74,
    ) -> list[NormalizedEvent]:
        if not SeatGeekAdapter._warned:
            logger.warning(
                "SeatGeek adapter disabled: public API program was shut down. "
                "Partner access only. Returning empty."
            )
            SeatGeekAdapter._warned = True
        return []
