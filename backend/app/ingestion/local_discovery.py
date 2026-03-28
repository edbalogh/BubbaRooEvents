"""
Local event source discovery service.

Automatically finds local event websites, calendars, and aggregators
for a given city/location. This helps users and the system discover
non-standard event sources like:
- City-specific event aggregators (Do512, TheDenverEar, BrooklynVegan, etc.)
- Local alternative weekly newspapers with event listings
- City/county parks & recreation calendars
- Library event calendars
- Convention center schedules
- Local venue websites
- Community Facebook groups (metadata only)

The discovery results get stored in the event_sources table and can
be reviewed by admins or auto-activated based on trust scoring.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredSource:
    name: str
    url: str
    source_type: str  # aggregator, venue, city_calendar, newspaper, ical
    description: str
    city: str
    state: str | None = None
    likely_categories: list[str] | None = None
    has_ical_feed: bool = False
    has_api: bool = False


# Known local event aggregators by city
# These are manually curated but the framework supports auto-discovery too
KNOWN_LOCAL_SOURCES: dict[str, list[DiscoveredSource]] = {
    "austin": [
        DiscoveredSource(
            name="Do512",
            url="https://do512.com/events",
            source_type="aggregator",
            description="Austin's go-to local events guide. Music, food, comedy, family, outdoor events.",
            city="Austin", state="TX",
            likely_categories=["music", "food", "comedy", "outdoor", "arts", "family"],
        ),
        DiscoveredSource(
            name="Austin Chronicle Events",
            url="https://www.austinchronicle.com/events/",
            source_type="newspaper",
            description="Austin Chronicle's comprehensive event calendar. Strong on music, arts, and culture.",
            city="Austin", state="TX",
            likely_categories=["music", "arts", "theatre", "comedy", "film"],
        ),
        DiscoveredSource(
            name="Austin Parks & Rec",
            url="https://www.austintexas.gov/department/parks-and-recreation",
            source_type="city_calendar",
            description="City of Austin Parks & Recreation events. Free community events, outdoor activities.",
            city="Austin", state="TX",
            likely_categories=["outdoor", "family", "fitness", "community"],
            has_ical_feed=True,
        ),
        DiscoveredSource(
            name="Austin Public Library",
            url="https://library.austintexas.gov/events",
            source_type="city_calendar",
            description="Free library events: author talks, kids programs, workshops, movie screenings.",
            city="Austin", state="TX",
            likely_categories=["education", "family", "community"],
            has_ical_feed=True,
        ),
        DiscoveredSource(
            name="Mohawk Austin",
            url="https://mohawkaustin.com/events",
            source_type="venue",
            description="Iconic Red River district music venue. Indie, punk, rock, electronic.",
            city="Austin", state="TX",
            likely_categories=["music", "concert", "nightlife"],
        ),
        DiscoveredSource(
            name="Stubb's BBQ",
            url="https://stubbsaustin.com/events",
            source_type="venue",
            description="Legendary Austin BBQ and music venue. Rock, country, hip-hop, and more.",
            city="Austin", state="TX",
            likely_categories=["music", "concert"],
        ),
        DiscoveredSource(
            name="Austin Convention Center",
            url="https://www.austinconventioncenter.com/events",
            source_type="venue",
            description="Major convention and expo center. Conventions, trade shows, conferences.",
            city="Austin", state="TX",
            likely_categories=["conventions", "conference", "expo"],
        ),
    ],
    "nashville": [
        DiscoveredSource(
            name="Nashville Scene",
            url="https://www.nashvillescene.com/arts-culture/events/",
            source_type="newspaper",
            description="Nashville's alternative weekly. Comprehensive local event coverage.",
            city="Nashville", state="TN",
            likely_categories=["music", "arts", "comedy", "food"],
        ),
        DiscoveredSource(
            name="Nashville Guru",
            url="https://nashvilleguru.com/events",
            source_type="aggregator",
            description="Local Nashville events guide covering music, food, festivals, and nightlife.",
            city="Nashville", state="TN",
            likely_categories=["music", "food", "festival", "nightlife"],
        ),
        DiscoveredSource(
            name="The Ryman Auditorium",
            url="https://rfrfryman.com/events",
            source_type="venue",
            description="The Mother Church of Country Music. Concerts, comedy, and special events.",
            city="Nashville", state="TN",
            likely_categories=["music", "concert", "comedy"],
        ),
        DiscoveredSource(
            name="Nashville Public Library",
            url="https://library.nashville.org/events",
            source_type="city_calendar",
            description="Free library events: author talks, films, workshops.",
            city="Nashville", state="TN",
            likely_categories=["education", "family", "community"],
            has_ical_feed=True,
        ),
    ],
    "denver": [
        DiscoveredSource(
            name="303 Magazine",
            url="https://303magazine.com/events/",
            source_type="newspaper",
            description="Denver's culture magazine. Music, food, art, fashion events.",
            city="Denver", state="CO",
            likely_categories=["music", "arts", "food", "fashion"],
        ),
        DiscoveredSource(
            name="Denver Arts & Venues",
            url="https://www.artsandvenuesdenver.com/events",
            source_type="city_calendar",
            description="City of Denver cultural events. Free concerts, festivals, art exhibitions.",
            city="Denver", state="CO",
            likely_categories=["arts", "music", "festival", "community"],
        ),
        DiscoveredSource(
            name="Colorado Convention Center",
            url="https://www.denverconvention.com/events",
            source_type="venue",
            description="Major conventions, expos, and trade shows in Denver.",
            city="Denver", state="CO",
            likely_categories=["conventions", "conference", "expo"],
        ),
    ],
    "portland": [
        DiscoveredSource(
            name="Portland Mercury",
            url="https://www.portlandmercury.com/events",
            source_type="newspaper",
            description="Portland's alt-weekly. Music, comedy, art, theatre events.",
            city="Portland", state="OR",
            likely_categories=["music", "comedy", "arts", "theatre"],
        ),
        DiscoveredSource(
            name="PDX Pipeline",
            url="https://pdxpipeline.com/events/",
            source_type="aggregator",
            description="Portland events aggregator. Free and cheap events, markets, festivals.",
            city="Portland", state="OR",
            likely_categories=["community", "food", "music", "outdoor"],
        ),
    ],
    "seattle": [
        DiscoveredSource(
            name="The Stranger",
            url="https://www.thestranger.com/events",
            source_type="newspaper",
            description="Seattle's alternative weekly. Comprehensive local event listings.",
            city="Seattle", state="WA",
            likely_categories=["music", "arts", "comedy", "theatre", "film"],
        ),
        DiscoveredSource(
            name="Seattle Met Events",
            url="https://www.seattlemet.com/events",
            source_type="aggregator",
            description="Seattle lifestyle magazine events calendar.",
            city="Seattle", state="WA",
            likely_categories=["food", "arts", "community"],
        ),
    ],
}

# Generic source types that exist in most cities
GENERIC_SOURCE_TEMPLATES = [
    {
        "suffix": "parks & recreation",
        "source_type": "city_calendar",
        "description_template": "{city} Parks & Recreation events calendar",
        "likely_categories": ["outdoor", "family", "fitness", "community"],
    },
    {
        "suffix": "public library events",
        "source_type": "city_calendar",
        "description_template": "{city} Public Library free events",
        "likely_categories": ["education", "family", "community"],
    },
    {
        "suffix": "convention center events",
        "source_type": "venue",
        "description_template": "{city} Convention Center schedule",
        "likely_categories": ["conventions", "conference", "expo"],
    },
]


async def discover_sources_for_city(city: str, state: str | None = None) -> list[DiscoveredSource]:
    """
    Discover local event sources for a given city.

    First checks our curated list of known sources, then attempts
    to find additional sources via web search patterns.
    """
    city_key = city.lower().strip()
    sources = list(KNOWN_LOCAL_SOURCES.get(city_key, []))

    # Try web search for additional sources if we have few known ones
    if len(sources) < 3:
        additional = await _search_for_local_sources(city, state)
        # Deduplicate by URL
        known_urls = {s.url for s in sources}
        for s in additional:
            if s.url not in known_urls:
                sources.append(s)

    return sources


async def _search_for_local_sources(city: str, state: str | None = None) -> list[DiscoveredSource]:
    """
    Search for local event sources using common URL patterns.
    This is a heuristic approach - checks if common patterns resolve.
    """
    sources = []
    location = f"{city}, {state}" if state else city

    # Common URL patterns for local event sites
    search_patterns = [
        (f"https://www.{city.lower().replace(' ', '')}events.com", "aggregator"),
        (f"https://do{city.lower().replace(' ', '')}.com", "aggregator"),
        (f"https://www.{city.lower().replace(' ', '')}.com/events", "aggregator"),
    ]

    async with httpx.AsyncClient(timeout=10) as client:
        for url, source_type in search_patterns:
            try:
                response = await client.head(url, follow_redirects=True)
                if response.status_code == 200:
                    sources.append(DiscoveredSource(
                        name=f"{city} Local Events",
                        url=url,
                        source_type=source_type,
                        description=f"Local event source discovered for {location}",
                        city=city,
                        state=state,
                        likely_categories=["community"],
                    ))
            except Exception:
                continue  # URL doesn't resolve, skip

    return sources


def get_known_cities() -> list[str]:
    """Return list of cities with curated local source data."""
    return list(KNOWN_LOCAL_SOURCES.keys())
