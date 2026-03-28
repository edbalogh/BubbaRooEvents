from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.category import Category

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
async def list_categories(db: AsyncSession = Depends(get_db)):
    """List all available event categories."""
    result = await db.execute(
        select(Category).order_by(Category.name.asc())
    )
    categories = result.scalars().all()
    return [
        {"id": c.id, "name": c.name, "slug": c.slug, "parent_id": c.parent_id}
        for c in categories
    ]
