# Home City Detection & Hierarchical Preferences Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded Austin city, mock data, and flat preferences with live city detection, on-demand ingestion, and a 3-step preferences wizard with MusicBrainz artist lookup.

**Architecture:** Five independent task groups: (1) strip mock data, (2) add dynamic city ingestion backend, (3) home page city detection + loading UI, (4) Settings tab restructure + preferences wizard, (5) artist preference model + API. Each group is independently committable and testable. The frontend calls a new `POST /api/v1/ingest/city` endpoint which queues a Celery task; the home page polls for events until they arrive. The preferences wizard is purely frontend-driven with a static genre taxonomy map; it writes to the existing `PUT /me/preferences` endpoint for category weights and to new `POST /me/artists` endpoints for artist data.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Celery, Redis, PostgreSQL, Alembic, pytest + pytest-asyncio + respx, React 19, TypeScript, Tailwind CSS, MusicBrainz REST API (public, no key needed)

---

## File Map

### Backend — new / modified files

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/ingestion/mock_data.py` | **Delete** | Mock events — gone |
| `backend/app/api/v1/seed.py` | **Delete** | Mock seed endpoint — gone |
| `backend/app/api/v1/router.py` | Modify | Remove seed import/include, add ingest include |
| `backend/app/core/config.py` | Modify | Remove `use_mock_data`, add nothing (simplify) |
| `backend/worker/tasks/ingestion.py` | Modify | Remove mock task, add `ingest_city_now`, dynamic city list |
| `backend/worker/celery_app.py` | Modify | Remove mock beat entry |
| `backend/app/api/v1/ingest.py` | **Create** | `POST /api/v1/ingest/city` endpoint |
| `backend/app/models/user.py` | Modify | Add `UserArtistPreference` model |
| `backend/app/api/v1/artists.py` | **Create** | `GET/POST/DELETE /me/artists` endpoints |
| `backend/alembic/versions/<rev>_add_artist_preferences.py` | **Create** | Migration for `user_artist_preferences` table |
| `backend/tests/api/test_ingest.py` | **Create** | Tests for ingest/city endpoint |
| `backend/tests/api/test_artists.py` | **Create** | Tests for artist preference endpoints |

### Frontend — new / modified files

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/src/pages/Home.tsx` | Modify | Read home city, trigger seeding, show loading screen |
| `frontend/src/hooks/useCitySeeding.ts` | **Create** | Check → trigger → poll → resolve logic |
| `frontend/src/components/CityLoadingScreen.tsx` | **Create** | Full-page loading state UI |
| `frontend/src/pages/Settings.tsx` | Modify | Add tab bar, delegate to tab components |
| `frontend/src/components/settings/GeneralTab.tsx` | **Create** | Distance, home city, timezone |
| `frontend/src/components/settings/PreferencesTab.tsx` | **Create** | 3-step wizard container |
| `frontend/src/components/settings/NotificationsTab.tsx` | **Create** | Extracted notification settings |
| `frontend/src/components/settings/SourcesTab.tsx` | **Create** | Extracted source settings |
| `frontend/src/components/settings/genreMap.ts` | **Create** | Static top-level type → genre → slug mapping |
| `frontend/src/api/client.ts` | Modify | Add `ingestCity`, `getArtists`, `addArtist`, `removeArtist` |

---

## Task 1: Remove Mock Data Infrastructure

**Files:**
- Delete: `backend/app/ingestion/mock_data.py`
- Delete: `backend/app/api/v1/seed.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/worker/tasks/ingestion.py`
- Modify: `backend/worker/celery_app.py`
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Delete mock data files**

```bash
rm backend/app/ingestion/mock_data.py
rm backend/app/api/v1/seed.py
```

- [ ] **Step 2: Remove seed router from router.py**

Replace the contents of `backend/app/api/v1/router.py`:

```python
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.categories import router as categories_router
from app.api.v1.events import router as events_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.preferences import router as preferences_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.sources import router as sources_router
from app.api.v1.trips import router as trips_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(categories_router)
api_router.include_router(events_router)
api_router.include_router(notifications_router)
api_router.include_router(preferences_router)
api_router.include_router(recommendations_router)
api_router.include_router(sources_router)
api_router.include_router(trips_router)
```

- [ ] **Step 3: Remove mock task and import from ingestion.py**

In `backend/worker/tasks/ingestion.py`, remove these lines:

```python
# Remove this import at the top:
from app.ingestion.mock_data import generate_mock_events

# Remove this entire function:
async def _run_mock_ingestion():
    total = 0
    async with _session_factory() as db:
        for city in INGEST_CITIES:
            events = generate_mock_events(city)
            count = await upsert_events(db, events)
            total += count
    return total

# Remove this entire task:
@celery_app.task(name="worker.tasks.ingestion.ingest_mock_events")
def ingest_mock_events():
    """Ingest mock events for development."""
    if not settings.use_mock_data:
        return "Skipped: Mock data disabled"
    count = asyncio.run(_run_mock_ingestion())
    return f"Ingested {count} mock events"
```

- [ ] **Step 4: Remove mock beat entry from celery_app.py**

In `backend/worker/celery_app.py`, remove this block from `beat_schedule`:

```python
# Remove:
"ingest-mock-events": {
    "task": "worker.tasks.ingestion.ingest_mock_events",
    "schedule": 3600.0,  # every hour (development only)
},
```

- [ ] **Step 5: Remove use_mock_data and app_env from config.py**

In `backend/app/core/config.py`, remove these two lines:

```python
    app_env: str = "development"
    use_mock_data: bool = True
```

Also remove from `.env` and `.env.example`:
```
APP_ENV=development
USE_MOCK_DATA=true
```

- [ ] **Step 6: Verify the app still imports cleanly**

```bash
cd backend && python -c "from app.main import app; print('OK')"
```

Expected: `OK` with no import errors.

```bash
cd backend && python -c "from worker.celery_app import celery_app; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Run existing tests to confirm nothing broke**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all 10 existing tests pass.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: remove all mock data infrastructure, live data only"
```

---

## Task 2: Dynamic City List + ingest_city_now Celery Task

**Files:**
- Modify: `backend/worker/tasks/ingestion.py`
- Create: `backend/tests/worker/test_ingest_city_now.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/worker/__init__.py` (empty) and `backend/tests/worker/test_ingest_city_now.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_get_active_cities_returns_user_cities():
    """_get_active_cities merges hardcoded defaults with user home_cities."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["Nashville", "Denver", "Portland"]

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("worker.tasks.ingestion._session_factory") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        from worker.tasks.ingestion import _get_active_cities
        cities = await _get_active_cities()

    # Must include defaults even if not in DB
    assert "Austin" in cities
    assert "Nashville" in cities
    assert "Denver" in cities
    # Returns dict with (lat, lon) tuples
    assert isinstance(cities["Austin"], tuple)
    assert len(cities["Austin"]) == 2


@pytest.mark.asyncio
async def test_get_active_cities_deduplicates():
    """Cities in both DB and defaults are not duplicated."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["Austin", "Nashville"]

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("worker.tasks.ingestion._session_factory") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        from worker.tasks.ingestion import _get_active_cities
        cities = await _get_active_cities()

    city_list = list(cities.keys())
    assert city_list.count("Austin") == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/worker/test_ingest_city_now.py -v
```

Expected: `ImportError` — `_get_active_cities` doesn't exist yet.

- [ ] **Step 3: Add `_get_active_cities` and `ingest_city_now` to ingestion.py**

Add these to `backend/worker/tasks/ingestion.py` after the existing `INGEST_CITIES` dict. Also replace `INGEST_CITIES` usage in the scheduled helpers to call `_get_active_cities()` dynamically.

First add the import at the top of the file:
```python
from sqlalchemy import select, text
from app.models.user import User
import redis as redis_lib
```

Then add after `INGEST_CITIES`:

```python
# Default always-on cities (used even if no users registered)
_DEFAULT_CITIES = {
    "Austin": (30.2672, -97.7431),
    "Nashville": (36.1627, -86.7816),
}

# Redis client for rate-limiting on-demand ingestion
_redis = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)


async def _get_active_cities() -> dict[str, tuple[float, float]]:
    """Return merged dict of default cities + all user home_cities."""
    cities = dict(_DEFAULT_CITIES)

    async with _session_factory() as db:
        result = await db.execute(
            select(User.home_city).where(User.home_city.isnot(None)).distinct()
        )
        user_cities = result.scalars().all()

    for city in user_cities:
        if city not in cities:
            # Unknown city: use (0, 0) coords — adapters that don't need coords will work fine;
            # geo-based adapters will skip gracefully
            cities[city] = (0.0, 0.0)

    return cities
```

Then add the new Celery task at the bottom of the file:

