from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class EventResponse(BaseModel):
    id: UUID
    source: str
    title: str
    description: str | None
    venue_name: str | None
    venue_address: str | None
    city: str | None
    state: str | None
    country: str
    latitude: float | None
    longitude: float | None
    starts_at: datetime
    ends_at: datetime | None
    on_sale_at: datetime | None
    price_min: Decimal | None
    price_max: Decimal | None
    currency: str
    url: str | None
    image_url: str | None
    status: str
    categories: list[str] = []

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    events: list[EventResponse]
    total: int
    page: int
    per_page: int


class EventSearchParams(BaseModel):
    q: str | None = None
    city: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_miles: float = 25.0
    category: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    price_max: float | None = None
    sort: str = "date"
    page: int = 1
    per_page: int = 20
