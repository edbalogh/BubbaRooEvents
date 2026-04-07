import uuid
from app.models.venue import Venue


def test_venue_has_required_fields():
    v = Venue(
        id=uuid.uuid4(),
        name="3rd & Lindsley",
        slug="3rd-and-lindsley-nashville",
        city="Nashville",
        state="TN",
    )
    assert v.name == "3rd & Lindsley"
    assert v.slug == "3rd-and-lindsley-nashville"
    assert v.city == "Nashville"


def test_venue_optional_fields_default_none():
    v = Venue(id=uuid.uuid4(), name="Test Venue", slug="test-venue", city="Nashville", state="TN")
    assert v.address is None
    assert v.lat is None
    assert v.lon is None
    assert v.website_url is None
    assert v.source_slugs is None
