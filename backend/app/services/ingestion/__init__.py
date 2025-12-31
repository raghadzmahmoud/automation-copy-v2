"""
📥 Ingestion Services
خدمات جمع واستيراد الأخبار
"""

from .scraper import NewsScraper
from .source_detector import SourceDetector, SourceType, SourceInfo, detect_source
from .smart_scraper import SmartScraper, ScrapeResult, PageType, ContentStatus, smart_scrape
from .news_crawler import NewsCrawler, CrawlResult, NewsArticle, crawl_news_site
from .content_extractor import ContentExtractor, ExtractionResult, extract_and_prepare_news
from .manual_scraper import ManualScraper, ManualScrapeResult, scrape_url, scrape_urls

__all__ = [
    # Original RSS
    'NewsScraper',
    
    # Source Detection
    'SourceDetector',
    'SourceType', 
    'SourceInfo',
    'detect_source',
    
    # Smart Scraping (NEW)
    'SmartScraper',
    'ScrapeResult',
    'PageType',
    'ContentStatus',
    'smart_scrape',
    
    # News Crawling
    'NewsCrawler',
    'CrawlResult',
    'NewsArticle',
    'crawl_news_site',
    
    # Content Extraction
    'ContentExtractor',
    'ExtractionResult',
    'extract_and_prepare_news',
    
    # Manual Scraping
    'ManualScraper',
    'ManualScrapeResult',
    'scrape_url',
    'scrape_urls',
]