```python
@celery_app.task(name="worker.tasks.ingestion.ingest_city_now")
def ingest_city_now(city: str):
    """On-demand ingestion for a single city across all adapters."""
    async def _run():
        today = datetime.now(UTC).date()
        date_to = today + timedelta(days=30)
        total = 0

        async with _session_factory() as db:
            # Ticketmaster
            if settings.ticketmaster_api_key:
                try:
                    adapter = TicketmasterAdapter()
                    events = await adapter.fetch_events(city, today, date_to)
                    total += await upsert_events(db, events)
                    logger.info(f"[ingest_city_now][ticketmaster] {city}: {len(events)} events")
                except Exception as e:
                    logger.error(f"[ingest_city_now][ticketmaster] {city} failed: {e}")

            # SeatGeek
            if settings.seatgeek_client_id:
                try:
                    adapter = SeatGeekAdapter()
                    events = await adapter.fetch_events(city, today, date_to)
                    total += await upsert_events(db, events)
                    logger.info(f"[ingest_city_now][seatgeek] {city}: {len(events)} events")
                except Exception as e:
                    logger.error(f"[ingest_city_now][seatgeek] {city} failed: {e}")

            # Bandsintown
            try:
                adapter = BandsintownAdapter()
                events = await adapter.fetch_events(city, today, date_to, lat=0, lon=0)
                total += await upsert_events(db, events)
                logger.info(f"[ingest_city_now][bandsintown] {city}: {len(events)} events")
            except Exception as e:
                logger.error(f"[ingest_city_now][bandsintown] {city} failed: {e}")

            # Eventbrite
            try:
                adapter = EventbriteAdapter()
                events = await adapter.fetch_events(city, today, date_to, lat=0, lon=0)
                total += await upsert_events(db, events)
                logger.info(f"[ingest_city_now][eventbrite] {city}: {len(events)} events")
            except Exception as e:
                logger.error(f"[ingest_city_now][eventbrite] {city} failed: {e}")

        return total

    count = asyncio.run(_run())
    logger.info(f"[ingest_city_now] {city}: {count} total events ingested")
    return f"Ingested {count} events for {city}"
```

Also update `_run_ticketmaster_ingestion` and other scheduled runners to use `_get_active_cities()` instead of the hardcoded `INGEST_CITIES`:

```python
async def _run_ticketmaster_ingestion():
    adapter = TicketmasterAdapter()
    today = datetime.now(UTC).date()
    date_to = today + timedelta(days=30)
    cities = await _get_active_cities()

    total = 0
    async with _session_factory() as db:
        for city in cities:
            try:
                events = await adapter.fetch_events(city, today, date_to)
                count = await upsert_events(db, events)
                total += count
            except Exception as e:
                logger.error(f"[ticketmaster] {city} failed: {e}")
    return total
```

Apply the same `cities = await _get_active_cities()` replacement to `_run_adapter_ingestion` (replace `INGEST_CITIES.items()` with `(await _get_active_cities()).items()`).

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/worker/test_ingest_city_now.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/worker/tasks/ingestion.py backend/tests/worker/
git commit -m "feat: add ingest_city_now task and dynamic city list from user home_city"
```

---

## Task 3: On-Demand Ingest API Endpoint

**Files:**
- Create: `backend/app/api/v1/ingest.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `backend/tests/api/test_ingest.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/api/__init__.py` (empty if not exists) and `backend/tests/api/test_ingest.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def auth_headers(monkeypatch):
    """Patch get_current_user to return a fake user."""
    import uuid
    from app.models.user import User
    fake_user = User(
        id=uuid.uuid4(),
        email="test@test.com",
        password_hash="x",
        display_name="Test",
        home_city="Nashville",
    )

    async def _fake_user():
        return fake_user

    monkeypatch.setattr("app.api.v1.ingest.get_current_user", _fake_user)
    return {"Authorization": "Bearer faketoken"}


@pytest.mark.asyncio
async def test_ingest_city_queues_task(auth_headers):
    with patch("app.api.v1.ingest.ingest_city_now") as mock_task, \
         patch("app.api.v1.ingest._redis") as mock_redis:
        mock_redis.get.return_value = None  # not rate-limited
        mock_task.delay = MagicMock()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/ingest/city",
                json={"city": "Nashville"},
                headers=auth_headers,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["city"] == "Nashville"
    mock_task.delay.assert_called_once_with("Nashville")


@pytest.mark.asyncio
async def test_ingest_city_rate_limited(auth_headers):
    with patch("app.api.v1.ingest.ingest_city_now") as mock_task, \
         patch("app.api.v1.ingest._redis") as mock_redis:
        mock_redis.get.return_value = "1"  # already queued recently

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/ingest/city",
                json={"city": "Nashville"},
                headers=auth_headers,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "already_queued"
    mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_city_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/ingest/city", json={"city": "Nashville"})
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/api/test_ingest.py -v
```

Expected: `ImportError` or `404` — endpoint doesn't exist yet.

- [ ] **Step 3: Create `backend/app/api/v1/ingest.py`**

```python
"""On-demand city ingestion endpoint."""

import redis as redis_lib
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models.user import User
from worker.tasks.ingestion import ingest_city_now

router = APIRouter(prefix="/ingest", tags=["ingest"])

_redis = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)

RATE_LIMIT_TTL = 600  # 10 minutes


class IngestCityRequest(BaseModel):
    city: str


@router.post("/city")
async def trigger_city_ingest(
    body: IngestCityRequest,
    user: User = Depends(get_current_user),
):
    """Queue on-demand ingestion for a city. Rate-limited to once per 10 minutes per city."""
    redis_key = f"ingest:city:{body.city.lower()}:last_queued"

    if _redis.get(redis_key):
        return {"status": "already_queued", "city": body.city}

    ingest_city_now.delay(body.city)
    _redis.setex(redis_key, RATE_LIMIT_TTL, "1")

    return {"status": "queued", "city": body.city}
```

- [ ] **Step 4: Register the router in `backend/app/api/v1/router.py`**

Add to `router.py`:

```python
from app.api.v1.ingest import router as ingest_router
# ...
api_router.include_router(ingest_router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/api/test_ingest.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/ingest.py backend/app/api/v1/router.py backend/tests/api/test_ingest.py
git commit -m "feat: add POST /api/v1/ingest/city endpoint with Redis rate limiting"
```

---

## Task 4: Trigger Ingestion on User Registration / City Update

**Files:**
- Modify: `backend/app/services/user_service.py`
- Modify: `backend/app/api/v1/preferences.py` (the `update_home_city` endpoint if it exists, or add it)

- [ ] **Step 1: Add ingestion trigger to `create_user` in user_service.py**

Replace the entire `backend/app/services/user_service.py`:

```python
import redis as redis_lib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserRegister

_redis = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)
_INGEST_TTL = 600  # 10 minutes


def _queue_city_ingest_if_needed(city: str) -> None:
    """Fire-and-forget city ingestion, rate-limited by Redis."""
    redis_key = f"ingest:city:{city.lower()}:last_queued"
    if not _redis.get(redis_key):
        from worker.tasks.ingestion import ingest_city_now
        ingest_city_now.delay(city)
        _redis.setex(redis_key, _INGEST_TTL, "1")


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
```

- [ ] **Step 2: Add `PUT /me/city` endpoint to preferences.py**

At the end of `backend/app/api/v1/preferences.py`, add:

```python
from app.services.user_service import update_user_city
from pydantic import BaseModel as PydanticBase

class UpdateCityRequest(PydanticBase):
    city: str

@router.put("/city")
async def update_home_city(
    body: UpdateCityRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the user's home city and queue ingestion for it."""
    await update_user_city(db, user, body.city)
    await db.commit()
    return {"home_city": body.city}
```

- [ ] **Step 3: Verify the app imports cleanly**

```bash
cd backend && python -c "from app.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/user_service.py backend/app/api/v1/preferences.py
git commit -m "feat: trigger city ingestion on user registration and home_city update"
```

---

## Task 5: UserArtistPreference Model + Migration + Artist API

**Files:**
- Modify: `backend/app/models/user.py`
- Create: `backend/alembic/versions/<rev>_add_artist_preferences.py`
- Create: `backend/app/api/v1/artists.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `backend/tests/api/test_artists.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/api/test_artists.py`:

```python
import uuid
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.user import User


@pytest.fixture
def fake_user():
    return User(
        id=uuid.uuid4(),
        email="test@test.com",
        password_hash="x",
        display_name="Test",
        home_city="Austin",
    )


@pytest.fixture
def auth_headers(monkeypatch, fake_user):
    async def _fake_user():
        return fake_user
    monkeypatch.setattr("app.api.v1.artists.get_current_user", _fake_user)
    return {"Authorization": "Bearer faketoken"}


