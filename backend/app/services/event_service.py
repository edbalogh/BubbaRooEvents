from datetime import UTC, date, datetime

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.event import Event, EventCategory


def build_event_query(
    q: str | None = None,
    city: str | None = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    price_max: float | None = None,
    sort: str = "date",
) -> Select:
    query = select(Event).where(Event.status == "active")

    if q:
        query = query.where(Event.title.ilike(f"%{q}%"))

    if city:
        query = query.where(func.lower(Event.city) == city.lower())

    if date_from:
        query = query.where(Event.starts_at >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=UTC))

    if date_to:
        query = query.where(Event.starts_at <= datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=UTC))

    if price_max is not None:
        query = query.where(Event.price_min <= price_max)

    if category:
        query = query.join(EventCategory, Event.id == EventCategory.event_id).join(
            Category, EventCategory.category_id == Category.id
        ).where(Category.slug == category)

    if sort == "date":
        query = query.order_by(Event.starts_at.asc())
    elif sort == "price":
        query = query.order_by(Event.price_min.asc().nullslast())

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
) -> tuple[list[Event], int]:
    query = build_event_query(
        q=q, city=city, category=category,
        date_from=date_from, date_to=date_to,
        price_max=price_max, sort=sort,
    )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    events = list(result.scalars().all())

    return events, total


async def get_event_by_id(db: AsyncSession, event_id) -> Event | None:
    result = await db.execute(select(Event).where(Event.id == event_id))
    return result.scalar_one_or_none()


async def get_tonight_events(db: AsyncSession, city: str) -> list[Event]:
    now = datetime.now(UTC)
    end_of_day = now.replace(hour=23, minute=59, second=59)

    query = (
        select(Event)
        .where(
            and_(
                Event.status == "active",
                func.lower(Event.city) == city.lower(),
                Event.starts_at >= now,
                Event.starts_at <= end_of_day,
            )
        )
        .order_by(Event.starts_at.asc())
        .limit(50)
    )
    result = await db.execute(query)
    return list(result.scalars().all())
