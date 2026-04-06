import pytest
from unittest.mock import MagicMock, patch
from app.services.user_service import _queue_city_ingest_if_needed


def test_queue_city_ingest_fires_when_not_rate_limited():
    with patch("app.services.user_service._redis") as mock_redis, \
         patch("app.services.user_service.ingest_city_now") as mock_task:
        # SET NX returns True = acquired (not rate-limited)
        mock_redis.set.return_value = True
        mock_task.delay = MagicMock()

        _queue_city_ingest_if_needed("Nashville")

        mock_redis.set.assert_called_once_with(
            "ingest:city:nashville:last_queued", "1", ex=600, nx=True
        )
        mock_task.delay.assert_called_once_with("Nashville")


def test_queue_city_ingest_skips_when_rate_limited():
    with patch("app.services.user_service._redis") as mock_redis, \
         patch("app.services.user_service.ingest_city_now") as mock_task:
        # SET NX returns None = not acquired (rate-limited)
        mock_redis.set.return_value = None
        mock_task.delay = MagicMock()

        _queue_city_ingest_if_needed("Nashville")

        mock_task.delay.assert_not_called()
