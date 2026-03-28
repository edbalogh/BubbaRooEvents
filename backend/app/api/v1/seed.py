"""Endpoint to seed mock data (development only)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.ingestion.ingest_service import upsert_events
from app.ingestion.mock_data import generate_mock_events

router = APIRouter(prefix="/seed", tags=["dev"])


@router.post("")
async def seed_mock_data(
    city: str = "Austin",
    db: AsyncSession = Depends(get_db),
):
    if settings.app_env != "development":
        return {"error": "Seed endpoint only available in development"}

    events = generate_mock_events(city)
    count = await upsert_events(db, events)
    return {"status": "ok", "events_seeded": count, "city": city}
