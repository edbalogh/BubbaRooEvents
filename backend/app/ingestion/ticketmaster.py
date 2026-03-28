from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import httpx

from app.core.config import settings
from app.ingestion.base import NormalizedEvent

BASE_URL = "https://app.ticketmaster.com/discovery/v2"


class TicketmasterAdapter:
    source_name = "ticketmaster"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.ticketmaster_api_key

    async def fetch_events(
        self, city: str, date_from: date, date_to: date
    ) -> list[NormalizedEvent]:
        if not self.api_key:
            return []

        params = {
            "apikey": self.api_key,
            "city": city,
            "startDateTime": f"{date_from}T00:00:00Z",
            "endDateTime": f"{date_to}T23:59:59Z",
            "size": 100,
            "sort": "date,asc",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{BASE_URL}/events.json", params=params)
            response.raise_for_status()
            data = response.json()

        embedded = data.get("_embedded", {})
        raw_events = embedded.get("events", [])

        return [self._normalize(event) for event in raw_events]

    def _normalize(self, raw: dict) -> NormalizedEvent:
        # Extract venue info
        venues = raw.get("_embedded", {}).get("venues", [])
        venue = venues[0] if venues else {}
        location = venue.get("location", {})

        # Extract price ranges
        price_ranges = raw.get("priceRanges", [])
        price_min = None
        price_max = None
        if price_ranges:
            price_min = Decimal(str(price_ranges[0].get("min", 0)))
            price_max = Decimal(str(price_ranges[0].get("max", 0)))

        # Extract dates
        dates = raw.get("dates", {})
        start = dates.get("start", {})
        start_dt = start.get("dateTime")
        starts_at = datetime.fromisoformat(start_dt.replace("Z", "+00:00")) if start_dt else None

        # Extract sales dates
        sales = raw.get("sales", {}).get("public", {})
        on_sale_str = sales.get("startDateTime")
        on_sale_at = (
            datetime.fromisoformat(on_sale_str.replace("Z", "+00:00")) if on_sale_str else None
        )

        # Extract categories from classifications
        # Ticketmaster segments: Music, Sports, Arts & Theatre, Film, Miscellaneous
        # We map these + genres to our broader category taxonomy
        SEGMENT_MAP = {
            "music": ["music", "concert"],
            "sports": ["sports"],
            "arts & theatre": ["arts", "theatre"],
            "film": ["film", "entertainment"],
            "miscellaneous": [],
        }
        classifications = raw.get("classifications", [])
        categories = []
        for c in classifications:
            segment = c.get("segment", {}).get("name", "").strip()
            genre = c.get("genre", {}).get("name", "").strip()
            subgenre = c.get("subGenre", {}).get("name", "").strip()
            event_type = c.get("type", {}).get("name", "").strip()

            if segment and segment != "Undefined":
                mapped = SEGMENT_MAP.get(segment.lower(), [segment.lower()])
                categories.extend(mapped)
            if genre and genre != "Undefined":
                categories.append(genre.lower())
            if subgenre and subgenre != "Undefined" and subgenre.lower() != genre.lower():
                categories.append(subgenre.lower())
            # Ticketmaster "type" can indicate convention, festival, expo, etc.
            if event_type and event_type != "Undefined":
                type_lower = event_type.lower()
                if "convention" in type_lower or "conference" in type_lower or "expo" in type_lower:
                    categories.append("conventions")
                if "festival" in type_lower:
                    categories.append("festival")

        categories = list(dict.fromkeys(categories))  # deduplicate, preserve order

        # Extract image
        images = raw.get("images", [])
        image_url = images[0]["url"] if images else None

        return NormalizedEvent(
            external_id=raw["id"],
            source=self.source_name,
            title=raw.get("name", ""),
            description=raw.get("info") or raw.get("pleaseNote"),
            venue_name=venue.get("name"),
            venue_address=venue.get("address", {}).get("line1"),
            city=venue.get("city", {}).get("name"),
            state=venue.get("state", {}).get("stateCode"),
            country=venue.get("country", {}).get("countryCode", "US"),
            latitude=float(location["latitude"]) if location.get("latitude") else None,
            longitude=float(location["longitude"]) if location.get("longitude") else None,
            starts_at=starts_at,
            ends_at=None,
            on_sale_at=on_sale_at,
            price_min=price_min,
            price_max=price_max,
            url=raw.get("url"),
            image_url=image_url,
            categories=categories,
            raw_data=raw,
        )
