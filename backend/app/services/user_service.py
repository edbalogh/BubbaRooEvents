import redis as redis_lib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserRegister
from worker.tasks.ingestion import ingest_city_now

_redis = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)
_INGEST_TTL = 600  # 10 minutes


def _queue_city_ingest_if_needed(city: str) -> None:
    """Fire-and-forget city ingestion, rate-limited by Redis (atomic NX)."""
    redis_key = f"ingest:city:{city.lower()}:last_queued"
    acquired = _redis.set(redis_key, "1", ex=_INGEST_TTL, nx=True)
    if acquired:
        ingest_city_now.delay(city)


async def create_user(db: AsyncSession, data: UserRegister) -> User:
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        home_city=data.home_city,
        home_latitude=data.home_latitude,
        home_longitude=data.home_longitude,
        timezone=data.timezone,
    )
    db.add(user)
    await db.flush()

    if data.home_city:
        _queue_city_ingest_if_needed(data.home_city)

    return user


async def update_user_city(db: AsyncSession, user: User, city: str) -> User:
    """Update user's home_city and queue ingestion for the new city."""
    user.home_city = city
    await db.flush()
    _queue_city_ingest_if_needed(city)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def generate_token(user: User) -> str:
    return create_access_token(subject=str(user.id))
