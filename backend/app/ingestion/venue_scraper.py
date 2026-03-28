"""
HTML venue scraper framework for local event sources.

This provides a base class and utilities for scraping event data from
local venue websites, city calendars, alternative weekly newspapers,
and other HTML-based event sources that don't have APIs.

Each venue/source gets a concrete scraper class that defines:
- The URL(s) to scrape
- CSS selectors or parsing logic for event data
- How to normalize into our standard NormalizedEvent format

Usage:
    class MohawkAustinScraper(VenueScraperBase):
        source_name = "mohawk-austin"
        base_url = "https://mohawkaustin.com/events"

        async def parse_events(self, html: str) -> list[NormalizedEvent]:
            # Custom parsing logic
            ...
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date, datetime

import httpx

from app.ingestion.base import NormalizedEvent

logger = logging.getLogger(__name__)


class VenueScraperBase(ABC):
    """Base class for HTML-based event scrapers."""

    source_name: str = "scraper"
    base_url: str = ""
    venue_name: str = ""
    city: str = ""
    state: str = ""
    latitude: float | None = None
    longitude: float | None = None
    default_categories: list[str] = []

    # Polite scraping defaults
    request_timeout: int = 30
    user_agent: str = "BubbaRooEvents/0.1 (event-discovery-bot)"

    async def fetch_events(
        self, city: str | None = None, date_from: date | None = None, date_to: date | None = None,
    ) -> list[NormalizedEvent]:
        """Fetch and parse events from the venue's website."""
        try:
            html = await self._fetch_html(self.base_url)
            events = await self.parse_events(html)
            logger.info(f"[{self.source_name}] Scraped {len(events)} events")
            return events
        except Exception as e:
            logger.error(f"[{self.source_name}] Scraping failed: {e}")
            return []

    async def _fetch_html(self, url: str) -> str:
        """Fetch HTML content from a URL with polite headers."""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            response = await client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            return response.text

    @abstractmethod
    async def parse_events(self, html: str) -> list[NormalizedEvent]:
        """Parse HTML and return normalized events. Implement per venue."""
        ...


class ICalScraperBase(ABC):
    """Base class for iCal/ICS feed scrapers (common for city/parks/library sites)."""

    source_name: str = "ical"
    feed_url: str = ""
    default_city: str = ""
    default_state: str = ""
    default_categories: list[str] = []

    async def fetch_events(
        self, city: str | None = None, date_from: date | None = None, date_to: date | None = None,
    ) -> list[NormalizedEvent]:
        """Fetch and parse events from an iCal feed."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(self.feed_url)
                response.raise_for_status()
                ical_text = response.text

            return self.parse_ical(ical_text)
        except Exception as e:
            logger.error(f"[{self.source_name}] iCal fetch failed: {e}")
            return []

    def parse_ical(self, ical_text: str) -> list[NormalizedEvent]:
        """Parse iCal text into normalized events.

        Requires the `icalendar` package. Install with: pip install icalendar
        """
        try:
            from icalendar import Calendar
        except ImportError:
            logger.warning("icalendar not installed. pip install icalendar")
            return []

        cal = Calendar.from_ical(ical_text)
        events = []

        for component in cal.walk():
            if component.name != "VEVENT":
                continue

            uid = str(component.get("uid", ""))
            summary = str(component.get("summary", ""))
            description = str(component.get("description", ""))
            location = str(component.get("location", ""))
            dtstart = component.get("dtstart")
            dtend = component.get("dtend")
            url = str(component.get("url", ""))

            starts_at = dtstart.dt if dtstart else None
            ends_at = dtend.dt if dtend else None

            # Convert date to datetime if needed
            if isinstance(starts_at, date) and not isinstance(starts_at, datetime):
                starts_at = datetime.combine(starts_at, datetime.min.time())
            if isinstance(ends_at, date) and not isinstance(ends_at, datetime):
                ends_at = datetime.combine(ends_at, datetime.min.time())

            events.append(NormalizedEvent(
                external_id=uid or f"{self.source_name}-{summary[:50]}",
                source=self.source_name,
                title=summary,
                description=description[:2000] if description else None,
                venue_name=location or None,
                city=self.default_city,
                state=self.default_state,
                starts_at=starts_at,
                ends_at=ends_at,
                url=url or None,
                categories=self.default_categories or ["community"],
            ))

        return events


# --- Example concrete scrapers (uncomment and customize per venue) ---


# class AustinChronicleEventsScraper(VenueScraperBase):
#     """Scrapes events from the Austin Chronicle events calendar."""
#     source_name = "austin-chronicle"
#     base_url = "https://www.austinchronicle.com/events/"
#     city = "Austin"
#     state = "TX"
#     default_categories = ["community", "arts"]
#
#     async def parse_events(self, html: str) -> list[NormalizedEvent]:
#         from html.parser import HTMLParser
#         # Custom parsing logic for Austin Chronicle HTML structure
#         events = []
#         # ... parse HTML ...
#         return events


# class AustinParksICalScraper(ICalScraperBase):
#     """Scrapes Austin Parks & Recreation events via iCal feed."""
#     source_name = "austin-parks"
#     feed_url = "https://www.austintexas.gov/calendar/ical/parks"
#     default_city = "Austin"
#     default_state = "TX"
#     default_categories = ["outdoor", "community", "family"]
