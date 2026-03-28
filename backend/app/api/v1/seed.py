"""Endpoint to seed mock data and bootstrap source registry (development only)."""

from fastapi import APIRouter, Depends
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.ingestion.ingest_service import upsert_events
from app.ingestion.mock_data import generate_mock_events
from app.models.source import EventSource

router = APIRouter(prefix="/seed", tags=["dev"])

# Default sources to register
DEFAULT_SOURCES = [
    # National API sources
    {"slug": "ticketmaster", "name": "Ticketmaster", "source_type": "api", "is_local": False,
     "description": "Major ticketing platform. Concerts, sports, theatre, and arena events.",
     "url": "https://www.ticketmaster.com", "default_trust_score": 1.0},
    {"slug": "seatgeek", "name": "SeatGeek", "source_type": "api", "is_local": False,
     "description": "Ticket aggregator with good coverage of sports and concerts.",
     "url": "https://seatgeek.com", "default_trust_score": 1.0},
    {"slug": "eventbrite", "name": "Eventbrite", "source_type": "api", "is_local": False,
     "description": "Community events platform. Workshops, classes, conferences, fundraisers.",
     "url": "https://www.eventbrite.com", "default_trust_score": 0.9},
    {"slug": "meetup", "name": "Meetup", "source_type": "api", "is_local": False,
     "description": "Community groups and meetups. Tech, hobbies, sports, professional networking.",
     "url": "https://www.meetup.com", "default_trust_score": 0.8},
    {"slug": "bandsintown", "name": "Bandsintown", "source_type": "api", "is_local": False,
     "description": "Live music discovery. Concerts, tours, DJ sets at venues of all sizes.",
     "url": "https://www.bandsintown.com", "default_trust_score": 0.9},
    # Mock source for development
    {"slug": "mock", "name": "Mock Data", "source_type": "manual", "is_local": False,
     "description": "Development mock data.", "default_trust_score": 0.5},

    # Austin local sources
    {"slug": "do512", "name": "Do512", "source_type": "scraper", "is_local": True,
     "description": "Austin's go-to local events guide. Music, food, comedy, family events.",
     "url": "https://do512.com", "coverage_cities": "Austin", "default_trust_score": 1.2},
    {"slug": "austin-chronicle", "name": "Austin Chronicle", "source_type": "scraper", "is_local": True,
     "description": "Austin Chronicle events calendar. Strong on music, arts, and culture.",
     "url": "https://www.austinchronicle.com/events/", "coverage_cities": "Austin", "default_trust_score": 1.1},
    {"slug": "austin-parks", "name": "Austin Parks & Rec", "source_type": "ical", "is_local": True,
     "description": "City of Austin Parks & Recreation. Free community events, outdoor activities.",
     "url": "https://www.austintexas.gov/department/parks-and-recreation",
     "coverage_cities": "Austin", "default_trust_score": 1.0},
    {"slug": "austin-convention-center", "name": "Austin Convention Center", "source_type": "scraper", "is_local": True,
     "description": "Conventions, trade shows, conferences, and expos.",
     "url": "https://www.austinconventioncenter.com/events",
     "coverage_cities": "Austin", "default_trust_score": 1.0},

    # Nashville local sources
    {"slug": "nashville-scene", "name": "Nashville Scene", "source_type": "scraper", "is_local": True,
     "description": "Nashville's alternative weekly. Comprehensive local event coverage.",
     "url": "https://www.nashvillescene.com/arts-culture/events/",
     "coverage_cities": "Nashville", "default_trust_score": 1.1},
    {"slug": "nashville-guru", "name": "Nashville Guru", "source_type": "scraper", "is_local": True,
     "description": "Local Nashville events guide. Music, food, festivals, nightlife.",
     "url": "https://nashvilleguru.com/events",
     "coverage_cities": "Nashville", "default_trust_score": 1.1},

    # Denver local sources
    {"slug": "303-magazine", "name": "303 Magazine", "source_type": "scraper", "is_local": True,
     "description": "Denver's culture magazine. Music, food, art, fashion events.",
     "url": "https://303magazine.com/events/",
     "coverage_cities": "Denver", "default_trust_score": 1.1},
]


@router.post("")
async def seed_mock_data(
    city: str = "Austin",
    db: AsyncSession = Depends(get_db),
):
    if settings.app_env != "development":
        return {"error": "Seed endpoint only available in development"}

    # Seed event sources
    sources_created = 0
    for source_data in DEFAULT_SOURCES:
        stmt = insert(EventSource).values(**source_data).on_conflict_do_nothing(
            index_elements=["slug"]
        )
        result = await db.execute(stmt)
        if result.rowcount:
            sources_created += 1

    # Seed mock events
    events = generate_mock_events(city)
    event_count = await upsert_events(db, events)

    return {
        "status": "ok",
        "events_seeded": event_count,
        "sources_registered": sources_created,
        "city": city,
    }
