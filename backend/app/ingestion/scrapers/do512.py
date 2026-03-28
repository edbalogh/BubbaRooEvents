"""Scraper for Do512 - Austin's go-to local events guide.

Extracts events from Do512's event listing pages using HTML parsing.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime

from app.ingestion.base import NormalizedEvent
from app.ingestion.venue_scraper import VenueScraperBase

logger = logging.getLogger(__name__)


class Do512Scraper(VenueScraperBase):
    source_name = "do512"
    base_url = "https://do512.com/events"
    city = "Austin"
    state = "TX"
    latitude = 30.2672
    longitude = -97.7431
    default_categories = ["community"]

    async def parse_events(self, html: str) -> list[NormalizedEvent]:
        """Parse Do512 event listing HTML."""
        events = []

        # Do512 uses structured event cards - parse with regex for robustness
        # Look for event blocks with title, date, venue, and URL patterns
        event_blocks = re.findall(
            r'<a[^>]*href="(/events/[^"]+)"[^>]*>.*?</a>',
            html,
            re.DOTALL,
        )

        # Also try JSON-LD structured data if present
        json_ld_events = self._parse_json_ld(html)
        if json_ld_events:
            return json_ld_events

        # Fallback: parse visible text patterns
        title_pattern = re.compile(
            r'class="[^"]*event[^"]*title[^"]*"[^>]*>([^<]+)<', re.IGNORECASE
        )
        date_pattern = re.compile(
            r'class="[^"]*event[^"]*date[^"]*"[^>]*>([^<]+)<', re.IGNORECASE
        )
        venue_pattern = re.compile(
            r'class="[^"]*event[^"]*venue[^"]*"[^>]*>([^<]+)<', re.IGNORECASE
        )
        link_pattern = re.compile(
            r'href="(/events/[^"]+)"', re.IGNORECASE
        )

        titles = title_pattern.findall(html)
        dates = date_pattern.findall(html)
        venues = venue_pattern.findall(html)
        links = link_pattern.findall(html)

        for i, title in enumerate(titles):
            title = title.strip()
            if not title:
                continue

            venue = venues[i].strip() if i < len(venues) else None
            date_str = dates[i].strip() if i < len(dates) else None
            link = links[i] if i < len(links) else None

            starts_at = self._parse_date(date_str) if date_str else None
            url = f"https://do512.com{link}" if link else None
            ext_id = hashlib.md5(f"do512-{title}-{date_str}".encode()).hexdigest()[:16]

            events.append(NormalizedEvent(
                external_id=ext_id,
                source=self.source_name,
                title=title,
                description=None,
                venue_name=venue,
                city=self.city,
                state=self.state,
                latitude=self.latitude,
                longitude=self.longitude,
                starts_at=starts_at,
                url=url,
                categories=self.default_categories,
            ))

        return events

    def _parse_json_ld(self, html: str) -> list[NormalizedEvent]:
        """Try to extract events from JSON-LD structured data."""
        import json

        events = []
        json_ld_blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            html,
            re.DOTALL,
        )

        for block in json_ld_blocks:
            try:
                data = json.loads(block)
                items = data if isinstance(data, list) else [data]

                for item in items:
                    if item.get("@type") != "Event":
                        continue

                    starts_at = None
                    if item.get("startDate"):
                        try:
                            starts_at = datetime.fromisoformat(
                                item["startDate"].replace("Z", "+00:00")
                            )
                        except ValueError:
                            pass

                    ends_at = None
                    if item.get("endDate"):
                        try:
                            ends_at = datetime.fromisoformat(
                                item["endDate"].replace("Z", "+00:00")
                            )
                        except ValueError:
                            pass

                    location = item.get("location", {})
                    venue_name = location.get("name") if isinstance(location, dict) else None

                    # Price
                    price_min = None
                    offers = item.get("offers", {})
                    if isinstance(offers, dict) and offers.get("price"):
                        try:
                            price_min = float(offers["price"])
                        except (ValueError, TypeError):
                            pass

                    events.append(NormalizedEvent(
                        external_id=item.get("url", item.get("name", ""))[:64],
                        source=self.source_name,
                        title=item.get("name", ""),
                        description=item.get("description"),
                        venue_name=venue_name,
                        city=self.city,
                        state=self.state,
                        latitude=self.latitude,
                        longitude=self.longitude,
                        starts_at=starts_at,
                        ends_at=ends_at,
                        price_min=price_min,
                        url=item.get("url"),
                        image_url=item.get("image"),
                        categories=self.default_categories,
                    ))
            except (json.JSONDecodeError, TypeError):
                continue

        return events

    def _parse_date(self, date_str: str) -> datetime | None:
        """Try common date formats from Do512."""
        formats = [
            "%B %d, %Y %I:%M %p",
            "%b %d, %Y %I:%M %p",
            "%B %d, %Y",
            "%m/%d/%Y %I:%M %p",
            "%Y-%m-%dT%H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
