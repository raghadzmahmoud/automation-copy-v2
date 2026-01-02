#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 Test Scraper
ملف اختبار مستقل

Usage:
    python test_scraper.py
    python test_scraper.py "https://aljazeera.net/rss"
    python test_scraper.py "https://bbc.com/arabic" 5
"""

import sys
import os

# إضافة المسار
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ingestion.scraper import scrape_url, scrape_urls


def test_single_url(url: str, max_articles: int = 5):
    """اختبار رابط واحد"""
    print(f"\n🧪 Testing: {url}")
    print(f"   Max articles: {max_articles}")
    
    result = scrape_url(
        url=url,
        save_to_db=True,
        max_articles=max_articles
    )
    
    print(f"\n📊 Result:")
    print(f"   Success: {result.success}")
    print(f"   Type: {result.source_type}")
    print(f"   Source ID: {result.source_id}")
    print(f"   Extracted: {result.extracted}")
    print(f"   Saved: {result.saved}")
    print(f"   Skipped: {result.skipped}")
    print(f"   Time: {result.time_seconds:.2f}s")
    
    if result.error:
        print(f"   ❌ Error: {result.error}")
    
    return result


def test_multiple_urls():
    """اختبار عدة روابط"""
    test_urls = [
        # RSS
        "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4571-a7f7-a3a8ded9ca52/73d0e1b4-532f-45ef-b135-bba0b7844a97",
        
        # Web
        "https://www.bbc.com/arabic",
        "https://arabic.rt.com",
    ]
    
    print("\n" + "="*60)
    print("🧪 Testing Multiple URLs")
    print("="*60)
    
    results = scrape_urls(test_urls, max_articles=3, save_to_db=False)
    
    print("\n" + "="*60)
    print("📊 Summary")
    print("="*60)
    
    for i, result in enumerate(results):
        status = "✅" if result.success else "❌"
        print(f"{status} [{i+1}] {result.url[:50]}... → {result.extracted} extracted")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
        max_articles = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        test_single_url(url, max_articles)
    else:
        # اختبار افتراضي
        print("Usage: python test_scraper.py <URL> [max_articles]")
        print("\nRunning default test...")
        
        # اختبار RSS
        test_single_url(
            "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4571-a7f7-a3a8ded9ca52/73d0e1b4-532f-45ef-b135-bba0b7844a97",
            max_articles=3
        )