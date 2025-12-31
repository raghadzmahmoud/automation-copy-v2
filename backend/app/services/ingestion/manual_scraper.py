#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📥 Manual URL Scraper
سحب الأخبار من رابط يدخله المستخدم وحفظها في الـ Database
"""

import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

# المكونات
from app.services.ingestion.source_detector import SourceDetector, SourceType, SourceInfo
from app.services.ingestion.smart_scraper import SmartScraper, PageType, ContentStatus
from app.services.ingestion.news_crawler import NewsCrawler, CrawlResult
from app.services.ingestion.content_extractor import (
    ContentExtractor, 
    extract_and_prepare_news, 
    ExtractionResult
)

# Database
from app.utils.database import get_db_connection


# ============================================
# 🗄️ Database Functions
# ============================================

def get_or_create_source(url: str) -> int:
    """
    الحصول على source_id أو إنشاء واحد جديد
    
    - يبحث أولاً عن source موجود بنفس الدومين
    - إذا غير موجود، ينشئ واحد جديد مع source_type_id = 3 (URL Scrape)
    - الـ id يتم إنشاؤه تلقائياً من الـ Database (SERIAL)
    """
    # استخراج الدومين
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')  # إزالة www
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # البحث عن source موجود بنفس الدومين
        cur.execute("""
            SELECT id, name FROM sources 
            WHERE url LIKE %s OR url LIKE %s OR name LIKE %s
            LIMIT 1
        """, (f'%{domain}%', f'%www.{domain}%', f'%{domain}%'))
        
        result = cur.fetchone()
        
        if result:
            print(f"   ✅ Found existing source: {result[1]} (id={result[0]})")
            return result[0]
        
        # إصلاح الـ sequence قبل الإدخال
        cur.execute("SELECT setval('sources_id_seq', (SELECT COALESCE(MAX(id), 0) FROM sources))")
        
        # إنشاء source جديد
        # source_type_id = 3 → URL Scrape (من جدول source_types)
        cur.execute("""
            INSERT INTO sources (name, source_type_id, url, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            RETURNING id
        """, (
            domain,           # name = الدومين
            3,                # source_type_id = 3 (URL Scrape)
            url,              # الرابط الكامل
            True              # is_active
        ))
        
        source_id = cur.fetchone()[0]
        conn.commit()
        
        print(f"   🆕 Created new source: {domain} (id={source_id}, type=URL Scrape)")
        return source_id
        
    except Exception as e:
        conn.rollback()
        print(f"   ⚠️ Error with source: {e}")
        raise e
    finally:
        cur.close()
        conn.close()


def get_or_create_category_id(category_name: str) -> int:
    """الحصول على category_id أو إنشاء واحد جديد"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # البحث عن category موجود
        cur.execute("SELECT id FROM categories WHERE name = %s", (category_name,))
        result = cur.fetchone()
        
        if result:
            return result[0]
        
        # إصلاح الـ sequence قبل الإدخال
        cur.execute("SELECT setval('categories_id_seq', (SELECT COALESCE(MAX(id), 0) FROM categories))")
        
        # إنشاء category جديد
        cur.execute("""
            INSERT INTO categories (name, created_at, updated_at)
            VALUES (%s, NOW(), NOW())
            RETURNING id
        """, (category_name,))
        
        category_id = cur.fetchone()[0]
        conn.commit()
        print(f"   🆕 Created new category: {category_name} (id={category_id})")
        return category_id
        
    except Exception as e:
        conn.rollback()
        return 1  # default category
    finally:
        cur.close()
        conn.close()


def get_input_method_id() -> int:
    """
    الحصول على input_method_id لـ URL Scrape
    يبحث عن "URL Scrape" أو "url_scrape" أو ينشئ واحد جديد
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # البحث عن input method موجود
        cur.execute("""
            SELECT id FROM input_methods 
            WHERE LOWER(name) LIKE '%url%' OR LOWER(name) LIKE '%scrape%'
            LIMIT 1
        """)
        result = cur.fetchone()
        
        if result:
            return result[0]
        
        # إصلاح الـ sequence قبل الإدخال
        cur.execute("SELECT setval('input_methods_id_seq', (SELECT COALESCE(MAX(id), 0) FROM input_methods))")
        
        # إنشاء جديد إذا غير موجود
        cur.execute("""
            INSERT INTO input_methods (name, description, category, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            RETURNING id
        """, (
            'URL Scrape',
            'Manual URL scraping by user',
            'manual',
            True
        ))
        
        method_id = cur.fetchone()[0]
        conn.commit()
        print(f"   🆕 Created input method: URL Scrape (id={method_id})")
        return method_id
        
    except Exception as e:
        conn.rollback()
        return 1
    finally:
        cur.close()
        conn.close()


def save_news_to_db(news_list: List[Dict], source_url: str) -> int:
    """
    حفظ الأخبار في raw_news
    
    Returns:
        int: عدد الأخبار المحفوظة
    """
    if not news_list:
        return 0
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    saved_count = 0
    
    try:
        # إصلاح الـ sequence قبل الإدخال
        cur.execute("SELECT setval('raw_news_id_seq', (SELECT COALESCE(MAX(id), 0) FROM raw_news))")
        
        for news in news_list:
            try:
                cur.execute("""
                    INSERT INTO raw_news (
                        title, content_text, content_img, content_video,
                        tags, source_id, language_id, category_id,
                        input_method_id, source_url, published_at, collected_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                    )
                """, (
                    news.get('title', ''),
                    news.get('content_text', ''),
                    news.get('content_img', ''),
                    news.get('content_video', ''),
                    news.get('tags', ''),
                    news.get('source_id'),
                    news.get('language_id', 1),  # 1 = عربي
                    news.get('category_id'),
                    news.get('input_method_id'),
                    source_url
                ))
                saved_count += 1
                
            except Exception as e:
                print(f"   ⚠️ Error saving news '{news.get('title', '')[:30]}...': {str(e)[:50]}")
                continue
        
        conn.commit()
        return saved_count
        
    except Exception as e:
        conn.rollback()
        print(f"   ❌ Database error: {e}")
        return 0
    finally:
        cur.close()
        conn.close()


# ============================================
# 📥 Manual Scraper
# ============================================

@dataclass
class ManualScrapeResult:
    """نتيجة السحب اليدوي"""
    success: bool
    url: str
    source_type: str
    scrape_mode: str = "single"
    
    # الإحصائيات
    news_extracted: int = 0
    news_saved: int = 0
    pages_crawled: int = 0
    source_id: int = 0
    
    # التفاصيل
    news_items: List[Dict] = field(default_factory=list)
    
    # الأخطاء
    error_message: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    
    # التوقيت
    processing_time_seconds: float = 0.0


class ManualScraper:
    """
    📥 Manual Scraper
    سحب الأخبار من أي رابط وحفظها في الـ Database
    
    Usage:
        scraper = ManualScraper()
        result = scraper.scrape_url("https://www.maannews.net")
        
        if result.success:
            print(f"Saved {result.news_saved} news to source_id={result.source_id}")
    """
    
    def __init__(
        self,
        default_language_id: int = 1,
        auto_save: bool = True,
        timeout: int = 30,
        max_articles: int = 10
    ):
        """
        Args:
            default_language_id: ID اللغة (1 = عربي)
            auto_save: حفظ تلقائي في DB
            timeout: مهلة السحب
            max_articles: الحد الأقصى للأخبار
        """
        self.default_language_id = default_language_id
        self.auto_save = auto_save
        self.timeout = timeout
        self.max_articles = max_articles
        
        # المكونات
        self.detector = SourceDetector()
        self.scraper = SmartScraper(timeout=timeout)
        self.news_crawler = NewsCrawler(max_articles=max_articles, timeout=timeout)
        self.extractor = ContentExtractor()
    
    def scrape_url(
        self,
        url: str,
        language_id: Optional[int] = None,
        save_to_db: Optional[bool] = None,
        force_crawl: bool = False,
        force_single: bool = False
    ) -> ManualScrapeResult:
        """
        سحب الأخبار من رابط
        
        Args:
            url: الرابط المراد سحبه
            language_id: ID اللغة (1 = عربي)
            save_to_db: حفظ في الـ Database
            force_crawl: إجبار وضع الزحف
            force_single: إجبار وضع الصفحة الواحدة
        
        Returns:
            ManualScrapeResult: نتيجة السحب
        """
        start_time = time.time()
        
        language_id = language_id or self.default_language_id
        should_save = save_to_db if save_to_db is not None else self.auto_save
        
        print(f"\n{'='*60}")
        print(f"📥 Manual URL Scraper")
        print(f"{'='*60}")
        print(f"🔗 URL: {url}")
        print(f"💾 Auto Save: {should_save}")
        
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
        
        # التحقق من Telegram
        if source_info.source_type in [SourceType.TELEGRAM_CHANNEL, SourceType.TELEGRAM_POST]:
            return ManualScrapeResult(
                success=False,
                url=url,
                source_type=source_info.source_type.value,
                error_message="Telegram scraping not implemented yet",
                processing_time_seconds=time.time() - start_time
            )
        
        # ===== Step 2: Get/Create Source & Input Method =====
        print(f"\n📌 Step 2: Getting/Creating source in database...")
        
        try:
            source_id = get_or_create_source(source_info.normalized_url)
            input_method_id = get_input_method_id()
            print(f"   ✅ Source ID: {source_id}")
            print(f"   ✅ Input Method ID: {input_method_id}")
        except Exception as e:
            return ManualScrapeResult(
                success=False,
                url=url,
                source_type=source_info.source_type.value,
                error_message=f"Database error: {str(e)}",
                processing_time_seconds=time.time() - start_time
            )
        
        # ===== Step 3: تحديد وضع السحب =====
        use_crawl = force_crawl or (self._should_crawl(url) and not force_single)
        mode = "crawl" if use_crawl else "single"
        print(f"\n📋 Step 3: Scrape mode: {mode.upper()}")
        
        # ===== Step 4: السحب =====
        if use_crawl:
            result = self._scrape_with_crawl(
                url=source_info.normalized_url,
                source_id=source_id,
                language_id=language_id,
                input_method_id=input_method_id,
                should_save=should_save,
                start_time=start_time
            )
        else:
            result = self._scrape_single_page(
                url=source_info.normalized_url,
                source_info=source_info,
                source_id=source_id,
                language_id=language_id,
                input_method_id=input_method_id,
                should_save=should_save,
                start_time=start_time
            )
        
        result.scrape_mode = mode
        result.source_id = source_id
        return result
    
    def _should_crawl(self, url: str) -> bool:
        """تحديد إذا نحتاج crawling"""
        import re
        
        # صفحة رئيسية (domain فقط)
        if re.match(r'^https?://[^/]+/?$', url):
            return True
        
        # لا يحتوي على ID أو تاريخ = ليس مقال
        if not re.search(r'/\d{4}/', url) and not re.search(r'/\d+/?$', url):
            return True
        
        return False
    
    def _scrape_with_crawl(
        self,
        url: str,
        source_id: int,
        language_id: int,
        input_method_id: int,
        should_save: bool,
        start_time: float
    ) -> ManualScrapeResult:
        """السحب باستخدام الزحف"""
        
        print(f"\n🕷️ Step 4: Crawling news site...")
        
        crawl_result = self.news_crawler.crawl(url)
        
        if not crawl_result.success or not crawl_result.combined_content:
            return ManualScrapeResult(
                success=False,
                url=url,
                source_type="web",
                pages_crawled=crawl_result.total_articles_scraped,
                error_message=crawl_result.error_message or "فشل في الزحف على الموقع",
                processing_time_seconds=time.time() - start_time
            )
        
        print(f"   ✅ Crawled {crawl_result.total_articles_scraped} articles")
        print(f"   📝 Combined content: {len(crawl_result.combined_content)} chars")
        
        # ===== Step 5: LLM Extraction =====
        print(f"\n🤖 Step 5: Extracting news with AI...")
        
        news_list = extract_and_prepare_news(
            content=crawl_result.combined_content,
            source_url=url,
            source_id=source_id,
            language_id=language_id,
            available_images=crawl_result.all_images
        )
        
        if not news_list:
            return ManualScrapeResult(
                success=False,
                url=url,
                source_type="web",
                pages_crawled=crawl_result.total_articles_scraped,
                error_message="لم يتم استخراج أي أخبار من المحتوى",
                processing_time_seconds=time.time() - start_time
            )
        
        # إضافة input_method_id لكل خبر
        for news in news_list:
            news['input_method_id'] = input_method_id
        
        return self._finalize_and_save(
            news_list=news_list,
            url=url,
            source_type="web",
            source_id=source_id,
            should_save=should_save,
            start_time=start_time,
            pages_crawled=crawl_result.total_articles_scraped
        )
    
    def _scrape_single_page(
        self,
        url: str,
        source_info: SourceInfo,
        source_id: int,
        language_id: int,
        input_method_id: int,
        should_save: bool,
        start_time: float
    ) -> ManualScrapeResult:
        """السحب من صفحة واحدة"""
        
        print(f"\n🌐 Step 4: Scraping single page...")
        
        scraped = self.scraper.scrape(url)
        
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
        print(f"   📄 Page Type: {scraped.page_type.value}")
        print(f"   🔧 Method: {scraped.method_used}")
        
        # إذا المحتوى قصير، جرب الزحف
        if scraped.content_status in [ContentStatus.EMPTY, ContentStatus.PARTIAL]:
            print(f"   ⚠️ Content insufficient, switching to crawl mode...")
            return self._scrape_with_crawl(
                url=url,
                source_id=source_id,
                language_id=language_id,
                input_method_id=input_method_id,
                should_save=should_save,
                start_time=start_time
            )
        
        # ===== Step 5: LLM Extraction =====
        print(f"\n🤖 Step 5: Extracting news with AI...")
        
        news_list = extract_and_prepare_news(
            content=scraped.clean_text,
            source_url=url,
            source_id=source_id,
            language_id=language_id,
            available_images=scraped.images
        )
        
        if not news_list:
            return ManualScrapeResult(
                success=False,
                url=url,
                source_type=source_info.source_type.value,
                error_message="لم يتم استخراج أي أخبار من المحتوى",
                processing_time_seconds=time.time() - start_time
            )
        
        # إضافة input_method_id لكل خبر
        for news in news_list:
            news['input_method_id'] = input_method_id
        
        return self._finalize_and_save(
            news_list=news_list,
            url=url,
            source_type=source_info.source_type.value,
            source_id=source_id,
            should_save=should_save,
            start_time=start_time
        )
    
    def _finalize_and_save(
        self,
        news_list: List[Dict],
        url: str,
        source_type: str,
        source_id: int,
        should_save: bool,
        start_time: float,
        pages_crawled: int = 0
    ) -> ManualScrapeResult:
        """تعيين التصنيفات والحفظ"""
        
        # ===== تعيين category_id =====
        print(f"\n📁 Step 6: Assigning categories...")
        
        for news in news_list:
            if 'category_name' in news:
                news['category_id'] = get_or_create_category_id(news['category_name'])
                del news['category_name']
        
        print(f"   ✅ Processed {len(news_list)} news items")
        
        # ===== Save to Database =====
        saved_count = 0
        
        if should_save:
            print(f"\n💾 Step 7: Saving to database (raw_news)...")
            saved_count = save_news_to_db(news_list, url)
            print(f"   ✅ Saved {saved_count}/{len(news_list)} news items")
        else:
            print(f"\n⏭️ Step 7: Skipping database save (auto_save=False)")
        
        # ===== النتيجة =====
        processing_time = time.time() - start_time
        
        print(f"\n{'='*60}")
        print(f"✅ Completed in {processing_time:.2f}s")
        print(f"   📰 Extracted: {len(news_list)}")
        print(f"   💾 Saved: {saved_count}")
        print(f"   🔗 Source ID: {source_id}")
        if pages_crawled:
            print(f"   🕷️ Pages crawled: {pages_crawled}")
        print(f"{'='*60}\n")
        
        return ManualScrapeResult(
            success=True,
            url=url,
            source_type=source_type,
            news_extracted=len(news_list),
            news_saved=saved_count,
            pages_crawled=pages_crawled,
            source_id=source_id,
            news_items=news_list,
            processing_time_seconds=processing_time
        )


# ============================================
# 🚀 دوال مختصرة
# ============================================

def scrape_url(url: str, save_to_db: bool = True, max_articles: int = 10) -> ManualScrapeResult:
    """دالة مختصرة لسحب رابط واحد"""
    scraper = ManualScraper(auto_save=save_to_db, max_articles=max_articles)
    return scraper.scrape_url(url)


def scrape_urls(urls: List[str], save_to_db: bool = True, max_articles: int = 10) -> List[ManualScrapeResult]:
    """دالة مختصرة لسحب عدة روابط"""
    scraper = ManualScraper(auto_save=save_to_db, max_articles=max_articles)
    results = []
    
    for i, url in enumerate(urls, 1):
        print(f"\n📌 [{i}/{len(urls)}] Processing: {url[:50]}...")
        result = scraper.scrape_url(url)
        results.append(result)
        
        if i < len(urls):
            time.sleep(3)
    
    return results