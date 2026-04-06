import uuid
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.dependencies import get_current_user
from app.models.user import User


def make_fake_user():
    return User(
        id=uuid.uuid4(),
        email="test@test.com",
        password_hash="x",
        display_name="Test",
        home_city="Nashville",
    )


@pytest.fixture(autouse=False)
def auth_override():
    """Override get_current_user dependency to return a fake user."""
    fake_user = make_fake_user()

    async def _fake_user():
        return fake_user

    app.dependency_overrides[get_current_user] = _fake_user
    yield {"Authorization": "Bearer faketoken"}
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_ingest_city_queues_task(auth_override):
    with patch("app.api.v1.ingest.ingest_city_now") as mock_task, \
         patch("app.api.v1.ingest._redis") as mock_redis:
        mock_redis.get.return_value = None  # not rate-limited
        mock_task.delay = MagicMock()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/ingest/city",
                json={"city": "Nashville"},
                headers=auth_override,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["city"] == "Nashville"
    mock_task.delay.assert_called_once_with("Nashville")


@pytest.mark.asyncio
async def test_ingest_city_rate_limited(auth_override):
    with patch("app.api.v1.ingest.ingest_city_now") as mock_task, \
         patch("app.api.v1.ingest._redis") as mock_redis:
        mock_redis.get.return_value = "1"  # already queued recently

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/ingest/city",
                json={"city": "Nashville"},
                headers=auth_override,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "already_queued"
    mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_city_requires_auth():
    # HTTPBearer returns 403 when no Authorization header is provided
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/ingest/city", json={"city": "Nashville"})
    assert resp.status_code == 403
