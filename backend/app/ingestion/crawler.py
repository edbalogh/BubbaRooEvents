"""Crawl4AI wrapper for fetching page content as clean markdown."""

from __future__ import annotations

import logging

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

from app.core.config import settings

logger = logging.getLogger(__name__)


async def fetch_page_markdown(url: str) -> str:
    """Fetch a URL and return its content as clean markdown. Returns empty string on failure."""
    config = CrawlerRunConfig(
        page_timeout=settings.crawl4ai_timeout * 1000,  # ms
        word_count_threshold=10,
        remove_overlay_elements=True,
    )
    try:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url, config=config)
            if result.success and result.markdown:
                return result.markdown
            logger.warning(f"[crawler] Failed to fetch {url}: success={result.success}")
            return ""
    except Exception as e:
        logger.error(f"[crawler] Error fetching {url}: {e}")
        return ""
