"""Eventbrite ingestion adapter.

While Eventbrite's public event search API was deprecated in 2020, we can still:
1. Search by location using their web search endpoint
2. Fetch events for known organizers/venues via the v3 API
3. Use their destination pages for city-level discovery

Covers: workshops, classes, conferences, fundraisers, comedy, theatre,
and other ticketed community events not on Ticketmaster.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import httpx

from app.core.config import settings
from app.ingestion.base import NormalizedEvent

BASE_URL = "https://www.eventbriteapi.com/v3"


class EventbriteAdapter:
    source_name = "eventbrite"

    def __init__(self, oauth_token: str | None = None):
        self.oauth_token = oauth_token

    async def fetch_events(
        self, city: str, date_from: date, date_to: date,
        lat: float = 30.27, lon: float = -97.74,
    ) -> list[NormalizedEvent]:
        """
        Fetch events using Eventbrite's location-based search.
        Falls back to destination page scraping if no OAuth token.
        """
        if not self.oauth_token:
            return await self._fetch_via_destination(city, lat, lon)

        params = {
            "location.latitude": lat,
            "location.longitude": lon,
            "location.within": "25mi",
            "start_date.range_start": f"{date_from}T00:00:00",
            "start_date.range_end": f"{date_to}T23:59:59",
            "expand": "venue,ticket_availability,category",
        }
        headers = {"Authorization": f"Bearer {self.oauth_token}"}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{BASE_URL}/events/search/", params=params, headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        return [self._normalize(e) for e in data.get("events", [])]

    async def _fetch_via_destination(
        self, city: str, lat: float, lon: float
    ) -> list[NormalizedEvent]:
        """
        Use Eventbrite's public destination API (no auth required).
        This returns popular events in a given location.
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "within": "25mi",
            "page_size": 50,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    "https://www.eventbrite.com/api/v3/destination/events/",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

            return [self._normalize_destination(e) for e in data.get("events", [])]
        except Exception:
            # Destination API is undocumented and may change
            return []

    def _normalize(self, raw: dict) -> NormalizedEvent:
        venue = raw.get("venue") or {}
        address = venue.get("address") or {}

        start = raw.get("start", {})
        end = raw.get("end", {})
        starts_at = datetime.fromisoformat(start["utc"].replace("Z", "+00:00")) if start.get("utc") else None
        ends_at = datetime.fromisoformat(end["utc"].replace("Z", "+00:00")) if end.get("utc") else None

        # Price from ticket availability
        ticket_info = raw.get("ticket_availability") or {}
        price_min = None
        price_max = None
        if ticket_info.get("minimum_ticket_price"):
            price_min = Decimal(str(ticket_info["minimum_ticket_price"].get("value", 0)))
        if ticket_info.get("maximum_ticket_price"):
            price_max = Decimal(str(ticket_info["maximum_ticket_price"].get("value", 0)))
        if raw.get("is_free"):
            price_min = Decimal("0")
            price_max = Decimal("0")

        # Categories
        categories = []
        cat = raw.get("category") or {}
        if cat.get("name"):
            categories.append(cat["name"].lower())
        if cat.get("short_name"):
            categories.append(cat["short_name"].lower())

        return NormalizedEvent(
            external_id=raw["id"],
            source=self.source_name,
            title=raw.get("name", {}).get("text", ""),
            description=raw.get("description", {}).get("text", "")[:2000] if raw.get("description") else None,
            venue_name=venue.get("name"),
            venue_address=address.get("localized_address_display"),
            city=address.get("city"),
            state=address.get("region"),
            country=address.get("country", "US"),
            latitude=float(address["latitude"]) if address.get("latitude") else None,
            longitude=float(address["longitude"]) if address.get("longitude") else None,
            starts_at=starts_at,
            ends_at=ends_at,
            price_min=price_min,
            price_max=price_max,
            url=raw.get("url"),
            image_url=raw.get("logo", {}).get("url") if raw.get("logo") else None,
            categories=categories or ["community"],
            raw_data=raw,
        )

    def _normalize_destination(self, raw: dict) -> NormalizedEvent:
        """Normalize from the destination API format (slightly different schema)."""
        starts_at = None
        if raw.get("start_date"):
            try:
                starts_at = datetime.fromisoformat(raw["start_date"])
            except (ValueError, TypeError):
                pass

        price_min = Decimal("0") if raw.get("is_free") else None
        price_max = Decimal("0") if raw.get("is_free") else None

        return NormalizedEvent(
            external_id=str(raw.get("id", "")),
            source=self.source_name,
            title=raw.get("name", ""),
            description=raw.get("summary", ""),
            venue_name=raw.get("primary_venue", {}).get("name"),
            city=raw.get("primary_venue", {}).get("address", {}).get("city"),
            state=raw.get("primary_venue", {}).get("address", {}).get("region"),
            latitude=raw.get("primary_venue", {}).get("address", {}).get("latitude"),
            longitude=raw.get("primary_venue", {}).get("address", {}).get("longitude"),
            starts_at=starts_at,
            price_min=price_min,
            price_max=price_max,
            url=raw.get("url"),
            image_url=raw.get("image", {}).get("url") if raw.get("image") else None,
            categories=["community"],
            raw_data=raw,
        )