@pytest.mark.asyncio
async def test_add_artist(auth_headers, fake_user):
    with patch("app.api.v1.artists.get_db") as mock_db_dep:
        mock_db = AsyncMock()
        mock_db.add = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db_dep.return_value = mock_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/me/artists",
                json={
                    "artist_name": "Radiohead",
                    "musicbrainz_id": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
                    "mb_genres": ["rock", "alternative"],
                    "genre_context": "rock",
                },
                headers=auth_headers,
            )

    assert resp.status_code == 201
    data = resp.json()
    assert data["artist_name"] == "Radiohead"
    assert data["genre_context"] == "rock"


@pytest.mark.asyncio
async def test_add_artist_max_3_per_genre(auth_headers, fake_user):
    """Adding a 4th artist for the same genre_context returns 400."""
    from app.models.user import UserArtistPreference

    existing = [
        UserArtistPreference(user_id=fake_user.id, artist_name=f"Artist{i}", genre_context="rock", weight=2.0)
        for i in range(3)
    ]

    with patch("app.api.v1.artists.get_db") as mock_db_dep:
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db_dep.return_value = mock_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/me/artists",
                json={"artist_name": "NewArtist", "genre_context": "rock"},
                headers=auth_headers,
            )

    assert resp.status_code == 400
    assert "maximum" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_artists_returns_list(auth_headers, fake_user):
    from app.models.user import UserArtistPreference

    artists = [
        UserArtistPreference(user_id=fake_user.id, artist_name="Radiohead", genre_context="rock", weight=2.0),
    ]

    with patch("app.api.v1.artists.get_db") as mock_db_dep:
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = artists
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db_dep.return_value = mock_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/me/artists", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["artist_name"] == "Radiohead"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/api/test_artists.py -v
```

Expected: `ImportError` — `UserArtistPreference` doesn't exist yet.

- [ ] **Step 3: Add `UserArtistPreference` to `backend/app/models/user.py`**

Add after the `UserPreference` class:

```python
from sqlalchemy import ARRAY, Text

