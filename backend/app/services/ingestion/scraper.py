#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📥 Unified News Scraper
ملف واحد شامل لسحب الأخبار من RSS و Web

📊 Source Types:
   - RSS (source_type_id from DB)
   - URL Scrape (source_type_id from DB)

Usage:
    from app.services.ingestion.scraper import scrape_url
    result = scrape_url("https://example.com/rss")
"""

import re
import time
import json
import requests
import feedparser
import warnings
from enum import Enum
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

# تجاهل تحذيرات SSL
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Playwright (اختياري)
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Database
from app.utils.database import (
    get_source_type_id,
    get_or_create_source,
    get_or_create_category_id,
    get_input_method_id,
    get_recent_news_titles,
    save_news_item,
    update_source_last_fetched,
)

# Classifier
try:
    from app.services.processing.classifier import classify_with_gemini
    CLASSIFIER_AVAILABLE = True
except ImportError:
    CLASSIFIER_AVAILABLE = False
    print("⚠️ Classifier not available")


# ============================================
# 📊 Enums & Data Classes
# ============================================

class SourceType(Enum):
    RSS = "RSS"
    WEB = "URL Scrape"
    UNKNOWN = "unknown"


@dataclass
class ScrapeResult:
    """نتيجة السحب"""
    success: bool
    url: str
    source_type: str
    source_type_id: int = 0
    source_id: int = 0
    
    extracted: int = 0
    saved: int = 0
    skipped: int = 0
    
    items: List[Dict] = field(default_factory=list)
    error: Optional[str] = None
    time_seconds: float = 0.0


# ============================================
# 🔍 Source Detection
# ============================================

RSS_PATTERNS = [
    r'\.rss$', r'\.xml$', r'/rss/?$', r'/feed/?$',
    r'/feeds?/', r'/atom/?$', r'[?&]format=rss',
]

def detect_source_type(url: str) -> SourceType:
    """اكتشاف نوع المصدر"""
    url_lower = url.lower()
    for pattern in RSS_PATTERNS:
        if re.search(pattern, url_lower):
            return SourceType.RSS
    return SourceType.WEB


def get_domain(url: str) -> str:
    """استخراج الدومين"""
    try:
        return urlparse(url).netloc.replace('www.', '')
    except:
        return ""


# ============================================
# 📰 RSS Scraper
# ============================================

class RssScraper:
    """سحب من RSS Feeds"""
    
    SOURCE_TYPE_NAME = "RSS"
    
    def __init__(self, language_id: int = 1):
        self.language_id = language_id
        self.source_type_id = get_source_type_id(self.SOURCE_TYPE_NAME)
        self.input_method_id = get_input_method_id("scraper")
    
    def scrape(
        self,
        feed_url: str,
        source_id: int,
        existing_titles: Set[str],
        max_items: int = 20,
        save_to_db: bool = True
    ) -> ScrapeResult:
        """سحب من RSS"""
        
        print(f"\n📰 RSS Scraper")
        print(f"   🔗 {feed_url}")
        
        try:
            # Parse feed
            feed = feedparser.parse(feed_url)
            
            if not feed.entries:
                return ScrapeResult(
                    success=False, url=feed_url,
                    source_type=self.SOURCE_TYPE_NAME,
                    error="No entries in feed"
                )
            
            print(f"   ✅ Found {len(feed.entries)} entries")

            news_items = []
            saved_count = 0
            skipped_count = 0
            
            for entry in feed.entries[:max_items]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                
                if not title:
                    continue
                
                # Deduplication
                if title in existing_titles:
                    skipped_count += 1
                    continue
                
                # استخراج المحتوى
                content = self._get_content(entry)
                image = self._get_image(entry)
                pub_date = self._get_date(entry)
                
                # التصنيف
                category, tags_str = self._classify(title, content)
                category_id = get_or_create_category_id(category)
                
                news_item = {
                    "title": title,
                    "content_text": self._clean_html(content),
                    "content_img": image,
                    "content_video": None,
                    "tags": tags_str,
                    "source_id": source_id,
                    "source_type_id": self.source_type_id,
                    "source_url": link,
                    "language_id": self.language_id,
                    "category_id": category_id,
                    "input_method_id": self.input_method_id,
                    "original_text": None,
                    "metadata": json.dumps({"feed_url": feed_url}),
                    "published_at": pub_date,
                }
                
                news_items.append(news_item)
                
                if save_to_db:
                    if save_news_item(news_item, existing_titles):
                        saved_count += 1
                        existing_titles.add(title)
                        print(f"   ✅ {title[:50]}...")
                    else:
                        skipped_count += 1
            
            return ScrapeResult(
                success=True,
                url=feed_url,
                source_type=self.SOURCE_TYPE_NAME,
                source_type_id=self.source_type_id,
                source_id=source_id,
                extracted=len(news_items),
                saved=saved_count,
                skipped=skipped_count,
                items=news_items
            )
            
        except Exception as e:
            return ScrapeResult(
                success=False, url=feed_url,
                source_type=self.SOURCE_TYPE_NAME,
                error=str(e)
            )
    
    def _get_content(self, entry) -> str:
        if "content" in entry and entry.content:
            return entry.content[0].get("value", "")
        return entry.get("summary", "") or entry.get("description", "")
    
    def _get_image(self, entry) -> Optional[str]:
        if "media_content" in entry:
            for media in entry.media_content:
                url = media.get("url", "")
                if any(ext in url.lower() for ext in ['.jpg', '.png', '.jpeg']):
                    return url
        if "media_thumbnail" in entry:
            return entry.media_thumbnail[0].get("url")
        return None
    
    def _get_date(self, entry) -> datetime:
        for field in ["published_parsed", "updated_parsed"]:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    import time as t
                    return datetime.fromtimestamp(t.mktime(getattr(entry, field)), tz=timezone.utc)
                except:
                    pass
        return datetime.now(timezone.utc)
    
    def _classify(self, title: str, content: str) -> tuple:
        if CLASSIFIER_AVAILABLE:
            try:
                cat, tags, _, _ = classify_with_gemini(title, content)
                return cat, tags
            except:
                pass
        return "أخرى", ""
    
    def _clean_html(self, text: str) -> str:
        if not text:
            return ""
        soup = BeautifulSoup(text, "html.parser")
        return soup.get_text(separator="\n", strip=True)


# ============================================
# 🌐 Web Scraper (with Crawler)
# ============================================

# إعدادات المواقع المعروفة
SITE_CONFIGS = {
    'bbc.com': {
        'dynamic': True,
        'article_selectors': ['a[href*="/arabic/"]', '.media__link', 'article a'],
        'title_selectors': ['h1', '.story-headline'],
        'content_selectors': ['article', '.story-body'],
    },
    'rt.com': {
        'dynamic': True,
        'article_selectors': ['a[href*="/world/"]', 'a[href*="/russia/"]', 'a[href*="/middle_east/"]', '.card__heading a'],
        'title_selectors': ['h1', '.article__heading'],
        'content_selectors': ['.article__text', '.text'],
    },
    'aljazeera.net': {
        'dynamic': True,
        'article_selectors': ['a[href*="/news/"]', '.gc__title a', 'article a'],
        'title_selectors': ['h1'],
        'content_selectors': ['.wysiwyg', '.article-body'],
    },
    'wafa.ps': {
        'dynamic': True,
        'article_selectors': ['a[href*="/Pages/Details/"]', '.news-item a', 'article a'],
        'title_selectors': ['h1', '.news-title'],
        'content_selectors': ['.news-content', '.content'],
    },
}

# ✅ أنماط روابط الأخبار
ARTICLE_PATTERNS = [
    r'/\d{5,}',              # ID طويل (5+ أرقام) مثل /1745080
    r'/\d{4}/\d{2}/\d{2}/',  # تاريخ /2024/01/15/
    r'/article/',
    r'/news/\d',             # /news/ متبوع برقم
    r'/story/',
    r'/details/',
    r'/Pages/Details/',
    r'-\d{5,}',              # عنوان-1745080
]

# ✅ روابط يجب تجاهلها
IGNORE_PATTERNS = [
    r'^#', r'^javascript:', r'^mailto:',
    r'/tag/', r'/category/', r'/author/',
    r'/search', r'/login', r'/about',
    r'/privacy', r'/terms', r'/contact',
    r'/page/\d+$',           # pagination
    r'/live/?$',             # صفحات البث المباشر
    r'/video/?$',            # صفحات الفيديو العامة
    r'/photos?/?$',          # صفحات الصور
    r'\.(jpg|png|gif|pdf|mp4|mp3)$',
    r'^https?://[^/]+/?$',   # الصفحة الرئيسية فقط
]

# ✅ الحدود الدنيا
MIN_PATH_LENGTH = 25        # طول المسار
MIN_ANCHOR_LENGTH = 15      # طول نص الرابط
MIN_CONTENT_LENGTH = 100    # طول المحتوى


class WebScraper:
    """سحب من صفحات الويب مع Crawler"""
    
    SOURCE_TYPE_NAME = "URL Scrape"
    
    def __init__(self, language_id: int = 1, max_articles: int = 10, timeout: int = 30):
        self.language_id = language_id
        self.max_articles = max_articles
        self.timeout = timeout
        self.source_type_id = get_source_type_id(self.SOURCE_TYPE_NAME)
        self.input_method_id = get_input_method_id("scraper")
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'ar,en;q=0.9',
        }
    
    def scrape(
        self,
        url: str,
        source_id: int,
        existing_titles: Set[str],
        save_to_db: bool = True
    ) -> ScrapeResult:
        """سحب من الويب"""
        
        print(f"\n🌐 Web Scraper")
        print(f"   🔗 {url}")
        
        domain = get_domain(url)
        config = self._get_config(domain)
        
        # جلب HTML
        use_dynamic = config.get('dynamic', False) and PLAYWRIGHT_AVAILABLE
        
        if use_dynamic:
            print(f"   🎭 Using Playwright")
            html = self._fetch_playwright(url)
        else:
            print(f"   📄 Using requests")
            html = self._fetch_requests(url)
        
        if not html:
            return ScrapeResult(
                success=False, url=url,
                source_type=self.SOURCE_TYPE_NAME,
                error="Failed to fetch page"
            )
        
        # ✅ استخراج روابط المقالات مع النص المرتبط
        soup = BeautifulSoup(html, 'html.parser')
        candidates = self._find_article_candidates(soup, url, config)
        
        print(f"   🔗 Found {len(candidates)} potential articles")
        
        if not candidates:
            return ScrapeResult(
                success=False, url=url,
                source_type=self.SOURCE_TYPE_NAME,
                error="No articles found"
            )
        
        # طباعة المرشحين
        print(f"\n   📋 Candidates:")
        for c in candidates[:self.max_articles]:
            anchor_preview = c['anchor'][:40] + "..." if len(c['anchor']) > 40 else c['anchor']
            print(f"      → {anchor_preview or '(no text)'}")
        
        # سحب المقالات
        news_items = []
        saved_count = 0
        skipped_count = 0
        failed_count = 0
        
        for i, candidate in enumerate(candidates):
            # توقف إذا وصلنا للحد المطلوب
            if len(news_items) >= self.max_articles:
                break
            
            link = candidate['url']
            anchor = candidate['anchor']
            
            print(f"\n   📰 [{i+1}] Fetching: {link[:60]}...")
            
            article = self._fetch_article(link, config)
            
            # ✅ تحقق: هل نجح الجلب وهل هناك محتوى كافي؟
            if not article:
                print(f"      ⚠️ Failed to fetch")
                failed_count += 1
                continue
            
            title = article.get("title", "").strip()
            content = article.get("content", "")
            
            if not title or len(title) < 10:
                print(f"      ⚠️ No title, skip")
                failed_count += 1
                continue
            
            if len(content) < MIN_CONTENT_LENGTH:
                print(f"      ⚠️ Content too short ({len(content)} chars), skip")
                failed_count += 1
                continue
            
            # Deduplication
            if title in existing_titles:
                print(f"      ⏭️ Skip (exists): {title[:40]}...")
                skipped_count += 1
                continue
            
            # التصنيف
            category, tags_str = self._classify(title, content)
            category_id = get_or_create_category_id(category)
            
            news_item = {
                "title": title,
                "content_text": content,
                "content_img": article.get("image"),
                "content_video": None,
                "tags": tags_str,
                "source_id": source_id,
                "source_type_id": self.source_type_id,
                "source_url": link,
                "language_id": self.language_id,
                "category_id": category_id,
                "input_method_id": self.input_method_id,
                "original_text": None,
                "metadata": json.dumps({"scraped_from": url}),
                "published_at": article.get("date") or datetime.now(timezone.utc),
            }
            
            news_items.append(news_item)
            
            if save_to_db:
                if save_news_item(news_item, existing_titles):
                    saved_count += 1
                    existing_titles.add(title)
                    print(f"      ✅ Saved: {title[:50]}...")
                else:
                    skipped_count += 1
                    print(f"      ⏭️ Skipped (DB)")
            else:
                print(f"      📝 {title[:50]}...")
            
            time.sleep(1)  # تأخير
        
        print(f"\n   📊 Summary: {len(news_items)} extracted, {failed_count} failed, {skipped_count} skipped")
        
        return ScrapeResult(
            success=len(news_items) > 0,
            url=url,
            source_type=self.SOURCE_TYPE_NAME,
            source_type_id=self.source_type_id,
            source_id=source_id,
            extracted=len(news_items),
            saved=saved_count,
            skipped=skipped_count,
            items=news_items
        )
    
    def _get_config(self, domain: str) -> Dict:
        for site, config in SITE_CONFIGS.items():
            if site in domain:
                return config
        return {}
    
    def _fetch_requests(self, url: str) -> Optional[str]:
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout, verify=False)
            response.raise_for_status()
            return response.text
        except:
            return None
    
    def _fetch_playwright(self, url: str) -> Optional[str]:
        if not PLAYWRIGHT_AVAILABLE:
            return self._fetch_requests(url)
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=self.headers['User-Agent'])
                page.goto(url, wait_until='networkidle', timeout=self.timeout * 1000)
                
                # تمرير
                for _ in range(3):
                    page.evaluate('window.scrollBy(0, 500)')
                    time.sleep(0.5)
                
                html = page.content()
                browser.close()
                return html
        except Exception as e:
            print(f"   ⚠️ Playwright error: {e}")
            return self._fetch_requests(url)
    
    def _find_article_candidates(self, soup: BeautifulSoup, base_url: str, config: Dict) -> List[Dict]:
        """
        ✅ البحث عن روابط المقالات مع النص المرتبط
        
        Returns:
            List of {'url': str, 'anchor': str, 'score': int}
        """
        candidates = []
        seen_urls = set()
        
        # 1️⃣ Selectors خاصة بالموقع (أولوية عالية)
        for selector in config.get('article_selectors', []):
            try:
                for a in soup.select(selector):
                    result = self._evaluate_link(a, base_url, seen_urls, priority=10)
                    if result:
                        candidates.append(result)
                        seen_urls.add(result['url'])
            except:
                continue
        
        # 2️⃣ بحث عام إذا لم نجد كفاية
        if len(candidates) < 10:
            for a in soup.find_all('a', href=True):
                result = self._evaluate_link(a, base_url, seen_urls, priority=0)
                if result:
                    candidates.append(result)
                    seen_urls.add(result['url'])
        
        # ترتيب حسب الـ score
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        return candidates
    
    def _evaluate_link(self, a_tag, base_url: str, seen_urls: Set[str], priority: int = 0) -> Optional[Dict]:
        """
        ✅ تقييم رابط واحد
        
        يعطي score بناءً على:
        - طول المسار
        - وجود ID طويل
        - طول النص المرتبط
        """
        href = a_tag.get('href')
        if not href:
            return None
        
        full_url = urljoin(base_url, href)
        
        # تجاهل المكرر
        if full_url in seen_urls:
            return None
        
        # تحقق أساسي
        if not self._is_valid_url(full_url, base_url):
            return None
        
        # النص المرتبط
        anchor_text = a_tag.get_text(strip=True)
        
        # حساب الـ score
        score = priority
        path = urlparse(full_url).path
        
        # ✅ أنماط معروفة للأخبار
        for pattern in ARTICLE_PATTERNS:
            if re.search(pattern, full_url):
                score += 20
                break
        
        # ✅ طول المسار (روابط الأخبار طويلة)
        if len(path) > 100:
            score += 15
        elif len(path) > 50:
            score += 10
        elif len(path) > MIN_PATH_LENGTH:
            score += 5
        
        # ✅ طول النص المرتبط (عنوان الخبر)
        if len(anchor_text) > 40:
            score += 15
        elif len(anchor_text) > MIN_ANCHOR_LENGTH:
            score += 10
        
        # الحد الأدنى للقبول
        if score < 5:
            return None
        
        return {
            'url': full_url,
            'anchor': anchor_text,
            'score': score
        }
    
    def _is_valid_url(self, url: str, base_url: str) -> bool:
        """التحقق من صحة الرابط"""
        if not url.startswith('http'):
            return False
        
        # نفس الدومين
        base_domain = get_domain(base_url)
        url_domain = get_domain(url)
        if base_domain not in url_domain and url_domain not in base_domain:
            return False
        
        # تجاهل الأنماط غير المرغوبة
        for pattern in IGNORE_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        return True
    
    def _fetch_article(self, url: str, config: Dict) -> Optional[Dict]:
        """جلب محتوى مقال"""
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout, verify=False)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # العنوان
            title = ""
            for selector in config.get('title_selectors', ['h1']):
                elem = soup.select_one(selector)
                if elem:
                    title = elem.get_text(strip=True)
                    break
            if not title:
                h1 = soup.find('h1')
                title = h1.get_text(strip=True) if h1 else ""
            
            # المحتوى
            content = ""
            for selector in config.get('content_selectors', ['article']):
                elem = soup.select_one(selector)
                if elem:
                    for tag in elem.find_all(['script', 'style', 'nav', 'aside']):
                        tag.decompose()
                    content = elem.get_text(separator='\n', strip=True)
                    if len(content) > MIN_CONTENT_LENGTH:
                        break
            
            if not content or len(content) < MIN_CONTENT_LENGTH:
                paragraphs = soup.find_all('p')
                content = '\n'.join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50)
            
            # الصورة
            image = ""
            og = soup.find('meta', property='og:image')
            if og:
                image = og.get('content', '')
            
            # التاريخ
            pub_date = None
            meta_date = soup.find('meta', property='article:published_time')
            if meta_date:
                try:
                    pub_date = date_parser.parse(meta_date['content'])
                except:
                    pass
            
            return {
                "title": title,
                "content": content,
                "image": image,
                "date": pub_date
            }
            
        except Exception as e:
            return None
    
    def _classify(self, title: str, content: str) -> tuple:
        if CLASSIFIER_AVAILABLE:
            try:
                cat, tags, _, _ = classify_with_gemini(title, content)
                return cat, tags
            except:
                pass
        return "أخرى", ""


# ============================================
# 🚀 Main Entry Point
# ============================================

def scrape_url(
    url: str,
    save_to_db: bool = True,
    max_articles: int = 10,
    language_id: int = 1
) -> ScrapeResult:
    """
    🎯 الدالة الرئيسية لسحب الأخبار
    """
    start_time = time.time()
    
    print(f"\n{'='*60}")
    print(f"📥 News Scraper")
    print(f"{'='*60}")
    print(f"🔗 URL: {url}")
    
    # تنظيف الرابط
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # اكتشاف النوع
    source_type = detect_source_type(url)
    domain = get_domain(url)
    
    print(f"🏷️ Type: {source_type.value}")
    print(f"📍 Domain: {domain}")
    
    # الحصول على source_type_id من Database
    source_type_id = get_source_type_id(source_type.value)
    
    # إنشاء/جلب المصدر
    source_id = get_or_create_source(
        source_url=url,
        source_type_id=source_type_id,
        source_name=domain
    )
    
    print(f"📌 Source ID: {source_id}")
    
    # جلب آخر 100 خبر للـ Deduplication
    existing_titles = get_recent_news_titles(source_id, limit=100)
    print(f"📋 Existing: {len(existing_titles)} titles")
    
    # السحب حسب النوع
    if source_type == SourceType.RSS:
        scraper = RssScraper(language_id=language_id)
        result = scraper.scrape(
            feed_url=url,
            source_id=source_id,
            existing_titles=existing_titles,
            max_items=max_articles,
            save_to_db=save_to_db
        )
    else:
        scraper = WebScraper(language_id=language_id, max_articles=max_articles)
        result = scraper.scrape(
            url=url,
            source_id=source_id,
            existing_titles=existing_titles,
            save_to_db=save_to_db
        )
    
    # تحديث last_fetched
    if result.success and result.saved > 0:
        update_source_last_fetched(source_id)
    
    result.time_seconds = time.time() - start_time
    result.source_id = source_id
    
    # طباعة النتيجة
    print(f"\n{'='*60}")
    if result.success:
        print(f"✅ SUCCESS in {result.time_seconds:.2f}s")
    else:
        print(f"❌ FAILED: {result.error}")
    print(f"   📰 Extracted: {result.extracted}")
    print(f"   💾 Saved: {result.saved}")
    print(f"   ⏭️ Skipped: {result.skipped}")
    print(f"{'='*60}\n")
    
    return result


def scrape_urls(urls: List[str], **kwargs) -> List[ScrapeResult]:
    """سحب عدة روابط"""
    results = []
    for i, url in enumerate(urls, 1):
        print(f"\n📌 [{i}/{len(urls)}] {url}")
        result = scrape_url(url, **kwargs)
        results.append(result)
        if i < len(urls):
            time.sleep(3)
    return results


# ============================================
# 🧪 Test
# ============================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        url = sys.argv[1]
        max_articles = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        result = scrape_url(url, max_articles=max_articles, save_to_db=False)
    else:
        print("Usage: python scraper.py <URL> [max_articles]")
        print("Example: python scraper.py https://arabic.rt.com 5")