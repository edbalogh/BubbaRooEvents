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
