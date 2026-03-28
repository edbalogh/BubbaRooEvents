from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserRegister


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
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def generate_token(user: User) -> str:
    return create_access_token(subject=str(user.id))
