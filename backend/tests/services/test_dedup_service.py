import pytest
from unittest.mock import AsyncMock
from app.services.dedup_service import (
    make_venue_slug,
    fuzzy_match_venue_name,
    merge_canonical_event_fields,
    pick_best_field,
)


def test_make_venue_slug_basic():
    assert make_venue_slug("3rd & Lindsley", "Nashville") == "3rd-lindsley-nashville"


def test_make_venue_slug_normalizes():
    assert make_venue_slug("The Ryman Auditorium", "Nashville") == "the-ryman-auditorium-nashville"


def test_make_venue_slug_truncates():
    long_name = "A" * 400
    slug = make_venue_slug(long_name, "Nashville")
    assert len(slug) <= 350


def test_fuzzy_match_venue_name_exact():
    candidates = [
        {"name": "Bluebird Cafe", "city": "Nashville"},
        {"name": "Ryman Auditorium", "city": "Nashville"},
    ]
    match = fuzzy_match_venue_name("Bluebird Cafe", "Nashville", candidates, threshold=85)
    assert match is not None
    assert match["name"] == "Bluebird Cafe"


def test_fuzzy_match_venue_name_close():
    candidates = [{"name": "3rd and Lindsley", "city": "Nashville"}]
    match = fuzzy_match_venue_name("3rd & Lindsley", "Nashville", candidates, threshold=85)
    assert match is not None


def test_fuzzy_match_venue_name_no_match():
    candidates = [{"name": "Ryman Auditorium", "city": "Nashville"}]
    match = fuzzy_match_venue_name("Completely Different Place", "Nashville", candidates, threshold=85)
    assert match is None


def test_fuzzy_match_venue_name_wrong_city():
    candidates = [{"name": "Bluebird Cafe", "city": "Denver"}]
    match = fuzzy_match_venue_name("Bluebird Cafe", "Nashville", candidates, threshold=85)
    assert match is None


def test_pick_best_field_venue_wins_over_ticketmaster():
    values = [
        {"source": "ticketmaster", "value": 45.0},
        {"source": "nashville-venue-scraper", "value": 40.0},
    ]
    result = pick_best_field("price_min", values)
    assert result == 40.0


def test_pick_best_field_longest_description_wins():
    values = [
        {"source": "ticketmaster", "value": "Short desc"},
        {"source": "nashville-scraper", "value": "A much longer and more detailed description of this event"},
    ]
    result = pick_best_field("description", values)
    assert result == "A much longer and more detailed description of this event"


def test_merge_canonical_event_fields_picks_best():
    raw_events = [
        {
            "source": "ticketmaster",
            "title": "Jazz Night",
            "description": "Short",
            "price_min": 45.0,
            "url": "https://ticketmaster.com/jazz",
            "image_url": "https://tm.com/img.jpg",
            "starts_at": "2026-05-01T20:00:00",
        },
        {
            "source": "bluebird-cafe",
            "title": "Jazz Night at Bluebird",
            "description": "A wonderful evening of jazz featuring local musicians in an intimate setting",
            "price_min": 40.0,
            "url": "https://bluebirdcafe.com/events/jazz",
            "image_url": None,
            "starts_at": "2026-05-01T20:00:00",
        },
    ]
    merged = merge_canonical_event_fields(raw_events)
    assert merged["price_min"] == 40.0
    assert "intimate" in merged["description"]
    assert "bluebirdcafe.com" in merged["url"]
    assert "price_min" in merged["conflicts"]
