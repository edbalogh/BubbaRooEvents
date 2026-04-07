import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.ingestion.crawler import fetch_page_markdown


@pytest.mark.asyncio
async def test_fetch_page_markdown_returns_string():
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.markdown = "# Test Page\n\nSome events here"

    mock_crawler = AsyncMock()
    mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler.__aexit__ = AsyncMock(return_value=False)
    mock_crawler.arun = AsyncMock(return_value=mock_result)

    with patch("app.ingestion.crawler.AsyncWebCrawler", return_value=mock_crawler):
        result = await fetch_page_markdown("https://example.com/events")

    assert isinstance(result, str)
    assert "Test Page" in result


@pytest.mark.asyncio
async def test_fetch_page_markdown_returns_empty_on_failure():
    mock_result = MagicMock()
    mock_result.success = False
    mock_result.markdown = None

    mock_crawler = AsyncMock()
    mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler.__aexit__ = AsyncMock(return_value=False)
    mock_crawler.arun = AsyncMock(return_value=mock_result)

    with patch("app.ingestion.crawler.AsyncWebCrawler", return_value=mock_crawler):
        result = await fetch_page_markdown("https://example.com/broken")

    assert result == ""
