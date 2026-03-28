"""Service to ingest events from adapters and upsert into the database."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.base import NormalizedEvent
from app.models.category import Category
from app.models.event import Event, EventCategory


async def upsert_events(db: AsyncSession, events: list[NormalizedEvent]) -> int:
    """Upsert normalized events into the database. Returns count of upserted events."""
    upserted = 0

    for event in events:
        if event.starts_at is None:
            continue

        stmt = insert(Event).values(
            external_id=event.external_id,
            source=event.source,
            title=event.title,
            description=event.description,
            venue_name=event.venue_name,
            venue_address=event.venue_address,
            city=event.city,
            state=event.state,
            country=event.country,
            latitude=event.latitude,
            longitude=event.longitude,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            on_sale_at=event.on_sale_at,
            price_min=event.price_min,
            price_max=event.price_max,
            currency=event.currency,
            url=event.url,
            image_url=event.image_url,
            status="active",
            raw_data=event.raw_data,
        ).on_conflict_do_update(
            index_elements=["source", "external_id"],
            set_={
                "title": event.title,
                "description": event.description,
                "price_min": event.price_min,
                "price_max": event.price_max,
                "status": "active",
                "image_url": event.image_url,
            },
        ).returning(Event.id)

        result = await db.execute(stmt)
        event_id = result.scalar_one()

        # Link categories
        if event.categories:
            for cat_name in event.categories:
                cat_slug = cat_name.lower().replace(" ", "-")
                # Ensure category exists
                cat_stmt = insert(Category).values(
                    name=cat_name.title(), slug=cat_slug
                ).on_conflict_do_nothing(index_elements=["slug"])
                await db.execute(cat_stmt)

                cat_result = await db.execute(
                    select(Category.id).where(Category.slug == cat_slug)
                )
                cat_id = cat_result.scalar_one()

                ec_stmt = insert(EventCategory).values(
                    event_id=event_id, category_id=cat_id
                ).on_conflict_do_nothing()
                await db.execute(ec_stmt)

        upserted += 1

    await db.commit()
    return upserted
