"""Meetup.com ingestion adapter.

Uses the Meetup GraphQL API (v2) to find events near a location.
Covers: tech meetups, hobby groups, sports clubs, professional networking,
language exchanges, book clubs, and other community events that rarely
appear on Ticketmaster/SeatGeek.

API docs: https://www.meetup.com/api/schema/
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import httpx

from app.ingestion.base import NormalizedEvent

GRAPHQL_URL = "https://api.meetup.com/gql"


class MeetupAdapter:
    source_name = "meetup"

    async def fetch_events(
        self, city: str, date_from: date, date_to: date, lat: float = 30.27, lon: float = -97.74
    ) -> list[NormalizedEvent]:
        query = """
        query($lat: Float!, $lon: Float!, $startDateRange: DateTime!, $endDateRange: DateTime!) {
          rankedEvents(
            filter: {
              lat: $lat
              lon: $lon
              radius: 25
              startDateRange: $startDateRange
              endDateRange: $endDateRange
            }
            first: 100
          ) {
            edges {
              node {
                id
                title
                description
                dateTime
                endTime
                eventUrl
                going
                fee {
                  amount
                  currency
                }
                venue {
                  name
                  address
                  city
                  state
                  lat
                  lng
                }
                group {
                  name
                  urlname
                }
                images {
                  source
                }
                topics {
                  name
                }
              }
            }
          }
        }
        """

        variables = {
            "lat": lat,
            "lon": lon,
            "startDateRange": f"{date_from}T00:00:00Z",
            "endDateRange": f"{date_to}T23:59:59Z",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                GRAPHQL_URL,
                json={"query": query, "variables": variables},
            )
            response.raise_for_status()
            data = response.json()

        edges = data.get("data", {}).get("rankedEvents", {}).get("edges", [])
        return [self._normalize(edge["node"]) for edge in edges if edge.get("node")]

    def _normalize(self, raw: dict) -> NormalizedEvent:
        venue = raw.get("venue") or {}
        fee = raw.get("fee") or {}
        images = raw.get("images") or []
        topics = raw.get("topics") or []
        group = raw.get("group") or {}

        # Parse datetime
        dt_str = raw.get("dateTime")
        starts_at = datetime.fromisoformat(dt_str) if dt_str else None
        end_str = raw.get("endTime")
        ends_at = datetime.fromisoformat(end_str) if end_str else None

        # Build categories from topics
        categories = ["meetup"]
        for topic in topics[:5]:
            name = topic.get("name", "").lower()
            if name:
                categories.append(name)

        # Map common Meetup topics to our categories
        topic_names = {t.get("name", "").lower() for t in topics}
        if topic_names & {"technology", "software", "programming", "tech", "ai", "data science"}:
            categories.append("technology")
        if topic_names & {"outdoor", "hiking", "running", "fitness", "yoga"}:
            categories.append("outdoor")
        if topic_names & {"music", "jazz", "rock", "concert"}:
            categories.append("music")
        if topic_names & {"food", "cooking", "wine", "beer", "dining"}:
            categories.append("food")
        if topic_names & {"art", "photography", "painting", "design"}:
            categories.append("arts")
        if topic_names & {"gaming", "board games", "video games"}:
            categories.append("entertainment")
        if topic_names & {"parents", "kids", "family"}:
            categories.append("family")

        categories = list(dict.fromkeys(categories))  # deduplicate

        price = Decimal(str(fee.get("amount", 0)))

        return NormalizedEvent(
            external_id=raw["id"],
            source=self.source_name,
            title=raw.get("title", ""),
            description=raw.get("description", "")[:2000] if raw.get("description") else None,
            venue_name=venue.get("name") or group.get("name"),
            venue_address=venue.get("address"),
            city=venue.get("city"),
            state=venue.get("state"),
            latitude=venue.get("lat"),
            longitude=venue.get("lng"),
            starts_at=starts_at,
            ends_at=ends_at,
            price_min=price,
            price_max=price,
            url=raw.get("eventUrl"),
            image_url=images[0].get("source") if images else None,
            categories=categories,
            raw_data=raw,
        )
