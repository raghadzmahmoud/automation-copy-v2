"""
📥 Ingestion Services
خدمات جمع واستيراد الأخبار
"""

from .scraper import NewsScraper
from .source_detector import SourceDetector, SourceType, SourceInfo, detect_source
from .web_scraper import WebScraper, ScrapedContent, scrape_url as web_scrape_url
from .content_extractor import ContentExtractor, ExtractionResult, extract_and_prepare_news
from .manual_scraper import ManualScraper, ManualScrapeResult, scrape_url, scrape_urls

__all__ = [
    # Original
    'NewsScraper',
    
    # Source Detection
    'SourceDetector',
    'SourceType', 
    'SourceInfo',
    'detect_source',
    
    # Web Scraping
    'WebScraper',
    'ScrapedContent',
    'web_scrape_url',
    
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