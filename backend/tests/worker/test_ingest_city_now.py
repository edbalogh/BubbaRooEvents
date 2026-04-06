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
async def test_ingest_city_now_calls_all_adapters():
    """_run_ingest_city_now opens a separate session per adapter and returns total events."""
    # Each call to _session_factory() should return a fresh async context manager.
    mock_db = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("worker.tasks.ingestion._session_factory", return_value=mock_ctx) as mock_factory, \
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

    # _session_factory should have been called once per always-on adapter (3 times).
    assert mock_factory.call_count == 3, (
        f"Expected 3 session factory calls (one per adapter), got {mock_factory.call_count}"
    )
    assert result == 9