class UserArtistPreference(Base):
    __tablename__ = "user_artist_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    artist_name: Mapped[str] = mapped_column(String(255), nullable=False)
    musicbrainz_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mb_genres: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    genre_context: Mapped[str] = mapped_column(String(100), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=2.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship()
```

Also add `ARRAY` and `Text` to the imports at the top of the file:
```python
from sqlalchemy import ARRAY, DateTime, Float, ForeignKey, Integer, String, Text, func
```

- [ ] **Step 4: Generate Alembic migration**

```bash
cd backend && alembic revision --autogenerate -m "add_artist_preferences"
```

Check the generated file in `backend/alembic/versions/`. It should contain `create_table('user_artist_preferences', ...)`. If the autogenerate misses the ARRAY type, manually edit to ensure it uses `postgresql.ARRAY(sa.Text())`.

- [ ] **Step 5: Run migration**

```bash
cd backend && alembic upgrade head
```

Expected: `Running upgrade ... -> <rev>, add_artist_preferences`

- [ ] **Step 6: Create `backend/app/api/v1/artists.py`**

```python
"""Artist preference endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, UserArtistPreference

router = APIRouter(prefix="/me/artists", tags=["artists"])

MAX_ARTISTS_PER_GENRE = 3


class AddArtistRequest(BaseModel):
    artist_name: str
    musicbrainz_id: str | None = None
    mb_genres: list[str] | None = None
    genre_context: str


class ArtistResponse(BaseModel):
    id: int
    artist_name: str
    musicbrainz_id: str | None
    mb_genres: list[str] | None
    genre_context: str
    weight: float

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ArtistResponse])
async def get_artists(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserArtistPreference).where(UserArtistPreference.user_id == user.id)
    )
    return result.scalars().all()


@router.post("", response_model=ArtistResponse, status_code=status.HTTP_201_CREATED)
async def add_artist(
    body: AddArtistRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Check max 3 per genre
    result = await db.execute(
        select(UserArtistPreference).where(
            UserArtistPreference.user_id == user.id,
            UserArtistPreference.genre_context == body.genre_context,
        )
    )
    existing = result.scalars().all()
    if len(existing) >= MAX_ARTISTS_PER_GENRE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_ARTISTS_PER_GENRE} artists per genre.",
        )

    artist = UserArtistPreference(
        user_id=user.id,
        artist_name=body.artist_name,
        musicbrainz_id=body.musicbrainz_id,
        mb_genres=body.mb_genres,
        genre_context=body.genre_context,
    )
    db.add(artist)
    await db.flush()
    await db.commit()
    await db.refresh(artist)
    return artist


@router.delete("/{artist_name}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_artist(
    artist_name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserArtistPreference).where(
            UserArtistPreference.user_id == user.id,
            UserArtistPreference.artist_name == artist_name,
        )
    )
    artist = result.scalar_one_or_none()
    if artist:
        await db.delete(artist)
        await db.commit()
```

- [ ] **Step 7: Register artists router in `router.py`**

```python
from app.api.v1.artists import router as artists_router
# ...
api_router.include_router(artists_router)
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/api/test_artists.py -v
```

Expected: `3 passed`

- [ ] **Step 9: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 10: Commit**

```bash
git add backend/app/models/user.py backend/app/api/v1/artists.py backend/app/api/v1/router.py backend/alembic/versions/ backend/tests/api/test_artists.py
git commit -m "feat: add UserArtistPreference model, migration, and artist preference API"
```

---

## Task 6: Frontend API Client Updates

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add new API methods to `frontend/src/api/client.ts`**

Add these interfaces and methods to the existing `client.ts`:

After the existing interfaces, add:

```typescript
export interface ArtistPreference {
  id: number
  artist_name: string
  musicbrainz_id: string | null
  mb_genres: string[] | null
  genre_context: string
  weight: number
}

export interface AddArtistRequest {
  artist_name: string
  musicbrainz_id?: string
  mb_genres?: string[]
  genre_context: string
}

export interface MusicBrainzArtist {
  id: string
  name: string
  tags?: { name: string; count: number }[]
  country?: string
}
```

Then add to the `api` object:

```typescript
  // City ingestion
  ingestCity(city: string): Promise<{ status: string; city: string }> {
    return request('/ingest/city', {
      method: 'POST',
      body: JSON.stringify({ city }),
    })
  },

  // Artist preferences
  getArtists(): Promise<ArtistPreference[]> {
    return request('/me/artists')
  },

  addArtist(data: AddArtistRequest): Promise<ArtistPreference> {
    return request('/me/artists', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  removeArtist(artistName: string): Promise<void> {
    return request(`/me/artists/${encodeURIComponent(artistName)}`, { method: 'DELETE' })
  },

  updateHomeCity(city: string): Promise<{ home_city: string }> {
    return request('/me/city', {
      method: 'PUT',
      body: JSON.stringify({ city }),
    })
  },

  // MusicBrainz artist search (called directly from frontend, no backend proxy)
  async searchMusicBrainzArtists(query: string): Promise<MusicBrainzArtist[]> {
    const resp = await fetch(
      `https://musicbrainz.org/ws/2/artist?query=${encodeURIComponent(query)}&fmt=json&limit=5`,
      { headers: { 'User-Agent': 'BubbaRooEvents/0.1 (dev)' } }
    )
    if (!resp.ok) return []
    const data = await resp.json()
    return data.artists ?? []
  },
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add ingestCity, artist preference, and MusicBrainz API methods to client"
```

---

## Task 7: useCitySeeding Hook + CityLoadingScreen Component

**Files:**
- Create: `frontend/src/hooks/useCitySeeding.ts`
- Create: `frontend/src/components/CityLoadingScreen.tsx`

- [ ] **Step 1: Create `frontend/src/hooks/useCitySeeding.ts`**

```typescript
import { useState, useEffect, useRef } from 'react'
import { api, type Event } from '../api/client'

type SeedingState = 'checking' | 'seeding' | 'done' | 'error'

interface UseCitySeedingResult {
  state: SeedingState
  events: Event[]
  eventCount: number
  city: string
}

const POLL_INTERVAL_MS = 3000
const TIMEOUT_MS = 90000

export function useCitySeeding(city: string): UseCitySeedingResult {
  const [state, setState] = useState<SeedingState>('checking')
  const [events, setEvents] = useState<Event[]>([])
  const [eventCount, setEventCount] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const startedRef = useRef(false)

  useEffect(() => {
    if (!city || startedRef.current) return
    startedRef.current = true

    const cleanup = () => {
      if (timerRef.current) clearInterval(timerRef.current)
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }

    const checkAndSeed = async () => {
      try {
        // Check if city has events already
        const initial = await api.searchEvents({ city, per_page: '1' })
        if (initial.total > 0) {
          setEventCount(initial.total)
          setState('done')
          return
        }

        // No events — trigger ingestion and start polling
        setState('seeding')
        try {
          await api.ingestCity(city)
        } catch {
          // Ingest endpoint failure is non-fatal — still poll
        }

        // Timeout after 90s
        timeoutRef.current = setTimeout(() => {
          cleanup()
          setState('error')
        }, TIMEOUT_MS)

        // Poll every 3s for events
        timerRef.current = setInterval(async () => {
          try {
            const data = await api.searchEvents({ city, per_page: '5' })
            if (data.total > 0) {
              setEvents(data.events)
              setEventCount(data.total)
              cleanup()
              setState('done')
            }
          } catch {
            // ignore poll errors, keep trying
          }
        }, POLL_INTERVAL_MS)
      } catch {
        setState('error')
      }
    }

    checkAndSeed()
    return cleanup
  }, [city])

  return { state, events, eventCount, city }
}
```

- [ ] **Step 2: Create `frontend/src/components/CityLoadingScreen.tsx`**

```typescript
import type { Event } from '../api/client'

interface CityLoadingScreenProps {
  city: string
  events: Event[]
  eventCount: number
  isError: boolean
}

export default function CityLoadingScreen({ city, events, eventCount, isError }: CityLoadingScreenProps) {
  const progress = Math.min(100, (eventCount / 10) * 100)

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <div className="text-4xl mb-4">😕</div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          Couldn't find events for {city}
        </h2>
        <p className="text-gray-500 text-sm">
          We couldn't load events right now. Try searching for another city.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4 space-y-6 max-w-md mx-auto">
      <div className="text-5xl">🎉</div>

      <div>
        <h2 className="text-2xl font-bold text-gray-900">Setting up {city} for you</h2>
        <p className="text-gray-500 mt-1 text-sm">Finding the best events in your city…</p>
      </div>

      <div className="w-full space-y-2">
        <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
          <div
            className="h-2 rounded-full bg-brand-600 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="text-sm text-gray-500">
          {eventCount > 0 ? `${eventCount} events found` : 'Searching…'}
        </p>
      </div>

      {events.length > 0 && (
        <div className="w-full text-left bg-gray-50 rounded-xl p-4 space-y-2">
          {events.slice(0, 5).map((e) => (
            <div key={e.id} className="text-sm text-gray-700 flex items-start gap-2">
              <span className="text-green-500 mt-0.5">✓</span>
              <span>{e.title}</span>
            </div>
          ))}
          {eventCount > 5 && (
            <div className="text-sm text-gray-400 flex items-center gap-2">
              <span className="animate-pulse">⏳</span>
              <span>Finding more…</span>
            </div>
          )}
        </div>
      )}

      <p className="text-xs text-gray-400">This usually takes under a minute</p>
    </div>
  )
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useCitySeeding.ts frontend/src/components/CityLoadingScreen.tsx
git commit -m "feat: add useCitySeeding hook and CityLoadingScreen component"
```

---

## Task 8: Update Home.tsx to Use Home City + Loading Screen

**Files:**
- Modify: `frontend/src/pages/Home.tsx`

- [ ] **Step 1: Replace `frontend/src/pages/Home.tsx`**

```typescript
import { useEffect, useState, useCallback } from 'react'
import { api, type Event } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useCitySeeding } from '../hooks/useCitySeeding'
import SearchBar from '../components/SearchBar'
import EventList from '../components/EventList'
import CityLoadingScreen from '../components/CityLoadingScreen'

export default function Home() {
  const { user } = useAuth()
  const defaultCity = user?.home_city ?? 'Austin'

  const [events, setEvents] = useState<Event[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [searchParams, setSearchParams] = useState<Record<string, string>>({ city: defaultCity })

  const { state: seedState, events: seedEvents, eventCount, city: seedCity } = useCitySeeding(defaultCity)

  const loadEvents = useCallback(async (params: Record<string, string>) => {
    setLoading(true)
    try {
      const data = await api.searchEvents(params)
      setEvents(data.events)
      setTotal(data.total)
    } catch (err) {
      console.error('Failed to load events:', err)
      setEvents([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [])

  // Once seeding resolves to 'done', load the full event list
  useEffect(() => {
    if (seedState === 'done') {
      loadEvents(searchParams)
    }
  }, [seedState, searchParams, loadEvents])

  const handleSearch = (params: { q?: string; city?: string; category?: string }) => {
    const newParams: Record<string, string> = {}
    if (params.q) newParams.q = params.q
    newParams.city = params.city ?? defaultCity
    if (params.category) newParams.category = params.category
    setSearchParams(newParams)
  }

  // Show loading screen while seeding
  if (seedState === 'checking' || seedState === 'seeding') {
    return (
      <CityLoadingScreen
        city={seedCity}
        events={seedEvents}
        eventCount={eventCount}
        isError={false}
      />
    )
  }

  if (seedState === 'error') {
    return (
      <CityLoadingScreen
        city={seedCity}
        events={[]}
        eventCount={0}
        isError={true}
      />
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Discover Events</h1>
        <p className="text-gray-500 mt-1">
          Find concerts, shows, meetups, and more
          {defaultCity ? ` in ${defaultCity}` : ' near you'}
        </p>
      </div>
      <SearchBar onSearch={handleSearch} />
      <EventList events={events} loading={loading} total={total} />
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Smoke test in browser**

```bash
docker compose restart api
```

Open http://localhost:5173. If logged in with a home city set, should see the loading screen briefly, then the event list. If logged out, should default to Austin.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Home.tsx
git commit -m "feat: home page uses user home city with live seeding and loading screen"
```

---

## Task 9: Genre Map + Settings Tab Structure

**Files:**
- Create: `frontend/src/components/settings/genreMap.ts`
- Create: `frontend/src/components/settings/GeneralTab.tsx`
- Create: `frontend/src/components/settings/NotificationsTab.tsx`
- Create: `frontend/src/components/settings/SourcesTab.tsx`

- [ ] **Step 1: Create `frontend/src/components/settings/genreMap.ts`**

```typescript
export interface GenreEntry {
  label: string
  slugs: string[]        // maps to existing category slugs in DB
  subGenreSlugs?: string[] // optional deeper slugs shown in step 3
}

export interface EventTypeEntry {
  label: string
  emoji: string
  genres: GenreEntry[]
}

export const EVENT_TYPE_MAP: EventTypeEntry[] = [
  {
    label: 'Music',
    emoji: '🎵',
    genres: [
      { label: 'Rock', slugs: ['rock', 'indie-rock', 'alternative-rock', 'classic-rock'], subGenreSlugs: ['indie-rock', 'alternative', 'hard-rock', 'punk', 'metal', 'southern-rock', 'folk-rock', 'roots-rock'] },
      { label: 'Pop', slugs: ['pop', 'indie-pop', 'dance-pop', 'synth-pop', 'electro-pop'], subGenreSlugs: ['indie-pop', 'dance-pop', 'synth-pop', 'electro-pop', 'pop-rock'] },
      { label: 'Hip-Hop / Rap', slugs: ['hip-hop/rap', 'trap'], subGenreSlugs: ['trap'] },
      { label: 'Country', slugs: ['country', 'country-folk', 'classic-country', 'contemporary-country', 'americana', 'honky-tonk'], subGenreSlugs: ['country-folk', 'classic-country', 'contemporary-country', 'americana', 'honky-tonk', 'old-time-country', 'alternative-country'] },
      { label: 'Jazz', slugs: ['jazz', 'jazz-blues', 'soul-jazz', 'avant-garde-jazz'], subGenreSlugs: ['jazz-blues', 'soul-jazz', 'avant-garde-jazz'] },
      { label: 'Electronic / Dance', slugs: ['dance/electronic', 'house', 'dj', 'club-dance', 'electro-techno'], subGenreSlugs: ['house', 'dj', 'club-dance', 'electro-techno', 'ambient'] },
      { label: 'Classical', slugs: ['classical', 'classical/vocal', 'ballet'], subGenreSlugs: ['classical/vocal'] },
      { label: 'R&B / Soul', slugs: ['r&b', 'soul', 'funk'], subGenreSlugs: ['funk'] },
      { label: 'Folk / Americana', slugs: ['folk', 'americana', 'singer-songwriter', 'indie-folk', 'country-folk', 'alternative-folk'], subGenreSlugs: ['singer-songwriter', 'indie-folk', 'alternative-folk', 'folk-rock'] },
      { label: 'Metal', slugs: ['metal', 'heavy-metal', 'hard-rock', 'death-metal/black-metal', 'nu-metal'], subGenreSlugs: ['heavy-metal', 'hard-rock', 'death-metal/black-metal', 'nu-metal', 'sludge-metal'] },
      { label: 'Blues', slugs: ['blues', 'jazz-blues'], subGenreSlugs: ['jazz-blues'] },
      { label: 'Latin', slugs: ['latin'], subGenreSlugs: [] },
    ],
  },
  {
    label: 'Sports',
    emoji: '🏟',
    genres: [
      { label: 'Football', slugs: ['football'] },
      { label: 'Basketball', slugs: ['basketball', 'nba'] },
      { label: 'Baseball', slugs: ['baseball', 'mlb'] },
      { label: 'Soccer', slugs: ['soccer', 'mls'] },
      { label: 'Hockey', slugs: ['hockey', 'nhl'] },
      { label: 'Motorsports', slugs: ['motorsports/racing'] },
      { label: 'Other Sports', slugs: ['sports', 'minor-league'] },
    ],
  },
  {
    label: 'Arts & Theatre',
    emoji: '🎭',
    genres: [
      { label: 'Theatre', slugs: ['theatre', 'musical', 'miscellaneous-theatre'] },
      { label: 'Ballet & Dance', slugs: ['ballet', 'dance'] },
      { label: 'Arts & Exhibitions', slugs: ['arts'] },
      { label: 'Comedy', slugs: ['comedy'] },
    ],
  },
  {
    label: 'Food & Drink',
    emoji: '🍔',
    genres: [
      { label: 'Food Festivals', slugs: ['food', 'food-&-drink', 'fairs-&-festivals'] },
      { label: 'Restaurants & Markets', slugs: ['restaurant', 'market'] },
    ],
  },
  {
    label: 'Technology',
    emoji: '💻',
    genres: [
      { label: 'Tech Conferences', slugs: ['technology', 'conference', 'expo'] },
      { label: 'Meetups', slugs: ['meetup'] },
    ],
  },
  {
    label: 'Wellness',
    emoji: '🧘',
    genres: [
      { label: 'Fitness', slugs: ['fitness', 'wellness'] },
      { label: 'Outdoor', slugs: ['outdoor'] },
    ],
  },
  {
    label: 'Family',
    emoji: '👨‍👩‍👧',
    genres: [
      { label: 'Kids Events', slugs: ['kids', 'family'] },
    ],
  },
  {
    label: 'Nightlife',
    emoji: '🌙',
    genres: [
      { label: 'Clubs & DJ', slugs: ['nightlife', 'dj', 'club-dance'] },
    ],
  },
]

// All slugs that belong to a given top-level type
export function slugsForType(type: EventTypeEntry): string[] {
  return type.genres.flatMap((g) => g.slugs)
}
```

- [ ] **Step 2: Create `frontend/src/components/settings/GeneralTab.tsx`**

```typescript
import { useState } from 'react'
import { api } from '../../api/client'
import { useAuth } from '../../context/AuthContext'

interface GeneralTabProps {
  maxDistance: number
  onMaxDistanceChange: (v: number) => void
  onSave: () => Promise<void>
  saving: boolean
  message: string
}

export default function GeneralTab({ maxDistance, onMaxDistanceChange, onSave, saving, message }: GeneralTabProps) {
  const { user } = useAuth()
  const [cityInput, setCityInput] = useState(user?.home_city ?? '')
  const [cityMsg, setCityMsg] = useState('')

  const handleCitySave = async () => {
    if (!cityInput.trim()) return
    try {
      await api.updateHomeCity(cityInput.trim())
      setCityMsg('City updated!')
      setTimeout(() => setCityMsg(''), 3000)
    } catch {
      setCityMsg('Failed to update city')
    }
  }

  return (
    <div className="space-y-6">
      {/* Home City */}
      <div className="bg-white rounded-xl border p-6 space-y-4">
        <h2 className="text-lg font-semibold">Home City</h2>
        <p className="text-sm text-gray-500">Your default city for event discovery.</p>
        <div className="flex gap-2">
          <input
            type="text"
            value={cityInput}
            onChange={(e) => setCityInput(e.target.value)}
            placeholder="e.g. Nashville"
            className="border rounded px-3 py-2 text-sm flex-1"
          />
          <button
            onClick={handleCitySave}
            className="px-4 py-2 bg-brand-600 text-white text-sm rounded hover:bg-brand-700"
          >
            Update
          </button>
        </div>
        {cityMsg && (
          <p className={`text-sm ${cityMsg.includes('Failed') ? 'text-red-500' : 'text-green-600'}`}>{cityMsg}</p>
        )}
      </div>

      {/* Distance */}
      <div className="bg-white rounded-xl border p-6 space-y-4">
        <h2 className="text-lg font-semibold">Distance</h2>
        <p className="text-sm text-gray-500">How far are you willing to travel for an event?</p>
        <div className="flex items-center gap-4">
          <input
            type="range"
            min="5"
            max="200"
            step="5"
            value={maxDistance}
            onChange={(e) => onMaxDistanceChange(parseInt(e.target.value))}
            className="flex-1 accent-brand-600"
          />
          <span className="w-24 text-sm font-medium text-gray-700 text-right">
            {maxDistance} miles
          </span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button
          onClick={onSave}
          disabled={saving}
          className="px-6 py-3 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 font-medium"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        {message && (
          <span className={`text-sm ${message.includes('Failed') ? 'text-red-500' : 'text-green-600'}`}>
            {message}
          </span>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create `frontend/src/components/settings/NotificationsTab.tsx`**

Extract the full notifications section from the current `Settings.tsx` (lines ~280–473) into this component:

```typescript
import { api, type NotificationChannel, type NotificationPrefs } from '../../api/client'

interface NotificationsTabProps {
  channels: NotificationChannel[]
  setChannels: React.Dispatch<React.SetStateAction<NotificationChannel[]>>
  notifPrefs: NotificationPrefs
  setNotifPrefs: React.Dispatch<React.SetStateAction<NotificationPrefs>>
  onSave: () => Promise<void>
  saving: boolean
  message: string
}

export default function NotificationsTab({
  channels, setChannels, notifPrefs, setNotifPrefs, onSave, saving, message,
}: NotificationsTabProps) {
  const [newChannelType, setNewChannelType] = React.useState('email')
  const [newChannelAddress, setNewChannelAddress] = React.useState('')

  return (
    <div className="space-y-6">
      {/* Notification Channels */}
      <div className="bg-white rounded-xl border p-6 space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Notification Channels</h2>
          <p className="text-sm text-gray-500 mt-1">Add channels to receive event notifications.</p>
        </div>
        {channels.length > 0 && (
          <div className="space-y-2">
            {channels.map((ch) => (
              <div key={ch.id} className={`flex items-center gap-3 p-3 rounded-lg border ${ch.is_active ? 'bg-white' : 'bg-gray-50 opacity-60'}`}>
                <span className="text-lg">{ch.channel_type === 'email' ? '✉' : ch.channel_type === 'sms' ? '📱' : ch.channel_type === 'slack' ? '#' : '🔔'}</span>
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-gray-900 capitalize">{ch.channel_type}</span>
                  <p className="text-xs text-gray-500 truncate">{ch.channel_address}</p>
                </div>
                <button
                  onClick={async () => {
                    const result = await api.toggleNotificationChannel(ch.id)
                    setChannels((prev) => prev.map((c) => (c.id === ch.id ? { ...c, is_active: result.is_active } : c)))
                  }}
                  className={`px-3 py-1 text-xs rounded border ${ch.is_active ? 'bg-green-50 text-green-700 border-green-200' : 'bg-gray-100 text-gray-500 border-gray-200'}`}
                >
                  {ch.is_active ? 'Active' : 'Paused'}
                </button>
                <button
                  onClick={async () => { await api.removeNotificationChannel(ch.id); setChannels((prev) => prev.filter((c) => c.id !== ch.id)) }}
                  className="text-red-400 hover:text-red-600 text-sm"
                >Remove</button>
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-2 items-end">
          <div>
            <label className="text-xs text-gray-500 block mb-1">Type</label>
            <select value={newChannelType} onChange={(e) => setNewChannelType(e.target.value)} className="border rounded px-3 py-2 text-sm">
              <option value="email">Email</option>
              <option value="sms">SMS</option>
              <option value="slack">Slack Webhook</option>
              <option value="push">Push Token</option>
            </select>
          </div>
          <div className="flex-1">
            <label className="text-xs text-gray-500 block mb-1">
              {newChannelType === 'email' ? 'Email address' : newChannelType === 'sms' ? 'Phone number' : newChannelType === 'slack' ? 'Webhook URL' : 'FCM Token'}
            </label>
            <input type="text" value={newChannelAddress} onChange={(e) => setNewChannelAddress(e.target.value)}
              placeholder={newChannelType === 'email' ? 'you@example.com' : newChannelType === 'sms' ? '+15551234567' : newChannelType === 'slack' ? 'https://hooks.slack.com/...' : 'FCM device token'}
              className="border rounded px-3 py-2 text-sm w-full" />
          </div>
          <button
            onClick={async () => {
              if (!newChannelAddress.trim()) return
              const ch = await api.addNotificationChannel(newChannelType, newChannelAddress.trim())
              setChannels((prev) => [ch, ...prev])
              setNewChannelAddress('')
            }}
            className="px-4 py-2 bg-brand-600 text-white text-sm rounded hover:bg-brand-700"
          >Add</button>
        </div>
      </div>

      {/* Notification Types */}
      <div className="bg-white rounded-xl border p-6 space-y-4">
        <h2 className="text-lg font-semibold">Notification Preferences</h2>
        <div className="space-y-3">
          {[
            { type: 'ticket_alert', label: 'Ticket Alerts', desc: 'When matching events go on sale' },
            { type: 'tonight', label: 'Tonight', desc: 'Events happening today in your area' },
            { type: 'new_match', label: 'New Matches', desc: "High-score events we think you'll love" },
            { type: 'weekly_digest', label: 'Weekly Digest', desc: 'Top upcoming events each week' },
          ].map(({ type, label, desc }) => (
            <label key={type} className="flex items-center gap-3 p-2 rounded hover:bg-gray-50 cursor-pointer">
              <input type="checkbox" checked={notifPrefs.enabled_types.includes(type)}
                onChange={(e) => setNotifPrefs((prev) => ({ ...prev, enabled_types: e.target.checked ? [...prev.enabled_types, type] : prev.enabled_types.filter((t) => t !== type) }))}
                className="accent-brand-600 w-4 h-4" />
              <div>
                <span className="text-sm font-medium text-gray-900">{label}</span>
                <p className="text-xs text-gray-400">{desc}</p>
              </div>
            </label>
          ))}
        </div>
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Daily Limit</h3>
          <div className="flex items-center gap-4">
            <input type="range" min="1" max="20" value={notifPrefs.max_per_day}
              onChange={(e) => setNotifPrefs((prev) => ({ ...prev, max_per_day: parseInt(e.target.value) }))}
              className="flex-1 accent-brand-600" />
            <span className="w-32 text-sm text-gray-700 text-right">{notifPrefs.max_per_day} per day</span>
          </div>
        </div>
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Quiet Hours</h3>
          <div className="flex items-center gap-3">
            <input type="time" value={notifPrefs.quiet_hours_start ?? '22:00'}
              onChange={(e) => setNotifPrefs((prev) => ({ ...prev, quiet_hours_start: e.target.value }))}
              className="border rounded px-3 py-2 text-sm" />
            <span className="text-sm text-gray-500">to</span>
            <input type="time" value={notifPrefs.quiet_hours_end ?? '08:00'}
              onChange={(e) => setNotifPrefs((prev) => ({ ...prev, quiet_hours_end: e.target.value }))}
              className="border rounded px-3 py-2 text-sm" />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button onClick={onSave} disabled={saving} className="px-6 py-3 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 font-medium">
          {saving ? 'Saving…' : 'Save'}
        </button>
        {message && <span className={`text-sm ${message.includes('Failed') ? 'text-red-500' : 'text-green-600'}`}>{message}</span>}
      </div>
    </div>
  )
}

import React from 'react'
```

- [ ] **Step 4: Create `frontend/src/components/settings/SourcesTab.tsx`**

Extract the sources section from `Settings.tsx`:

```typescript
import { api, type EventSourceInfo, type UserSourcePref } from '../../api/client'

interface SourcesTabProps {
  sources: EventSourceInfo[]
  sourcePrefs: Map<number, string>
  onUpdate: (sourceId: number, preference: string) => Promise<void>
}

function sourceTypeLabel(type: string): string {
  const labels: Record<string, string> = { api: 'API', scraper: 'Local Site', ical: 'Calendar Feed', manual: 'Manual' }
  return labels[type] ?? type
}

function SourceRow({ source, preference, onUpdate, typeLabel }: { source: EventSourceInfo; preference: string; onUpdate: (id: number, pref: string) => void; typeLabel: string }) {
  const prefButtons = [
    { value: 'liked', label: 'Like', activeClass: 'bg-green-100 text-green-700 border-green-300' },
    { value: 'neutral', label: 'Neutral', activeClass: 'bg-gray-100 text-gray-700 border-gray-300' },
    { value: 'disliked', label: 'Dislike', activeClass: 'bg-orange-100 text-orange-700 border-orange-300' },
    { value: 'disabled', label: 'Off', activeClass: 'bg-red-100 text-red-600 border-red-300' },
  ]
  return (
    <div className={`flex items-center gap-3 p-3 rounded-lg border ${preference === 'disabled' ? 'opacity-50 bg-gray-50' : 'bg-white'}`}>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm text-gray-900">{source.name}</span>
          <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">{typeLabel}</span>
          {source.is_local && <span className="text-xs px-1.5 py-0.5 bg-brand-50 text-brand-700 rounded">Local</span>}
        </div>
        {source.description && <p className="text-xs text-gray-400 mt-0.5 truncate">{source.description}</p>}
      </div>
      <div className="flex gap-1">
        {prefButtons.map((btn) => (
          <button key={btn.value} onClick={() => onUpdate(source.id, btn.value)}
            className={`px-2 py-1 text-xs rounded border transition-colors ${preference === btn.value ? btn.activeClass : 'bg-white text-gray-400 border-gray-200 hover:border-gray-300'}`}>
            {btn.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function SourcesTab({ sources, sourcePrefs, onUpdate }: SourcesTabProps) {
  const localSources = sources.filter((s) => s.is_local)
  const nationalSources = sources.filter((s) => !s.is_local)

  return (
    <div className="bg-white rounded-xl border p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Event Sources</h2>
        <p className="text-sm text-gray-500 mt-1">Choose which sources you want to see events from.</p>
      </div>
      {localSources.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-brand-600 uppercase tracking-wide">Local Sources</h3>
          {localSources.map((s) => <SourceRow key={s.id} source={s} preference={sourcePrefs.get(s.id) ?? 'neutral'} onUpdate={onUpdate} typeLabel={sourceTypeLabel(s.source_type)} />)}
        </div>
      )}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">National Sources</h3>
        {nationalSources.map((s) => <SourceRow key={s.id} source={s} preference={sourcePrefs.get(s.id) ?? 'neutral'} onUpdate={onUpdate} typeLabel={sourceTypeLabel(s.source_type)} />)}
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/settings/
git commit -m "feat: add settings tab components and genre map"
```

---

## Task 10: PreferencesTab — 3-Step Wizard

**Files:**
- Create: `frontend/src/components/settings/PreferencesTab.tsx`

- [ ] **Step 1: Create `frontend/src/components/settings/PreferencesTab.tsx`**

```typescript
import { useState } from 'react'
import { api, type CategoryPreference, type ArtistPreference, type MusicBrainzArtist } from '../../api/client'
import { EVENT_TYPE_MAP, type EventTypeEntry, type GenreEntry } from './genreMap'

type WizardStep = 'types' | 'genres' | 'deepdive' | 'done'

const WEIGHT_LABELS: Record<string, string> = {
  '-1': 'Not interested',
  '0.5': 'Low',
  '1': 'Normal',
  '2': 'Interested',
  '3': 'Love it',
}

function weightLabel(w: number): string {
  if (w <= -0.5) return 'Not interested'
  if (w <= 0.5) return 'Low'
  if (w <= 1.5) return 'Normal'
  if (w <= 2.5) return 'Interested'
  return 'Love it'
}

function weightColor(w: number): string {
  if (w <= -0.5) return 'text-red-500'
  if (w <= 0.5) return 'text-gray-400'
  if (w <= 1.5) return 'text-gray-600'
  if (w <= 2.5) return 'text-blue-600'
  return 'text-green-600'
}

interface PreferencesTabProps {
  initialPreferences: CategoryPreference[]
  onSaved: () => void
}

export default function PreferencesTab({ initialPreferences, onSaved }: PreferencesTabProps) {
  const [step, setStep] = useState<WizardStep>('types')
  const [selectedTypes, setSelectedTypes] = useState<string[]>([])
  const [typeIndex, setTypeIndex] = useState(0)
  const [weights, setWeights] = useState<Record<string, number>>(() => {
    const map: Record<string, number> = {}
    initialPreferences.forEach((p) => { map[p.category_slug] = p.weight })
    return map
  })
  const [deepdiveGenres, setDeepdiveGenres] = useState<GenreEntry[]>([])
  const [deepdiveIndex, setDeepdiveIndex] = useState(0)
  const [selectedSubGenres, setSelectedSubGenres] = useState<Record<string, string[]>>({})
  const [artistSearch, setArtistSearch] = useState('')
  const [artistResults, setArtistResults] = useState<MusicBrainzArtist[]>([])
  const [addedArtists, setAddedArtists] = useState<Record<string, ArtistPreference[]>>({})
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  const getWeight = (slug: string) => weights[slug] ?? 1.0
  const setWeight = (slug: string, w: number) => setWeights((prev) => ({ ...prev, [slug]: w }))

  // Step 1 handlers
  const toggleType = (label: string) => {
    setSelectedTypes((prev) =>
      prev.includes(label) ? prev.filter((t) => t !== label) : [...prev, label]
    )
  }

  const handleTypesNext = () => {
    if (selectedTypes.length === 0) return
    setTypeIndex(0)
    setStep('genres')
  }

  // Step 2 handlers
  const currentType = EVENT_TYPE_MAP.find((t) => t.label === selectedTypes[typeIndex])

  const handleGenresNext = async () => {
    if (typeIndex < selectedTypes.length - 1) {
      setTypeIndex((i) => i + 1)
    } else {
      // Save all genre weights before moving to deep dive
      setSaving(true)
      try {
        const updates = Object.entries(weights).map(([category_slug, weight]) => ({ category_slug, weight }))
        await api.updatePreferences(updates)
      } finally {
        setSaving(false)
      }
      // Build deep-dive list: genres from selected types where weight > 1.0 and subGenreSlugs exist
      const genres: GenreEntry[] = []
      EVENT_TYPE_MAP.filter((t) => selectedTypes.includes(t.label)).forEach((t) => {
        t.genres.forEach((g) => {
          const maxWeight = Math.max(...g.slugs.map((s) => getWeight(s)))
          if (maxWeight > 1.0 && g.subGenreSlugs && g.subGenreSlugs.length > 0) {
            genres.push(g)
          }
        })
      })
      setDeepdiveGenres(genres)
      setDeepdiveIndex(0)
      setStep(genres.length > 0 ? 'deepdive' : 'done')
    }
  }

  // Step 3 handlers
  const currentDeepGenre = deepdiveGenres[deepdiveIndex]

  const toggleSubGenre = (genreLabel: string, slug: string) => {
    setSelectedSubGenres((prev) => {
      const current = prev[genreLabel] ?? []
      return {
        ...prev,
        [genreLabel]: current.includes(slug) ? current.filter((s) => s !== slug) : [...current, slug],
      }
    })
  }

  const handleArtistSearch = async (query: string) => {
    setArtistSearch(query)
    if (query.length < 2) { setArtistResults([]); return }
    const results = await api.searchMusicBrainzArtists(query)
    setArtistResults(results)
  }

  const handleAddArtist = async (artist: MusicBrainzArtist, genreLabel: string) => {
    const current = addedArtists[genreLabel] ?? []
    if (current.length >= 3) return
    try {
      const saved = await api.addArtist({
        artist_name: artist.name,
        musicbrainz_id: artist.id,
        mb_genres: artist.tags?.slice(0, 5).map((t) => t.name) ?? [],
        genre_context: genreLabel.toLowerCase(),
      })
      setAddedArtists((prev) => ({ ...prev, [genreLabel]: [...(prev[genreLabel] ?? []), saved] }))
      setArtistSearch('')
      setArtistResults([])
    } catch (err: any) {
      setMessage(err.message || 'Failed to add artist')
    }
  }

  const handleDeepDiveSave = async () => {
    if (!currentDeepGenre) return
    // Save sub-genre weights (boost selected sub-genres to "Interested" if not already higher)
    const subSlugs = selectedSubGenres[currentDeepGenre.label] ?? []
    if (subSlugs.length > 0) {
      const updates = subSlugs.map((slug) => ({
        category_slug: slug,
        weight: Math.max(getWeight(slug), 2.0),
      }))
      await api.updatePreferences(updates)
    }
    handleDeepDiveNext()
  }

  const handleDeepDiveNext = () => {
    if (deepdiveIndex < deepdiveGenres.length - 1) {
      setDeepdiveIndex((i) => i + 1)
      setArtistSearch('')
      setArtistResults([])
    } else {
      setStep('done')
    }
  }

  // Step indicators
  const stepNum = step === 'types' ? 1 : step === 'genres' ? 2 : step === 'deepdive' ? 3 : 3
  const stepLabels = ['Pick Types', 'Rate Genres', 'Go Deeper']

  if (step === 'done') {
    return (
      <div className="text-center py-16 space-y-4">
        <div className="text-5xl">🎉</div>
        <h2 className="text-xl font-semibold text-gray-900">Preferences saved!</h2>
        <p className="text-gray-500 text-sm">We'll use these to find events you'll love.</p>
        <button onClick={onSaved} className="px-6 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm">
          Done
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {stepLabels.map((label, i) => (
          <div key={label} className="flex items-center gap-2">
            <div className={`w-6 h-6 rounded-full text-xs flex items-center justify-center font-medium ${i + 1 <= stepNum ? 'bg-brand-600 text-white' : 'bg-gray-200 text-gray-500'}`}>
              {i + 1}
            </div>
            <span className={`text-xs ${i + 1 === stepNum ? 'text-brand-600 font-medium' : 'text-gray-400'}`}>{label}</span>
            {i < stepLabels.length - 1 && <div className={`flex-1 h-0.5 w-8 ${i + 1 < stepNum ? 'bg-brand-600' : 'bg-gray-200'}`} />}
          </div>
        ))}
      </div>

      {/* Step 1: Pick types */}
      {step === 'types' && (
        <div className="bg-white rounded-xl border p-6 space-y-4">
          <h2 className="text-lg font-semibold">What types of events do you enjoy?</h2>
          <p className="text-sm text-gray-500">Select all that apply. You can always change this later.</p>
          <div className="flex flex-wrap gap-3">
            {EVENT_TYPE_MAP.map((type) => (
              <button
                key={type.label}
                onClick={() => toggleType(type.label)}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-colors border ${selectedTypes.includes(type.label) ? 'bg-brand-600 text-white border-brand-600' : 'bg-white text-gray-700 border-gray-200 hover:border-brand-300'}`}
              >
                {type.emoji} {type.label}
              </button>
            ))}
          </div>
          <div className="flex justify-end pt-2">
            <button
              onClick={handleTypesNext}
              disabled={selectedTypes.length === 0}
              className="px-6 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-40 text-sm font-medium"
            >
              Next →
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Rate genres */}
      {step === 'genres' && currentType && (
        <div className="bg-white rounded-xl border p-6 space-y-4">
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
              {currentType.emoji} {currentType.label} · {typeIndex + 1} of {selectedTypes.length}
            </p>
            <h2 className="text-lg font-semibold">How much do you like each genre?</h2>
            <p className="text-sm text-gray-500">Slide to set your interest level.</p>
          </div>
          <div className="space-y-5">
            {currentType.genres.map((genre) => {
              const representativeSlug = genre.slugs[0]
              const w = getWeight(representativeSlug)
              return (
                <div key={genre.label} className="space-y-1">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium text-gray-700">{genre.label}</span>
                    <span className={`text-xs ${weightColor(w)}`}>{weightLabel(w)}</span>
                  </div>
                  <input
                    type="range"
                    min="-1"
                    max="3"
                    step="0.5"
                    value={w}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value)
                      genre.slugs.forEach((slug) => setWeight(slug, val))
                    }}
                    className="w-full accent-brand-600"
                  />
                </div>
              )
            })}
          </div>
          <div className="flex justify-between pt-2">
            <button onClick={() => { if (typeIndex > 0) setTypeIndex((i) => i - 1); else setStep('types') }}
              className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
              ← Back
            </button>
            <button onClick={handleGenresNext} disabled={saving}
              className="px-6 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-40 text-sm font-medium">
              {saving ? 'Saving…' : typeIndex < selectedTypes.length - 1 ? 'Next →' : 'Continue →'}
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Deep dive */}
      {step === 'deepdive' && currentDeepGenre && (
        <div className="bg-white rounded-xl border p-6 space-y-5">
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
              Optional · {deepdiveIndex + 1} of {deepdiveGenres.length}
            </p>
            <h2 className="text-lg font-semibold">Go deeper on {currentDeepGenre.label}?</h2>
            <p className="text-sm text-gray-500">Select sub-genres and add favorite artists (max 3).</p>
          </div>

          {/* Sub-genres */}
          {currentDeepGenre.subGenreSlugs && currentDeepGenre.subGenreSlugs.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-gray-500 uppercase">Sub-genres</p>
              <div className="flex flex-wrap gap-2">
                {currentDeepGenre.subGenreSlugs.map((slug) => {
                  const selected = (selectedSubGenres[currentDeepGenre.label] ?? []).includes(slug)
                  return (
                    <button
                      key={slug}
                      onClick={() => toggleSubGenre(currentDeepGenre.label, slug)}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors border ${selected ? 'bg-brand-600 text-white border-brand-600' : 'bg-white text-gray-600 border-gray-200 hover:border-brand-300'}`}
                    >
                      {slug.replace(/-/g, ' ').replace(/\//g, ' / ')}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Artist search */}
          <div className="space-y-2">
            <p className="text-xs font-medium text-gray-500 uppercase">
              Favorite Artists (optional · {(addedArtists[currentDeepGenre.label] ?? []).length}/3)
            </p>
            {(addedArtists[currentDeepGenre.label] ?? []).map((a) => (
              <div key={a.artist_name} className="flex items-center gap-2 bg-brand-50 border border-brand-200 rounded-full px-3 py-1 text-sm text-brand-700 w-fit">
                <span>{a.artist_name}</span>
                {a.mb_genres && a.mb_genres.length > 0 && (
                  <span className="text-xs text-brand-400">· {a.mb_genres.slice(0, 2).join(', ')}</span>
                )}
              </div>
            ))}
            {(addedArtists[currentDeepGenre.label] ?? []).length < 3 && (
              <div className="relative">
                <input
                  type="text"
                  value={artistSearch}
                  onChange={(e) => handleArtistSearch(e.target.value)}
                  placeholder="Search for an artist…"
                  className="border rounded-lg px-3 py-2 text-sm w-full"
                />
                {artistResults.length > 0 && (
                  <div className="absolute top-full left-0 right-0 bg-white border rounded-lg shadow-lg mt-1 z-10 overflow-hidden">
                    {artistResults.map((a) => (
                      <button
                        key={a.id}
                        onClick={() => handleAddArtist(a, currentDeepGenre.label)}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center justify-between"
                      >
                        <span>{a.name}</span>
                        {a.tags && a.tags.length > 0 && (
                          <span className="text-xs text-gray-400">{a.tags.slice(0, 2).map((t) => t.name).join(', ')}</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {message && <p className="text-sm text-red-500">{message}</p>}

          <div className="flex justify-between pt-2">
            <button onClick={handleDeepDiveNext} className="px-4 py-2 text-sm text-gray-500 border rounded-lg hover:bg-gray-50">
              Skip →
            </button>
            <button onClick={handleDeepDiveSave}
              className="px-6 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm font-medium">
              {deepdiveIndex < deepdiveGenres.length - 1 ? 'Save & Next →' : 'Finish →'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/settings/PreferencesTab.tsx
git commit -m "feat: add 3-step preferences wizard with MusicBrainz artist lookup"
```

---

## Task 11: Rewrite Settings.tsx with Tab Bar

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`

- [ ] **Step 1: Replace `frontend/src/pages/Settings.tsx`**

```typescript
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type CategoryPreference, type EventSourceInfo, type NotificationChannel, type NotificationPrefs } from '../api/client'
import { useAuth } from '../context/AuthContext'
import GeneralTab from '../components/settings/GeneralTab'
import PreferencesTab from '../components/settings/PreferencesTab'
import NotificationsTab from '../components/settings/NotificationsTab'
import SourcesTab from '../components/settings/SourcesTab'

type Tab = 'general' | 'preferences' | 'notifications' | 'sources'

const TABS: { id: Tab; label: string }[] = [
  { id: 'general', label: 'General' },
  { id: 'preferences', label: 'Preferences' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'sources', label: 'Sources' },
]

export default function Settings() {
  const { isAuthenticated, user } = useAuth()
  const [activeTab, setActiveTab] = useState<Tab>('general')

  // Shared state
  const [preferences, setPreferences] = useState<CategoryPreference[]>([])
  const [maxDistance, setMaxDistance] = useState(25)
  const [sources, setSources] = useState<EventSourceInfo[]>([])
  const [sourcePrefs, setSourcePrefs] = useState<Map<number, string>>(new Map())
  const [channels, setChannels] = useState<NotificationChannel[]>([])
  const [notifPrefs, setNotifPrefs] = useState<NotificationPrefs>({
    quiet_hours_start: null,
    quiet_hours_end: null,
    max_per_day: 5,
    enabled_types: ['ticket_alert', 'tonight', 'weekly_digest', 'new_match'],
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!isAuthenticated) return
    const load = async () => {
      try {
        const [prefs, srcs, srcPrefs, nChannels, nPrefs] = await Promise.all([
          api.getPreferences(),
          api.getSources(user?.home_city ?? undefined),
          api.getSourcePreferences(),
          api.getNotificationChannels(),
          api.getNotificationPreferences(),
        ])
        setPreferences(prefs.categories)
        setMaxDistance(prefs.max_distance_miles)
        setSources(srcs)
        setChannels(nChannels)
        setNotifPrefs(nPrefs)
        const prefMap = new Map<number, string>()
        srcPrefs.forEach((sp) => prefMap.set(sp.source_id, sp.preference))
        setSourcePrefs(prefMap)
      } catch (err) {
        console.error('Failed to load settings:', err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [isAuthenticated, user?.home_city])

  if (!isAuthenticated) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-500">Sign in to manage your preferences</p>
        <Link to="/login" className="text-brand-600 hover:underline mt-2 inline-block">Sign in</Link>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto animate-pulse space-y-4">
        <div className="h-8 bg-gray-200 rounded w-1/3" />
        {Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-12 bg-gray-200 rounded" />)}
      </div>
    )
  }

  const handleSaveGeneral = async () => {
    setSaving(true)
    setMessage('')
    try {
      await api.updateDistancePreference(maxDistance)
      setMessage('Saved!')
      setTimeout(() => setMessage(''), 3000)
    } catch {
      setMessage('Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleSaveNotifications = async () => {
    setSaving(true)
    setMessage('')
    try {
      await api.updateNotificationPreferences(notifPrefs)
      setMessage('Saved!')
      setTimeout(() => setMessage(''), 3000)
    } catch {
      setMessage('Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleSourcePref = async (sourceId: number, preference: string) => {
    await api.updateSourcePreference(sourceId, preference)
    setSourcePrefs((prev) => {
      const next = new Map(prev)
      if (preference === 'neutral') next.delete(sourceId)
      else next.set(sourceId, preference)
      return next
    })
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500 mt-1">Control your event sources and preferences</p>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-200">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab.id
                ? 'text-brand-600 border-brand-600'
                : 'text-gray-500 border-transparent hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'general' && (
        <GeneralTab
          maxDistance={maxDistance}
          onMaxDistanceChange={setMaxDistance}
          onSave={handleSaveGeneral}
          saving={saving}
          message={message}
        />
      )}
      {activeTab === 'preferences' && (
        <PreferencesTab
          initialPreferences={preferences}
          onSaved={() => setActiveTab('general')}
        />
      )}
      {activeTab === 'notifications' && (
        <NotificationsTab
          channels={channels}
          setChannels={setChannels}
          notifPrefs={notifPrefs}
          setNotifPrefs={setNotifPrefs}
          onSave={handleSaveNotifications}
          saving={saving}
          message={message}
        />
      )}
      {activeTab === 'sources' && (
        <SourcesTab
          sources={sources}
          sourcePrefs={sourcePrefs}
          onUpdate={handleSourcePref}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Rebuild frontend container and smoke test**

```bash
docker compose restart api
```

Open http://localhost:5173/settings. Verify:
- Tab bar shows General / Preferences / Notifications / Sources
- General tab shows distance slider and city input
- Preferences tab shows step 1 chip grid
- Notifications and Sources tabs show existing content

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Settings.tsx
git commit -m "feat: settings page tab bar with General, Preferences, Notifications, Sources tabs"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| Delete mock_data.py, seed.py, mock Celery task | Task 1 |
| Dynamic city list from user home_city | Task 2 |
| POST /api/v1/ingest/city with Redis rate limit | Task 3 |
| Trigger ingestion on registration/city update | Task 4 |
| UserArtistPreference model + migration | Task 5 |
| GET/POST/DELETE /me/artists | Task 5 |
| Frontend API methods (ingestCity, artists, MusicBrainz) | Task 6 |
| useCitySeeding hook (check → trigger → poll → resolve) | Task 7 |
| CityLoadingScreen with progress bar + event list | Task 7 |
| Home.tsx uses home city, shows loading screen | Task 8 |
| genreMap.ts static type→genre→slug mapping | Task 9 |
| GeneralTab (distance + city edit) | Task 9 |
| NotificationsTab (extracted) | Task 9 |
| SourcesTab (extracted) | Task 9 |
| PreferencesTab 3-step wizard | Task 10 |
| MusicBrainz artist search in step 3 | Task 10 |
| Settings.tsx tab bar | Task 11 |
| Seed endpoint removed from router | Task 1 |
| PUT /me/city endpoint | Task 4 |
| use_mock_data config field removed | Task 1 |
