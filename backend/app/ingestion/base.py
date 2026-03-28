from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol


@dataclass
class NormalizedEvent:
    external_id: str
    source: str
    title: str
    description: str | None = None
    venue_name: str | None = None
    venue_address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str = "US"
    latitude: float | None = None
    longitude: float | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    on_sale_at: datetime | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    currency: str = "USD"
    url: str | None = None
    image_url: str | None = None
    categories: list[str] | None = None
    raw_data: dict | None = None


class EventSourceAdapter(Protocol):
    source_name: str

    async def fetch_events(
        self, city: str, date_from: date, date_to: date
    ) -> list[NormalizedEvent]: ...
