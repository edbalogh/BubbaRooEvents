from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.events import router as events_router
from app.api.v1.preferences import router as preferences_router
from app.api.v1.seed import router as seed_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(events_router)
api_router.include_router(preferences_router)
api_router.include_router(seed_router)
