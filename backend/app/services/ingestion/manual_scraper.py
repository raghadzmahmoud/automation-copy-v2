#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📥 Manual URL Scraper
سحب الأخبار من رابط يدخله المستخدم
يجمع: Source Detection + Web Scraping + LLM Extraction
"""

import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

# المكونات - imports متوافقة مع هيكل المشروع
from app.services.ingestion.source_detector import SourceDetector, SourceType, SourceInfo
from app.services.ingestion.web_scraper import WebScraper, ScrapedContent
from app.services.ingestion.content_extractor import (
    ContentExtractor, 
    extract_and_prepare_news, 
    ExtractionResult
)

# Database utilities
try:
    from app.utils.database import (
        get_or_create_category_id,
        save_news_batch,
        get_db_connection
    )
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("⚠️ Database module not available - running in standalone mode")


@dataclass
class ManualScrapeResult:
    """نتيجة السحب اليدوي"""
    success: bool
    url: str
    source_type: str
    
    # الإحصائيات
    news_extracted: int = 0
    news_saved: int = 0
    
    # التفاصيل
    news_items: List[Dict] = field(default_factory=list)
    scraped_content: Optional[ScrapedContent] = None
    
    # الأخطاء
    error_message: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    
    # التوقيت
    processing_time_seconds: float = 0.0


class ManualScraper:
    """
    📥 Manual Scraper
    سحب الأخبار من أي رابط يدخله المستخدم
    
    Usage:
        scraper = ManualScraper()
        result = scraper.scrape_url("https://example.com/news")
        
        if result.success:
            print(f"Extracted {result.news_extracted} news")
            print(f"Saved {result.news_saved} to database")
    """
    
    def __init__(
        self,
        default_source_id: int = 1,
        default_language_id: int = 1,
        auto_save: bool = True,
        timeout: int = 30
    ):
        """
        تهيئة الـ Scraper
        
        Args:
            default_source_id: ID المصدر الافتراضي
            default_language_id: ID اللغة الافتراضية (1 = العربية)
            auto_save: حفظ تلقائي في DB
            timeout: مهلة السحب
        """
        self.default_source_id = default_source_id
        self.default_language_id = default_language_id
        self.auto_save = auto_save and DB_AVAILABLE
        self.timeout = timeout
        
        # المكونات
        self.detector = SourceDetector()
        self.web_scraper = WebScraper(timeout=timeout)
        self.extractor = ContentExtractor()
    
    def scrape_url(
        self,
        url: str,
        source_id: Optional[int] = None,
        language_id: Optional[int] = None,
        save_to_db: Optional[bool] = None
    ) -> ManualScrapeResult:
        """
        سحب الأخبار من رابط
        
        Args:
            url: الرابط
            source_id: ID المصدر (اختياري)
            language_id: ID اللغة (اختياري)
            save_to_db: حفظ في DB (None = استخدام auto_save)
        
        Returns:
            ManualScrapeResult: نتيجة السحب
        """
        start_time = time.time()
        errors = []
        
        # استخدام القيم الافتراضية
        source_id = source_id or self.default_source_id
        language_id = language_id or self.default_language_id
        should_save = save_to_db if save_to_db is not None else self.auto_save
        
        print(f"\n{'='*60}")
        print(f"📥 Manual Scraper")
        print(f"{'='*60}")
        print(f"🔗 URL: {url}")
        
        # ===== Step 1: Source Detection =====
        print(f"\n🔍 Step 1: Detecting source type...")
        source_info = self.detector.detect(url)
        
        if not source_info.is_valid:
            return ManualScrapeResult(
                success=False,
                url=url,
                source_type="unknown",
                error_message=source_info.error_message or "رابط غير صالح",
                processing_time_seconds=time.time() - start_time
            )
        
        print(f"   ✅ Type: {source_info.source_type.value}")
        print(f"   📍 Domain: {source_info.domain}")
        
        # ===== Step 2: Content Scraping =====
        print(f"\n🌐 Step 2: Scraping content...")
        
        if source_info.source_type == SourceType.WEB:
            scraped = self.web_scraper.scrape(source_info.normalized_url)
        elif source_info.source_type == SourceType.RSS:
            # TODO: استخدام RSS scraper الموجود
            errors.append("RSS scraping not implemented in manual mode yet")
            scraped = self.web_scraper.scrape(source_info.normalized_url)
        elif source_info.source_type in [SourceType.TELEGRAM_CHANNEL, SourceType.TELEGRAM_POST]:
            # TODO: Telegram scraper
            return ManualScrapeResult(
                success=False,
                url=url,
                source_type=source_info.source_type.value,
                error_message="Telegram scraping not implemented yet",
                processing_time_seconds=time.time() - start_time
            )
        else:
            return ManualScrapeResult(
                success=False,
                url=url,
                source_type="unknown",
                error_message="نوع المصدر غير مدعوم",
                processing_time_seconds=time.time() - start_time
            )
        
        if not scraped.success:
            return ManualScrapeResult(
                success=False,
                url=url,
                source_type=source_info.source_type.value,
                error_message=scraped.error_message or "فشل في سحب المحتوى",
                processing_time_seconds=time.time() - start_time
            )
        
        print(f"   ✅ Title: {scraped.title[:50]}..." if scraped.title else "   ⚠️ No title")
        print(f"   📝 Content: {len(scraped.clean_text)} chars")
        print(f"   🖼️ Images: {len(scraped.images)}")
        
        # ===== Step 3: LLM Extraction =====
        print(f"\n🤖 Step 3: Extracting news with AI...")
        
        news_list = extract_and_prepare_news(
            content=scraped.clean_text,
            source_url=source_info.normalized_url,
            source_id=source_id,
            language_id=language_id,
            available_images=scraped.images
        )
        
        if not news_list:
            return ManualScrapeResult(
                success=False,
                url=url,
                source_type=source_info.source_type.value,
                scraped_content=scraped,
                error_message="لم يتم استخراج أي أخبار من المحتوى",
                processing_time_seconds=time.time() - start_time
            )
        
        print(f"   ✅ Extracted {len(news_list)} news items")
        
        # ===== Step 4: تعيين category_id =====
        print(f"\n📁 Step 4: Assigning categories...")
        
        for news in news_list:
            if DB_AVAILABLE and 'category_name' in news:
                news['category_id'] = get_or_create_category_id(news['category_name'])
                del news['category_name']
            elif 'category_name' in news:
                # Standalone mode - keep category_name
                news['category_id'] = 1  # default
        
        # ===== Step 5: Save to Database =====
        saved_count = 0
        
        if should_save and DB_AVAILABLE:
            print(f"\n💾 Step 5: Saving to database...")
            saved_count = save_news_batch(news_list)
            print(f"   ✅ Saved {saved_count}/{len(news_list)} news items")
        else:
            print(f"\n⏭️ Step 5: Skipping database save")
            if not DB_AVAILABLE:
                print("   ⚠️ Database not available")
        
        # ===== النتيجة =====
        processing_time = time.time() - start_time
        
        print(f"\n{'='*60}")
        print(f"✅ Completed in {processing_time:.2f}s")
        print(f"   📰 Extracted: {len(news_list)}")
        print(f"   💾 Saved: {saved_count}")
        print(f"{'='*60}\n")
        
        return ManualScrapeResult(
            success=True,
            url=url,
            source_type=source_info.source_type.value,
            news_extracted=len(news_list),
            news_saved=saved_count,
            news_items=news_list,
            scraped_content=scraped,
            errors=errors,
            processing_time_seconds=processing_time
        )
    
    def scrape_multiple(
        self,
        urls: List[str],
        delay_seconds: int = 5
    ) -> List[ManualScrapeResult]:
        """
        سحب من عدة روابط
        
        Args:
            urls: قائمة الروابط
            delay_seconds: التأخير بين الروابط
        
        Returns:
            List[ManualScrapeResult]: نتائج السحب
        """
        results = []
        
        for i, url in enumerate(urls, 1):
            print(f"\n📌 [{i}/{len(urls)}] Processing...")
            
            result = self.scrape_url(url)
            results.append(result)
            
            if i < len(urls):
                print(f"⏳ Waiting {delay_seconds}s before next URL...")
                time.sleep(delay_seconds)
        
        # ملخص
        total_extracted = sum(r.news_extracted for r in results)
        total_saved = sum(r.news_saved for r in results)
        successful = sum(1 for r in results if r.success)
        
        print(f"\n{'='*60}")
        print(f"📊 Batch Summary")
        print(f"{'='*60}")
        print(f"   URLs processed: {len(urls)}")
        print(f"   Successful: {successful}")
        print(f"   Failed: {len(urls) - successful}")
        print(f"   Total news extracted: {total_extracted}")
        print(f"   Total news saved: {total_saved}")
        
        return results


# ============================================
# 🚀 دوال مختصرة للاستخدام السريع
# ============================================

def scrape_url(url: str, save_to_db: bool = True) -> ManualScrapeResult:
    """
    دالة مختصرة لسحب رابط واحد
    
    Usage:
        from app.services.ingestion.manual_scraper import scrape_url
        
        result = scrape_url("https://example.com/news")
        print(f"Extracted: {result.news_extracted}")
    """
    scraper = ManualScraper(auto_save=save_to_db)
    return scraper.scrape_url(url)


def scrape_urls(urls: List[str], save_to_db: bool = True) -> List[ManualScrapeResult]:
    """
    دالة مختصرة لسحب عدة روابط
    """
    scraper = ManualScraper(auto_save=save_to_db)
    return scraper.scrape_multiple(urls)


# ============================================
# 🧪 Test
# ============================================

if __name__ == "__main__":
    import sys
    
    # التحقق من وجود رابط في الأوامر
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
    else:
        # رابط افتراضي للاختبار
        test_url = "https://www.aljazeera.net"
    
    print(f"\n🧪 Testing Manual Scraper")
    print(f"URL: {test_url}\n")
    
    # تشغيل بدون حفظ في DB للاختبار
    scraper = ManualScraper(auto_save=False)
    result = scraper.scrape_url(test_url)
    
    if result.success:
        print(f"\n📰 Extracted News:")
        for i, news in enumerate(result.news_items[:3], 1):  # أول 3 فقط
            print(f"\n--- [{i}] ---")
            print(f"📌 {news['title'][:60]}...")
            print(f"📁 Category ID: {news.get('category_id', 'N/A')}")
            print(f"🏷️ Tags: {news.get('tags', '')[:50]}...")
    else:
        print(f"\n❌ Error: {result.error_message}")