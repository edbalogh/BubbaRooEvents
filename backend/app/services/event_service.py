from datetime import UTC, date, datetime

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canonical_event import CanonicalEvent
from app.models.venue import Venue


def build_event_query(
    q: str | None = None,
    city: str | None = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    price_max: float | None = None,
    sort: str = "date",
) -> Select:
    query = select(CanonicalEvent).where(
        CanonicalEvent.status == "active",
        CanonicalEvent.is_duplicate_of.is_(None),
    )

    if q:
        query = query.where(CanonicalEvent.title.ilike(f"%{q}%"))

    if city:
        query = (
            query
            .join(Venue, CanonicalEvent.venue_id == Venue.id, isouter=True)
            .where(func.lower(Venue.city) == city.lower())
        )

    if date_from:
        query = query.where(
            CanonicalEvent.starts_at >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=UTC)
        )

    if date_to:
        query = query.where(
            CanonicalEvent.starts_at <= datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=UTC)
        )

    if price_max is not None:
        query = query.where(CanonicalEvent.price_min <= price_max)

    if sort == "date":
        query = query.order_by(CanonicalEvent.starts_at.asc())
    elif sort == "price":
        query = query.order_by(CanonicalEvent.price_min.asc().nullslast())

    return query


async def search_events(
    db: AsyncSession,
    q: str | None = None,
    city: str | None = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    price_max: float | None = None,
    sort: str = "date",
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[CanonicalEvent], int]:
    query = build_event_query(
        q=q, city=city, category=category,
        date_from=date_from, date_to=date_to,
        price_max=price_max, sort=sort,
    )

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    events = list(result.scalars().all())

    return events, total


async def get_event_by_id(db: AsyncSession, event_id) -> CanonicalEvent | None:
    result = await db.execute(select(CanonicalEvent).where(CanonicalEvent.id == event_id))
    return result.scalar_one_or_none()


async def get_tonight_events(db: AsyncSession, city: str) -> list[CanonicalEvent]:
    now = datetime.now(UTC)
    end_of_day = now.replace(hour=23, minute=59, second=59)

    query = (
        select(CanonicalEvent)
        .join(Venue, CanonicalEvent.venue_id == Venue.id, isouter=True)
        .where(
            and_(
                CanonicalEvent.status == "active",
                CanonicalEvent.is_duplicate_of.is_(None),
                func.lower(Venue.city) == city.lower(),
                CanonicalEvent.starts_at >= now,
                CanonicalEvent.starts_at <= end_of_day,
            )
        )
        .order_by(CanonicalEvent.starts_at.asc())
        .limit(50)
    )
    result = await db.execute(query)
    return list(result.scalars().all())
