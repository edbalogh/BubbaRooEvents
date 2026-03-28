from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.categories import router as categories_router
from app.api.v1.events import router as events_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.preferences import router as preferences_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.seed import router as seed_router
from app.api.v1.sources import router as sources_router
from app.api.v1.trips import router as trips_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(categories_router)
api_router.include_router(events_router)
api_router.include_router(notifications_router)
api_router.include_router(preferences_router)
api_router.include_router(recommendations_router)
api_router.include_router(seed_router)
api_router.include_router(sources_router)
api_router.include_router(trips_router)
