"""SeatGeek event ingestion adapter.

Uses the SeatGeek Platform API v2 to fetch events by location.
Free tier with generous limits. Sign up: https://seatgeek.com/build
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app.core.config import settings
from app.ingestion.base import EventSourceAdapter, NormalizedEvent

logger = logging.getLogger(__name__)

SEATGEEK_API_URL = "https://api.seatgeek.com/2"

# Map SeatGeek taxonomies to our category slugs
TAXONOMY_MAP = {
    "concert": "concerts",
    "concerts": "concerts",
    "music_festival": "festivals",
    "sports": "sports",
    "nfl": "sports",
    "nba": "sports",
    "mlb": "sports",
    "nhl": "sports",
    "mls": "sports",
    "ncaa_football": "sports",
    "ncaa_basketball": "sports",
    "soccer": "sports",
    "tennis": "sports",
    "golf": "sports",
    "boxing": "sports",
    "mma": "sports",
    "wrestling": "sports",
    "auto_racing": "sports",
    "horse_racing": "sports",
    "theater": "theatre",
    "broadway": "theatre",
    "comedy": "comedy",
    "dance_performance_tour": "theatre",
    "classical": "concerts",
    "opera": "theatre",
    "literary": "conventions",
    "family": "family",
    "cirque_du_soleil": "family",
    "film": "theatre",
    "festival": "festivals",
}


class SeatGeekAdapter(EventSourceAdapter):
    source_name = "seatgeek"

    def __init__(self):
        self.client_id = settings.seatgeek_client_id
        self.client_secret = settings.seatgeek_client_secret

    async def fetch_events(
        self,
        city: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[NormalizedEvent]:
        if not self.client_id:
            logger.warning("SeatGeek client_id not configured, skipping")
            return []

        params: dict = {
            "client_id": self.client_id,
            "per_page": 100,
            "sort": "score.desc",
            "venue.city": city,
        }

        if self.client_secret:
            params["client_secret"] = self.client_secret

        if date_from:
            params["datetime_utc.gte"] = date_from.strftime("%Y-%m-%dT%H:%M:%S")
        if date_to:
            params["datetime_utc.lte"] = date_to.strftime("%Y-%m-%dT%H:%M:%S")

        events: list[NormalizedEvent] = []

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"{SEATGEEK_API_URL}/events",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

            for item in data.get("events", []):
                normalized = self._normalize(item)
                if normalized:
                    events.append(normalized)

            logger.info(f"SeatGeek: fetched {len(events)} events for {city}")

        except Exception as e:
            logger.error(f"SeatGeek API error: {e}")

        return events

    def _normalize(self, item: dict) -> NormalizedEvent | None:
        """Normalize a SeatGeek event to our standard format."""
        try:
            venue = item.get("venue", {})
            performers = item.get("performers", [])

            # Extract categories from taxonomies
            categories = set()
            for taxonomy in item.get("taxonomies", []):
                name = taxonomy.get("name", "").lower()
                if name in TAXONOMY_MAP:
                    categories.add(TAXONOMY_MAP[name])
                parent = taxonomy.get("parent_id")
                # Also check performer genres
            for performer in performers:
                for genre in performer.get("genres", []):
                    slug = genre.get("slug", "").lower()
                    if slug in TAXONOMY_MAP:
                        categories.add(TAXONOMY_MAP[slug])

            # Parse price range
            stats = item.get("stats", {})
            price_min = stats.get("lowest_price")
            price_max = stats.get("highest_price")

            # Parse dates
            starts_at = None
            if item.get("datetime_utc"):
                starts_at = datetime.fromisoformat(item["datetime_utc"].replace("Z", "+00:00"))

            # Build description from performers
            desc_parts = []
            if item.get("short_title") and item["short_title"] != item.get("title"):
                desc_parts.append(item["short_title"])
            if performers:
                performer_names = [p["name"] for p in performers[:5]]
                desc_parts.append(f"Featuring: {', '.join(performer_names)}")
            if item.get("description"):
                desc_parts.append(item["description"][:500])

            # Image: use first performer image or event image
            image_url = None
            for p in performers:
                if p.get("image"):
                    image_url = p["image"]
                    break

            return NormalizedEvent(
                external_id=str(item["id"]),
                source="seatgeek",
                title=item.get("title", ""),
                description="\n".join(desc_parts) if desc_parts else None,
                venue_name=venue.get("name"),
                venue_address=venue.get("address"),
                city=venue.get("city"),
                state=venue.get("state"),
                country=venue.get("country", "US"),
                latitude=venue.get("location", {}).get("lat"),
                longitude=venue.get("location", {}).get("lon"),
                starts_at=starts_at,
                ends_at=None,
                on_sale_at=None,
                price_min=float(price_min) if price_min else None,
                price_max=float(price_max) if price_max else None,
                currency="USD",
                url=item.get("url"),
                image_url=image_url,
                categories=list(categories) if categories else ["concerts"],
                raw_data=item,
            )

        except Exception as e:
            logger.warning(f"Failed to normalize SeatGeek event: {e}")
            return None
