import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


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


def _make_session_mock():
    """Return an async context manager mock for _session_factory()."""
    mock_db = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx, mock_db


@pytest.mark.asyncio
async def test_ingest_city_now_rate_limited():
    """_run_ingest_city_now returns 0 immediately when rate key exists in Redis."""
    mock_redis = MagicMock()
    mock_redis.get.return_value = "1"  # key exists → rate-limited

    with patch("worker.tasks.ingestion._redis", mock_redis), \
         patch("worker.tasks.ingestion._session_factory") as mock_factory:
        from worker.tasks.ingestion import _run_ingest_city_now
        result = await _run_ingest_city_now("Austin")

    mock_redis.get.assert_called_once_with("ingest:city:Austin:last_queued")
    mock_redis.setex.assert_not_called()
    mock_factory.assert_not_called()
    assert result == 0


@pytest.mark.asyncio
async def test_ingest_city_now_sets_rate_key_and_calls_adapters():
    """_run_ingest_city_now sets the rate key and opens a separate session per adapter."""
    mock_redis = MagicMock()
    mock_redis.get.return_value = None  # key absent → not rate-limited

    # Each call to _session_factory() should return a fresh async context manager.
    mock_db = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("worker.tasks.ingestion._redis", mock_redis), \
         patch("worker.tasks.ingestion._session_factory", return_value=mock_ctx) as mock_factory, \
         patch("worker.tasks.ingestion.upsert_events", new=AsyncMock(return_value=3)), \
         patch("worker.tasks.ingestion.BandsintownAdapter") as mock_bit, \
         patch("worker.tasks.ingestion.EventbriteAdapter") as mock_eb, \
         patch("worker.tasks.ingestion.MeetupAdapter") as mock_mu, \
         patch("worker.tasks.ingestion.TicketmasterAdapter"), \
         patch("worker.tasks.ingestion.SeatGeekAdapter"), \
         patch("worker.tasks.ingestion.settings") as mock_settings:
        # Disable key-gated adapters so only the 3 always-on ones run.
        mock_settings.ticketmaster_api_key = None
        mock_settings.seatgeek_client_id = None

        for adapter_cls in (mock_bit, mock_eb, mock_mu):
            adapter_cls.return_value.fetch_events = AsyncMock(return_value=[])

        from worker.tasks.ingestion import _run_ingest_city_now
        result = await _run_ingest_city_now("Denver")

    rate_key = "ingest:city:Denver:last_queued"
    mock_redis.get.assert_called_once_with(rate_key)
    mock_redis.setex.assert_called_once_with(rate_key, 600, "1")

    # _session_factory should have been called once per always-on adapter (3 times).
    assert mock_factory.call_count == 3, (
        f"Expected 3 session factory calls (one per adapter), got {mock_factory.call_count}"
    )
