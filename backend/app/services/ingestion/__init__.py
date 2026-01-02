"""
📥 Ingestion Services
خدمات سحب الأخبار

Usage:
    from app.services.ingestion import scrape_url
    result = scrape_url("https://example.com/rss")
"""

from .scraper import (
    scrape_url,
    scrape_urls,
    ScrapeResult,
    SourceType,
    RssScraper,
    WebScraper,
)

__all__ = [
    'scrape_url',
    'scrape_urls',
    'ScrapeResult',
    'SourceType',
    'RssScraper',
    'WebScraper',
]