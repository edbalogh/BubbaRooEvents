"""On-demand city ingestion endpoint."""

import redis as redis_lib
from fastapi import APIRouter, Depends
from typing import Annotated

from pydantic import BaseModel
from pydantic import StringConstraints

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models.user import User
from worker.tasks.ingestion import ingest_city_now

router = APIRouter(prefix="/ingest", tags=["ingest"])

_redis = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)

RATE_LIMIT_TTL = 600  # 10 minutes


class IngestCityRequest(BaseModel):
    city: Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]


class IngestCityResponse(BaseModel):
    status: str
    city: str


@router.post("/city", response_model=IngestCityResponse)
async def trigger_city_ingest(
    body: IngestCityRequest,
    user: User = Depends(get_current_user),
):
    """Queue on-demand ingestion for a city. Rate-limited to once per 10 minutes per city."""
    redis_key = f"ingest:city:{body.city.lower()}:last_queued"

    acquired = _redis.set(redis_key, "1", ex=RATE_LIMIT_TTL, nx=True)
    if not acquired:
        return {"status": "already_queued", "city": body.city}

    ingest_city_now.delay(body.city)

    return {"status": "queued", "city": body.city}
