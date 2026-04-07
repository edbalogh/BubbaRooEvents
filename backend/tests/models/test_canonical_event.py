import uuid
from datetime import datetime, UTC
from app.models.canonical_event import CanonicalEvent


def test_canonical_event_has_required_fields():
    event_id = uuid.uuid4()
    venue_id = uuid.uuid4()
    ce = CanonicalEvent(
        id=event_id,
        title="Test Concert",
        venue_id=venue_id,
        starts_at=datetime(2026, 5, 1, 20, 0, tzinfo=UTC),
        status="active",
    )
    assert ce.title == "Test Concert"
    assert ce.venue_id == venue_id
    assert ce.status == "active"


def test_canonical_event_optional_fields_default_none():
    ce = CanonicalEvent(
        id=uuid.uuid4(),
        title="Test",
        starts_at=datetime(2026, 5, 1, 20, 0, tzinfo=UTC),
        status="active",
    )
    assert ce.conflicts is None
    assert ce.field_sources is None
    assert ce.is_duplicate_of is None
