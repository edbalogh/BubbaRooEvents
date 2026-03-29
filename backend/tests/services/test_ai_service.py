import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_explain_recommendation_returns_provider_text():
    mock_provider = AsyncMock()
    mock_provider.complete.return_value = "You'll love this jazz event!"

    with patch("app.services.ai_service._recommend_provider", mock_provider):
        from app.services.ai_service import explain_recommendation
        result = await explain_recommendation(
            event_title="Jazz Night",
            event_description="A smooth evening of jazz",
            event_categories=["music", "jazz"],
            event_venue="Blue Note",
            event_city="Austin",
            event_date="2026-04-01",
            event_price_min=20.0,
            score=0.85,
            score_breakdown={"category_affinity": 0.9, "embedding_similarity": 0.7, "popularity": 0.5},
            user_top_categories=["music", "concerts"],
        )

    assert result == "You'll love this jazz event!"
    mock_provider.complete.assert_called_once()


@pytest.mark.asyncio
async def test_explain_recommendation_propagates_error():
    mock_provider = AsyncMock()
    mock_provider.complete.side_effect = RuntimeError("Ollama model not found: qwen3.5:9b")

    with patch("app.services.ai_service._recommend_provider", mock_provider):
        from app.services.ai_service import explain_recommendation
        with pytest.raises(RuntimeError, match="Ollama model not found"):
            await explain_recommendation(
                event_title="Jazz Night",
                event_description=None,
                event_categories=[],
                event_venue=None,
                event_city=None,
                event_date=None,
                event_price_min=None,
                score=0.5,
                score_breakdown={},
                user_top_categories=[],
            )


@pytest.mark.asyncio
async def test_plan_trip_returns_provider_text():
    mock_provider = AsyncMock()
    mock_provider.complete.return_value = "Day 1: Start with the jazz festival..."

    with patch("app.services.ai_service._trip_provider", mock_provider):
        from app.services.ai_service import plan_trip
        result = await plan_trip(
            destination_city="Austin",
            travel_dates="April 1-3",
            interests=["music", "food"],
            events_context=[{"title": "Jazz Fest", "date": "2026-04-01", "venue": "Stubb's", "price_min": 30}],
        )

    assert result == "Day 1: Start with the jazz festival..."
    mock_provider.complete.assert_called_once()


@pytest.mark.asyncio
async def test_plan_trip_propagates_error():
    mock_provider = AsyncMock()
    mock_provider.complete.side_effect = RuntimeError("Ollama error 500: internal error")

    with patch("app.services.ai_service._trip_provider", mock_provider):
        from app.services.ai_service import plan_trip
        with pytest.raises(RuntimeError, match="Ollama error 500"):
            await plan_trip(
                destination_city="Austin",
                travel_dates="April 1-3",
                interests=[],
                events_context=[],
            )
