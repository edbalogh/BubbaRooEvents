import uuid
from datetime import datetime, UTC
from app.models.event import RawEvent


def test_raw_event_has_required_fields():
    e = RawEvent(
        id=uuid.uuid4(),
        source="ticketmaster",
        title="Test Concert",
        starts_at=datetime(2026, 5, 1, 20, 0, tzinfo=UTC),
        status="active",
    )
    assert e.source == "ticketmaster"
    assert e.title == "Test Concert"
    assert e.status == "active"


def test_raw_event_optional_fks_default_none():
    e = RawEvent(
        id=uuid.uuid4(),
        source="ticketmaster",
        title="Test Concert",
        starts_at=datetime(2026, 5, 1, 20, 0, tzinfo=UTC),
    )
    assert e.venue_id is None
    assert e.canonical_event_id is None


def test_raw_event_composite_index_defined():
    # Verify the unique index on (source, external_id) is configured
    table_args = RawEvent.__table_args__
    assert any(
        getattr(idx, "name", None) == "uq_source_external_id"
        for idx in table_args
    )
