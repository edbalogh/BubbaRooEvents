import pytest
from unittest.mock import AsyncMock, patch
from app.services.discovery_service import (
    score_source_candidates,
    confirm_source,
    extract_events_from_markdown,
)


@pytest.mark.asyncio
async def test_score_source_candidates_filters_by_threshold():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value='''[
        {"url": "https://nashvillearts.com/events", "score": 0.9, "reason": "local arts calendar"},
        {"url": "https://ticketmaster.com", "score": 0.1, "reason": "national reseller"}
    ]''')

    results = await score_source_candidates(
        mock_llm,
        city="Nashville",
        candidates=[
            {"url": "https://nashvillearts.com/events", "snippet": "Nashville arts events"},
            {"url": "https://ticketmaster.com", "snippet": "Buy tickets"},
        ],
        threshold=0.7,
    )

    assert len(results) == 1
    assert results[0]["url"] == "https://nashvillearts.com/events"
    assert results[0]["score"] == 0.9


@pytest.mark.asyncio
async def test_score_source_candidates_handles_malformed_json():
    mock_llm = AsyncMock()
    # First call returns bad JSON, second returns valid
    mock_llm.complete = AsyncMock(side_effect=[
        "Sorry I can't do that",
        '[{"url": "https://example.com", "score": 0.8, "reason": "ok"}]',
    ])

    results = await score_source_candidates(
        mock_llm,
        city="Nashville",
        candidates=[{"url": "https://example.com", "snippet": "events"}],
        threshold=0.7,
    )
    assert len(results) == 1


@pytest.mark.asyncio
async def test_confirm_source_returns_true_for_event_site():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value='''
        {"is_event_site": true, "site_name": "Nashville Arts", "event_count_estimate": 25, "city": "Nashville"}
    ''')

    result = await confirm_source(mock_llm, markdown="# Upcoming Events\n- Concert on May 1...")
    assert result["is_event_site"] is True
    assert result["site_name"] == "Nashville Arts"


@pytest.mark.asyncio
async def test_confirm_source_returns_false_for_non_event_site():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value='''
        {"is_event_site": false, "site_name": "Random Blog", "event_count_estimate": 0, "city": null}
    ''')

    result = await confirm_source(mock_llm, markdown="# My Blog\nToday I ate a sandwich")
    assert result["is_event_site"] is False


@pytest.mark.asyncio
async def test_extract_events_from_markdown_returns_list():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value='''[
        {"title": "Jazz Night", "date": "2026-05-01", "time": "20:00",
         "venue": "Bluebird Cafe", "address": "4104 Hillsboro Pike",
         "price": "$15", "url": "https://example.com/jazz", "description": "Live jazz"},
        {"title": "Art Walk", "date": "2026-05-03", "time": "18:00",
         "venue": "5th Ave Gallery", "address": null,
         "price": "free", "url": null, "description": null}
    ]''')

    events = await extract_events_from_markdown(
        mock_llm, markdown="# May Events\n...", source_url="https://example.com"
    )

    assert len(events) == 2
    assert events[0]["title"] == "Jazz Night"
    assert events[1]["price"] == "free"


@pytest.mark.asyncio
async def test_extract_events_returns_empty_on_failure():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value="I cannot find any events")

    events = await extract_events_from_markdown(
        mock_llm, markdown="# Page with no events", source_url="https://example.com"
    )
    assert events == []


@pytest.mark.asyncio
async def test_score_source_candidates_returns_empty_when_both_calls_fail():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(side_effect=[
        "not json at all",
        "still not json",
    ])

    results = await score_source_candidates(
        mock_llm,
        city="Nashville",
        candidates=[{"url": "https://example.com", "snippet": "events"}],
        threshold=0.7,
    )
    assert results == []


@pytest.mark.asyncio
async def test_confirm_source_returns_fallback_when_both_calls_fail():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(side_effect=[
        "not json",
        "also not json",
    ])

    result = await confirm_source(mock_llm, markdown="# Some page content")
    assert result["is_event_site"] is False
    assert result["event_count_estimate"] == 0
