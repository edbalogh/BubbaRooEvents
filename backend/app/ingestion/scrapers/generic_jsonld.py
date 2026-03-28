"""Generic JSON-LD event scraper.

Many event websites embed structured data using JSON-LD (schema.org/Event).
This scraper extracts events from any page with JSON-LD structured data,
making it a versatile fallback scraper for venues and aggregators.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime

from app.ingestion.base import NormalizedEvent
from app.ingestion.venue_scraper import VenueScraperBase

logger = logging.getLogger(__name__)


class GenericJsonLdScraper(VenueScraperBase):
    """Scrapes events from any website that uses JSON-LD structured data.

    Configure by setting source_name, base_url, city, state, and
    default_categories. The parser handles schema.org/Event format
    automatically.

    Example usage:
        scraper = GenericJsonLdScraper()
        scraper.source_name = "stubbs-austin"
        scraper.base_url = "https://stubbsaustin.com/events"
        scraper.city = "Austin"
        scraper.state = "TX"
        scraper.venue_name = "Stubb's BBQ"
        scraper.default_categories = ["concerts"]
        events = await scraper.fetch_events()
    """

    source_name = "generic-jsonld"

    async def parse_events(self, html: str) -> list[NormalizedEvent]:
        """Extract events from JSON-LD blocks in HTML."""
        events = []

        json_ld_blocks = re.findall(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html,
            re.DOTALL | re.IGNORECASE,
        )

        for block in json_ld_blocks:
            try:
                data = json.loads(block.strip())
            except json.JSONDecodeError:
                continue

            # Handle single objects, arrays, and @graph patterns
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                if data.get("@type") == "Event":
                    items = [data]
                elif "@graph" in data:
                    items = data["@graph"]
                elif data.get("@type") == "ItemList":
                    items = data.get("itemListElement", [])

            for item in items:
                if isinstance(item, dict) and item.get("@type") == "ListItem":
                    item = item.get("item", {})
                if not isinstance(item, dict):
                    continue
                event_type = item.get("@type", "")
                if isinstance(event_type, list):
                    event_type = event_type[0] if event_type else ""
                if "Event" not in event_type:
                    continue

                event = self._normalize_jsonld_event(item)
                if event:
                    events.append(event)

        logger.info(f"[{self.source_name}] Extracted {len(events)} events from JSON-LD")
        return events

    def _normalize_jsonld_event(self, item: dict) -> NormalizedEvent | None:
        """Convert a JSON-LD Event object to NormalizedEvent."""
        title = item.get("name", "").strip()
        if not title:
            return None

        # Parse dates
        starts_at = self._parse_iso_date(item.get("startDate"))
        ends_at = self._parse_iso_date(item.get("endDate"))

        # Location
        location = item.get("location", {})
        venue = None
        address = None
        lat = self.latitude
        lon = self.longitude

        if isinstance(location, dict):
            venue = location.get("name") or self.venue_name
            addr = location.get("address", {})
            if isinstance(addr, dict):
                parts = [
                    addr.get("streetAddress", ""),
                    addr.get("addressLocality", ""),
                    addr.get("addressRegion", ""),
                ]
                address = ", ".join(p for p in parts if p)
            elif isinstance(addr, str):
                address = addr

            geo = location.get("geo", {})
            if isinstance(geo, dict):
                try:
                    lat = float(geo.get("latitude", 0)) or self.latitude
                    lon = float(geo.get("longitude", 0)) or self.longitude
                except (ValueError, TypeError):
                    pass
        elif isinstance(location, str):
            venue = location

        # Price
        price_min = None
        price_max = None
        offers = item.get("offers")
        if isinstance(offers, dict):
            price_min = self._parse_price(offers.get("price") or offers.get("lowPrice"))
            price_max = self._parse_price(offers.get("highPrice"))
        elif isinstance(offers, list):
            prices = [self._parse_price(o.get("price")) for o in offers if isinstance(o, dict)]
            prices = [p for p in prices if p is not None]
            if prices:
                price_min = min(prices)
                price_max = max(prices)

        # Image
        image_url = None
        image = item.get("image")
        if isinstance(image, str):
            image_url = image
        elif isinstance(image, list) and image:
            image_url = image[0] if isinstance(image[0], str) else image[0].get("url")
        elif isinstance(image, dict):
            image_url = image.get("url")

        # Description
        description = item.get("description", "")
        if description and len(description) > 2000:
            description = description[:2000]

        # URL
        url = item.get("url") or item.get("@id")

        # External ID
        ext_id = url or f"{self.source_name}-{title[:50]}"

        return NormalizedEvent(
            external_id=ext_id[:128],
            source=self.source_name,
            title=title,
            description=description or None,
            venue_name=venue or self.venue_name,
            venue_address=address,
            city=self.city,
            state=self.state,
            latitude=lat,
            longitude=lon,
            starts_at=starts_at,
            ends_at=ends_at,
            price_min=price_min,
            price_max=price_max,
            url=url,
            image_url=image_url,
            categories=self.default_categories or ["community"],
        )

    def _parse_iso_date(self, date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def _parse_price(self, value) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


# --- Pre-configured scrapers for known venues ---


def create_venue_scraper(
    source_name: str,
    url: str,
    city: str,
    state: str,
    venue_name: str = "",
    categories: list[str] | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> GenericJsonLdScraper:
    """Factory function to create a configured JSON-LD scraper for a venue."""
    scraper = GenericJsonLdScraper()
    scraper.source_name = source_name
    scraper.base_url = url
    scraper.city = city
    scraper.state = state
    scraper.venue_name = venue_name
    scraper.default_categories = categories or ["community"]
    scraper.latitude = lat
    scraper.longitude = lon
    return scraper


# Pre-built venue scrapers
VENUE_SCRAPERS = {
    "stubbs-austin": lambda: create_venue_scraper(
        "stubbs-austin", "https://stubbsaustin.com/events",
        "Austin", "TX", "Stubb's BBQ", ["concerts"], 30.2685, -97.7365,
    ),
    "mohawk-austin": lambda: create_venue_scraper(
        "mohawk-austin", "https://mohawkaustin.com/events",
        "Austin", "TX", "Mohawk", ["concerts", "nightlife"], 30.2675, -97.7355,
    ),
    "ryman-nashville": lambda: create_venue_scraper(
        "ryman-nashville", "https://rfrfryman.com/events",
        "Nashville", "TN", "Ryman Auditorium", ["concerts", "comedy"], 36.1612, -86.7767,
    ),
    "red-rocks-denver": lambda: create_venue_scraper(
        "red-rocks-denver", "https://www.redrocksonline.com/events",
        "Denver", "CO", "Red Rocks Amphitheatre", ["concerts"], 39.6654, -105.2057,
    ),
    "revolution-hall-portland": lambda: create_venue_scraper(
        "revolution-hall-portland", "https://www.revolutionhallpdx.com/events",
        "Portland", "OR", "Revolution Hall", ["concerts"], 45.5162, -122.6538,
    ),
    "showbox-seattle": lambda: create_venue_scraper(
        "showbox-seattle", "https://www.showboxpresents.com/events",
        "Seattle", "WA", "The Showbox", ["concerts"], 47.6083, -122.3398,
    ),
}
