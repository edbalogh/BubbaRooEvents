import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.user import User
from app.core.dependencies import get_current_user


@pytest.fixture
def fake_user():
    return User(
        id=uuid.uuid4(),
        email="test@test.com",
        password_hash="x",
        display_name="Test",
        home_city="Austin",
    )


@pytest.fixture(autouse=False)
def auth_override(fake_user):
    """Override get_current_user dependency for tests that need auth."""
    async def _fake_user():
        return fake_user
    app.dependency_overrides[get_current_user] = _fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def make_db_with_results(rows):
    """Build a mock async DB session that returns `rows` from execute().scalars().all()."""
    mock_db = AsyncMock()

    # result.scalars() and result.scalars().all() are sync calls on the result object
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = rows
    mock_result.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.delete = AsyncMock()

    return mock_db


def make_mock_db_override(mock_db):
    """Return an async generator dependency override for get_db."""
    async def _get_db():
        yield mock_db
    return _get_db


@pytest.mark.asyncio
async def test_add_artist(auth_override, fake_user):
    from app.core.database import get_db

    mock_db = make_db_with_results([])  # no existing artists

    # refresh sets id and weight so serialization works (mock DB doesn't apply column defaults)
    async def fake_refresh(obj):
        obj.id = 1
        if obj.weight is None:
            obj.weight = 2.0

    mock_db.refresh = AsyncMock(side_effect=fake_refresh)

    app.dependency_overrides[get_db] = make_mock_db_override(mock_db)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/me/artists",
                json={
                    "artist_name": "Radiohead",
                    "musicbrainz_id": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
                    "mb_genres": ["rock", "alternative"],
                    "genre_context": "rock",
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 201
    data = resp.json()
    assert data["artist_name"] == "Radiohead"
    assert data["genre_context"] == "rock"


@pytest.mark.asyncio
async def test_add_artist_max_3_per_genre(auth_override, fake_user):
    """Adding a 4th artist for the same genre_context returns 400."""
    from app.models.user import UserArtistPreference
    from app.core.database import get_db

    existing = [
        UserArtistPreference(user_id=fake_user.id, artist_name=f"Artist{i}", genre_context="rock", weight=2.0)
        for i in range(3)
    ]

    mock_db = make_db_with_results(existing)

    app.dependency_overrides[get_db] = make_mock_db_override(mock_db)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/me/artists",
                json={"artist_name": "NewArtist", "genre_context": "rock"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 400
    assert "maximum" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_artists_returns_list(auth_override, fake_user):
    from app.models.user import UserArtistPreference
    from app.core.database import get_db

    artist = UserArtistPreference(
        user_id=fake_user.id, artist_name="Radiohead", genre_context="rock", weight=2.0
    )
    artist.id = 1  # pre-set id so Pydantic serialization works
    artist.musicbrainz_id = None
    artist.mb_genres = None

    mock_db = make_db_with_results([artist])

    app.dependency_overrides[get_db] = make_mock_db_override(mock_db)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/me/artists")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["artist_name"] == "Radiohead"
