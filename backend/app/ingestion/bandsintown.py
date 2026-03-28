"""Bandsintown ingestion adapter.

Uses the free Bandsintown Artist Events API to discover concerts and
live music events. No auth required. Excellent coverage of small/indie
venues that Ticketmaster misses.

API docs: https://artists.bandsintown.com/support/api-installation
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import httpx

from app.ingestion.base import NormalizedEvent

BASE_URL = "https://rest.bandsintown.com"
APP_ID = "bubbaroo_events"  # Bandsintown requires an app_id but no key


class BandsintownAdapter:
    source_name = "bandsintown"

    async def fetch_events_by_location(
        self, lat: float, lon: float, radius_miles: int = 25, date_from: date | None = None
    ) -> list[NormalizedEvent]:
        """
        Bandsintown doesn't have a direct location search.
        We search for events at known venues in the area.
        This is a best-effort approach using their venue search.
        """
        # Bandsintown's primary API is artist-centric.
        # For location-based discovery, we use the events endpoint
        # with location parameters.
        params = {
            "app_id": APP_ID,
            "location": f"{lat},{lon}",
            "radius": str(radius_miles),
            "date": f"{date_from or 'upcoming'}",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{BASE_URL}/artists/events",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

            if isinstance(data, list):
                return [self._normalize(e) for e in data]
            return []
        except Exception:
            return []

    async def fetch_events(
        self, city: str, date_from: date, date_to: date,
        lat: float = 30.27, lon: float = -97.74,
    ) -> list[NormalizedEvent]:
        """Adapter interface: fetch events for a city."""
        return await self.fetch_events_by_location(lat, lon, date_from=date_from)

    async def fetch_artist_events(self, artist_name: str) -> list[NormalizedEvent]:
        """Fetch upcoming events for a specific artist."""
        encoded = artist_name.replace(" ", "%20")
        params = {"app_id": APP_ID, "date": "upcoming"}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{BASE_URL}/artists/{encoded}/events",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

        if isinstance(data, list):
            return [self._normalize(e) for e in data]
        return []

    def _normalize(self, raw: dict) -> NormalizedEvent:
        venue = raw.get("venue", {})

        # Parse datetime
        dt = raw.get("datetime")
        starts_at = None
        if dt:
            try:
                starts_at = datetime.fromisoformat(dt)
            except (ValueError, TypeError):
                pass

        # Bandsintown doesn't provide pricing, but we can note ticket status
        offers = raw.get("offers", [])
        ticket_url = offers[0].get("url") if offers else raw.get("url")
        ticket_status = offers[0].get("status") if offers else None

        # Extract artist info
        artist = raw.get("artist", {})
        artist_name = artist.get("name", "")

        # Categories
        categories = ["music", "concert"]
        if artist.get("genre"):
            categories.append(artist["genre"].lower())

        return NormalizedEvent(
            external_id=str(raw.get("id", "")),
            source=self.source_name,
            title=f"{artist_name} at {venue.get('name', 'TBD')}",
            description=raw.get("description") or f"Live music: {artist_name}. {ticket_status or ''}".strip(),
            venue_name=venue.get("name"),
            venue_address=venue.get("street_address"),
            city=venue.get("city"),
            state=venue.get("region"),
            country=venue.get("country", "US"),
            latitude=float(venue["latitude"]) if venue.get("latitude") else None,
            longitude=float(venue["longitude"]) if venue.get("longitude") else None,
            starts_at=starts_at,
            url=ticket_url,
            image_url=artist.get("image_url"),
            categories=categories,
            raw_data=raw,
        )
