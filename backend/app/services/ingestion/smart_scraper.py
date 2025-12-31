#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧠 Smart Web Scraper
نظام ذكي للتعامل مع كل أنواع صفحات الويب

Supported Page Types:
1. Static Pages - requests + BeautifulSoup
2. Dynamic Pages - Playwright (JS-rendered)
3. Hybrid Pages - requests with Playwright fallback
4. Listing Pages - Extract links only
5. Custom Layout - Site-specific selectors
6. Protected Pages - Custom headers/cookies
7. Invalid Pages - Skip patterns
"""

import re
import time
import requests
import warnings
from enum import Enum
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from datetime import datetime, timezone

# تجاهل تحذيرات SSL
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright not installed. Dynamic pages won't work.")
    print("   Install: pip install playwright && playwright install chromium")


# ============================================
# 📊 Enums & Data Classes
# ============================================

class PageType(Enum):
    """أنواع الصفحات"""
    STATIC = "static"           # HTML ثابت
    DYNAMIC = "dynamic"         # JavaScript-rendered
    HYBRID = "hybrid"           # جزء ثابت + JS
    LISTING = "listing"         # صفحة قوائم/روابط
    CUSTOM = "custom"           # تصميم خاص
    PROTECTED = "protected"     # محمية
    INVALID = "invalid"         # غير صالحة


class ContentStatus(Enum):
    """حالة المحتوى"""
    FULL = "full"               # محتوى كامل
    PARTIAL = "partial"         # محتوى جزئي
    EMPTY = "empty"             # فارغ
    LINKS_ONLY = "links_only"   # روابط فقط


@dataclass
class ScrapeResult:
    """نتيجة السحب"""
    success: bool
    url: str
    page_type: PageType
    content_status: ContentStatus
    
    # المحتوى
    title: str = ""
    content: str = ""
    clean_text: str = ""
    
    # الوسائط
    images: List[str] = field(default_factory=list)
    videos: List[str] = field(default_factory=list)
    
    # الروابط (للـ listing pages)
    article_links: List[str] = field(default_factory=list)
    
    # Meta
    meta_description: str = ""
    published_date: Optional[str] = None
    author: Optional[str] = None
    
    # التقنية
    method_used: str = "requests"  # requests | playwright
    fallback_used: bool = False
    
    # الأخطاء
    error_message: Optional[str] = None


# ============================================
# ⚙️ Site-Specific Configurations
# ============================================

SITE_CONFIGS: Dict[str, Dict] = {
    # مثال: إعدادات خاصة لموقع معين
    # "example.com": {
    #     "content_selector": ".article-body",
    #     "title_selector": "h1.title",
    #     "page_type": PageType.CUSTOM,
    #     "requires_browser": True,
    #     "wait_selector": ".content-loaded",
    #     "cookies": [{"name": "consent", "value": "true"}]
    # },
    
    # الجزيرة - ديناميكي
    "aljazeera.net": {
        "page_type": PageType.DYNAMIC,
        "requires_browser": True,
        "content_selector": ".wysiwyg",
        "wait_for": 2000,
    },
    
    # عرب 48
    "arab48.com": {
        "page_type": PageType.DYNAMIC,
        "requires_browser": True,
        "content_selector": ".article-content",
    },
    
    # وكالة معا
    "maannews.net": {
        "page_type": PageType.DYNAMIC,
        "requires_browser": True,
        "content_selector": ".article-body, .news-content",
    },
}


# ============================================
# 🚫 Skip Patterns (Invalid Pages)
# ============================================

SKIP_URL_PATTERNS = [
    r'/login',
    r'/register',
    r'/signup',
    r'/signin',
    r'/search',
    r'/tag/',
    r'/tags/',
    r'/category/',
    r'/categories/',
    r'/author/',
    r'/page/\d+',
    r'/video/',
    r'/videos/',
    r'/gallery/',
    r'/photos/',
    r'/contact',
    r'/about',
    r'/privacy',
    r'/terms',
    r'/faq',
    r'/rss',
    r'/feed',
    r'/sitemap',
    r'/archive',
    r'\.pdf$',
    r'\.jpg$',
    r'\.png$',
    r'\.mp4$',
    r'\.mp3$',
    r'^#',
    r'^javascript:',
    r'^mailto:',
    r'^tel:',
]


# ============================================
# 📰 Article URL Patterns
# ============================================

ARTICLE_URL_PATTERNS = [
    r'/\d{4}/\d{1,2}/\d{1,2}/',  # /2024/12/31/
    r'/\d{4}/\d{1,2}/',          # /2024/12/
    r'/news/\d+',                 # /news/123456
    r'/article/\d+',              # /article/123
    r'/story/\d+',                # /story/123
    r'/post/\d+',                 # /post/123
    r'[?&]id=\d+',               # ?id=123
    r'[?&]p=\d+',                # ?p=123
    r'-\d{5,}',                   # -123456
    r'/\d{6,}/?$',               # /123456 or /123456/
]


# ============================================
# 🧠 Smart Scraper Class
# ============================================

class SmartScraper:
    """
    🧠 Smart Web Scraper
    يكتشف نوع الصفحة تلقائياً ويختار الاستراتيجية المناسبة
    """
    
    # Thresholds
    MIN_CONTENT_LENGTH = 100      # الحد الأدنى للمحتوى
    HYBRID_THRESHOLD = 300        # للتحقق من hybrid
    
    # Content Selectors (بالترتيب من الأكثر دقة للأعم)
    CONTENT_SELECTORS = [
        'article .article-content',
        'article .post-content', 
        'article .entry-content',
        '.article-body',
        '.article-content',
        '.post-body',
        '.post-content',
        '.news-body',
        '.news-content',
        '.story-body',
        '.story-content',
        '.entry-content',
        '.single-content',
        '#article-body',
        '#post-content',
        '.wysiwyg',
        '.rich-text',
        'article',
        '[role="article"]',
        'main article',
        '.main-content article',
    ]
    
    # Title Selectors
    TITLE_SELECTORS = [
        'h1.article-title',
        'h1.post-title',
        'h1.entry-title',
        '.article-header h1',
        '.post-header h1',
        'article h1',
        'main h1',
        'h1',
    ]
    
    # Elements to Remove
    REMOVE_SELECTORS = [
        'script', 'style', 'nav', 'header', 'footer',
        'aside', 'iframe', 'form', 'noscript',
        '.ad', '.ads', '.advertisement', '.banner',
        '.social-share', '.share-buttons', '.sharing',
        '.related-posts', '.related-articles', '.recommended',
        '.comments', '.comment-section',
        '.sidebar', '.widget',
        '.newsletter', '.subscribe',
        '.popup', '.modal',
        '[class*="ad-"]', '[class*="ads-"]',
        '[id*="ad-"]', '[id*="ads-"]',
    ]
    
    def __init__(
        self,
        timeout: int = 30,
        min_content_length: int = 100,
        use_browser: bool = True
    ):
        self.timeout = timeout
        self.min_content_length = min_content_length
        self.use_browser = use_browser and PLAYWRIGHT_AVAILABLE
        
        # Session for requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ar,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Playwright browser (lazy init)
        self._browser = None
        self._playwright = None
    
    def scrape(self, url: str) -> ScrapeResult:
        """
        سحب صفحة بشكل ذكي
        
        1. يكتشف نوع الصفحة
        2. يختار الاستراتيجية المناسبة
        3. يجرب fallback إذا فشل
        """
        domain = self._get_domain(url)
        
        # Step 1: التحقق من الصفحات غير الصالحة
        if self._is_invalid_url(url):
            return ScrapeResult(
                success=False,
                url=url,
                page_type=PageType.INVALID,
                content_status=ContentStatus.EMPTY,
                error_message="رابط غير صالح للسحب"
            )
        
        # Step 2: التحقق من site-specific config
        site_config = self._get_site_config(domain)
        
        # Step 3: تحديد نوع الصفحة
        page_type = self._detect_page_type(url, site_config)
        
        # Step 4: السحب حسب النوع
        if page_type == PageType.LISTING:
            return self._scrape_listing_page(url, site_config)
        
        if page_type == PageType.DYNAMIC or site_config.get('requires_browser'):
            return self._scrape_with_browser(url, site_config, page_type)
        
        # Try requests first (Static/Hybrid)
        result = self._scrape_with_requests(url, site_config)
        
        # Fallback to browser if content is insufficient
        if result.content_status in [ContentStatus.EMPTY, ContentStatus.PARTIAL]:
            if self.use_browser:
                print(f"   ⚠️ Content insufficient ({len(result.clean_text)} chars), trying browser...")
                browser_result = self._scrape_with_browser(url, site_config, PageType.HYBRID)
                browser_result.fallback_used = True
                return browser_result
        
        return result
    
    def scrape_multiple(self, urls: List[str], delay: float = 1.0) -> List[ScrapeResult]:
        """سحب عدة صفحات"""
        results = []
        
        for i, url in enumerate(urls, 1):
            print(f"   [{i}/{len(urls)}] {url[:50]}...")
            result = self.scrape(url)
            results.append(result)
            
            if i < len(urls):
                time.sleep(delay)
        
        self._close_browser()
        return results
    
    # ============================================
    # 🔍 Detection Methods
    # ============================================
    
    def _detect_page_type(self, url: str, site_config: Dict) -> PageType:
        """تحديد نوع الصفحة"""
        
        # من الإعدادات
        if site_config.get('page_type'):
            return site_config['page_type']
        
        # صفحة قوائم؟
        if self._is_listing_url(url):
            return PageType.LISTING
        
        # افتراضي: hybrid (نجرب requests ثم browser)
        return PageType.HYBRID
    
    def _is_invalid_url(self, url: str) -> bool:
        """التحقق من رابط غير صالح"""
        path = urlparse(url).path.lower()
        
        for pattern in SKIP_URL_PATTERNS:
            if re.search(pattern, path) or re.search(pattern, url.lower()):
                return True
        return False
    
    def _is_listing_url(self, url: str) -> bool:
        """التحقق من صفحة قوائم"""
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')
        
        # الصفحة الرئيسية
        if not path or path == '/':
            return True
        
        # مسارات قصيرة بدون أرقام
        parts = [p for p in path.split('/') if p]
        if len(parts) <= 2 and not any(re.search(r'\d{4,}', p) for p in parts):
            # تحقق إضافي: هل يوجد نمط مقال؟
            if not any(re.search(pattern, url) for pattern in ARTICLE_URL_PATTERNS):
                return True
        
        return False
    
    def _is_article_url(self, url: str) -> bool:
        """التحقق من رابط مقال"""
        for pattern in ARTICLE_URL_PATTERNS:
            if re.search(pattern, url):
                return True
        return False
    
    def _get_site_config(self, domain: str) -> Dict:
        """الحصول على إعدادات الموقع"""
        # إزالة www
        clean_domain = domain.replace('www.', '')
        
        return SITE_CONFIGS.get(clean_domain, {})
    
    def _get_domain(self, url: str) -> str:
        """استخراج الدومين"""
        try:
            return urlparse(url).netloc
        except:
            return ""
    
    # ============================================
    # 📥 Scraping Methods
    # ============================================
    
    def _scrape_with_requests(self, url: str, site_config: Dict) -> ScrapeResult:
        """السحب بـ requests"""
        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                verify=False,
                allow_redirects=True
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            
            html = response.text
            return self._parse_html(html, url, "requests", site_config)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [403, 401]:
                return ScrapeResult(
                    success=False,
                    url=url,
                    page_type=PageType.PROTECTED,
                    content_status=ContentStatus.EMPTY,
                    error_message=f"صفحة محمية: {e.response.status_code}"
                )
            raise
        except Exception as e:
            return ScrapeResult(
                success=False,
                url=url,
                page_type=PageType.STATIC,
                content_status=ContentStatus.EMPTY,
                error_message=str(e)
            )
    
    def _scrape_with_browser(self, url: str, site_config: Dict, page_type: PageType) -> ScrapeResult:
        """السحب بـ Playwright"""
        if not PLAYWRIGHT_AVAILABLE:
            return ScrapeResult(
                success=False,
                url=url,
                page_type=page_type,
                content_status=ContentStatus.EMPTY,
                error_message="Playwright غير متوفر"
            )
        
        try:
            # تهيئة المتصفح
            if not self._browser:
                self._init_browser()
            
            page = self._browser.new_page()
            
            # إضافة cookies إذا موجودة
            if site_config.get('cookies'):
                page.context.add_cookies(site_config['cookies'])
            
            # الذهاب للصفحة
            page.goto(url, wait_until='domcontentloaded', timeout=self.timeout * 1000)
            
            # انتظار إضافي
            wait_time = site_config.get('wait_for', 2000)
            page.wait_for_timeout(wait_time)
            
            # انتظار selector معين
            if site_config.get('wait_selector'):
                try:
                    page.wait_for_selector(site_config['wait_selector'], timeout=5000)
                except:
                    pass
            
            html = page.content()
            page.close()
            
            return self._parse_html(html, url, "playwright", site_config)
            
        except Exception as e:
            return ScrapeResult(
                success=False,
                url=url,
                page_type=page_type,
                content_status=ContentStatus.EMPTY,
                error_message=str(e)
            )
    
    def _scrape_listing_page(self, url: str, site_config: Dict) -> ScrapeResult:
        """سحب صفحة قوائم - استخراج الروابط فقط"""
        
        # جلب الصفحة
        if site_config.get('requires_browser') and self.use_browser:
            result = self._scrape_with_browser(url, site_config, PageType.LISTING)
            html = result.content  # نستخدم raw HTML
        else:
            try:
                response = self.session.get(url, timeout=self.timeout, verify=False)
                response.raise_for_status()
                html = response.text
            except:
                # fallback to browser
                if self.use_browser:
                    result = self._scrape_with_browser(url, site_config, PageType.LISTING)
                    html = result.content
                else:
                    return ScrapeResult(
                        success=False,
                        url=url,
                        page_type=PageType.LISTING,
                        content_status=ContentStatus.EMPTY,
                        error_message="فشل في جلب الصفحة"
                    )
        
        # استخراج الروابط
        soup = BeautifulSoup(html, 'html.parser')
        article_links = self._extract_article_links(soup, url)
        
        return ScrapeResult(
            success=len(article_links) > 0,
            url=url,
            page_type=PageType.LISTING,
            content_status=ContentStatus.LINKS_ONLY,
            article_links=article_links,
            title=self._extract_title(soup),
            method_used="browser" if site_config.get('requires_browser') else "requests"
        )
    
    # ============================================
    # 🔧 Parsing Methods
    # ============================================
    
    def _parse_html(self, html: str, url: str, method: str, site_config: Dict) -> ScrapeResult:
        """تحليل HTML واستخراج المحتوى"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # إزالة العناصر غير المرغوبة
        self._clean_soup(soup)
        
        # استخراج العنوان
        title = self._extract_title(soup)
        
        # استخراج المحتوى
        content_selector = site_config.get('content_selector')
        content, clean_text = self._extract_content(soup, content_selector)
        
        # تحديد حالة المحتوى
        content_status = self._assess_content_status(clean_text)
        
        # استخراج الصور
        images = self._extract_images(soup, url)
        
        # استخراج الفيديو
        videos = self._extract_videos(soup, url)
        
        # Meta
        meta_desc = self._extract_meta_description(soup)
        pub_date = self._extract_date(soup)
        author = self._extract_author(soup)
        
        # تحديد نوع الصفحة
        page_type = PageType.DYNAMIC if method == "playwright" else PageType.STATIC
        if content_status == ContentStatus.PARTIAL:
            page_type = PageType.HYBRID
        
        return ScrapeResult(
            success=content_status != ContentStatus.EMPTY,
            url=url,
            page_type=page_type,
            content_status=content_status,
            title=title,
            content=content,
            clean_text=clean_text,
            images=images,
            videos=videos,
            meta_description=meta_desc,
            published_date=pub_date,
            author=author,
            method_used=method
        )
    
    def _clean_soup(self, soup: BeautifulSoup) -> None:
        """تنظيف DOM"""
        for selector in self.REMOVE_SELECTORS:
            try:
                for element in soup.select(selector):
                    element.decompose()
            except:
                continue
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """استخراج العنوان"""
        # من og:title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content'].strip()
            title = re.split(r'\s*[|\-–—]\s*', title)[0].strip()
            if len(title) > 10:
                return title
        
        # من selectors
        for selector in self.TITLE_SELECTORS:
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    if len(text) > 10:
                        return text
            except:
                continue
        
        # من title tag
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True).split('|')[0].strip()
        
        return ""
    
    def _extract_content(self, soup: BeautifulSoup, custom_selector: str = None) -> Tuple[str, str]:
        """استخراج المحتوى"""
        content_parts = []
        
        # Custom selector أولاً
        selectors = [custom_selector] if custom_selector else []
        selectors.extend(self.CONTENT_SELECTORS)
        
        for selector in selectors:
            if not selector:
                continue
            try:
                elements = soup.select(selector)
                for element in elements:
                    paragraphs = element.find_all('p')
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        if len(text) > 30 and not self._is_junk(text):
                            content_parts.append(text)
                    
                    if content_parts:
                        break
                
                if content_parts:
                    break
            except:
                continue
        
        # Fallback: كل الفقرات
        if not content_parts:
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if len(text) > 50 and not self._is_junk(text):
                    content_parts.append(text)
        
        # إزالة التكرار
        seen = set()
        unique_parts = []
        for part in content_parts:
            if part not in seen:
                seen.add(part)
                unique_parts.append(part)
        
        raw_content = '\n\n'.join(unique_parts[:20])
        clean_text = ' '.join(unique_parts[:20])
        
        return raw_content, clean_text
    
    def _is_junk(self, text: str) -> bool:
        """التحقق من نص غير مفيد"""
        junk_patterns = [
            r'اقرأ أيضا', r'مواضيع ذات صلة', r'شارك الخبر',
            r'تابعنا على', r'انضم إلى', r'اشترك في',
            r'حقوق النشر', r'جميع الحقوق', r'copyright',
            r'all rights', r'المزيد من', r'اقرأ المزيد',
        ]
        text_lower = text.lower()
        return any(re.search(p, text_lower, re.I) for p in junk_patterns)
    
    def _assess_content_status(self, clean_text: str) -> ContentStatus:
        """تقييم حالة المحتوى"""
        length = len(clean_text)
        
        if length < self.MIN_CONTENT_LENGTH:
            return ContentStatus.EMPTY
        elif length < self.HYBRID_THRESHOLD:
            return ContentStatus.PARTIAL
        else:
            return ContentStatus.FULL
    
    def _extract_article_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """استخراج روابط المقالات"""
        domain = self._get_domain(base_url)
        links = []
        seen = set()
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(base_url, href)
            
            # تجاهل الروابط الخارجية
            if domain not in full_url:
                continue
            
            # تجاهل المكرر
            if full_url in seen:
                continue
            seen.add(full_url)
            
            # تجاهل غير الصالحة
            if self._is_invalid_url(full_url):
                continue
            
            # فقط روابط المقالات
            if self._is_article_url(full_url):
                links.append(full_url)
        
        # ترتيب حسب الأحدث
        links.sort(key=lambda x: self._extract_id(x), reverse=True)
        
        return links
    
    def _extract_id(self, url: str) -> int:
        """استخراج ID للترتيب"""
        numbers = re.findall(r'\d{5,}', url)
        return int(numbers[-1]) if numbers else 0
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """استخراج الصور"""
        images = []
        seen = set()
        
        # og:image
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            full_url = urljoin(base_url, og_image['content'])
            images.append(full_url)
            seen.add(full_url)
        
        # img tags
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src:
                full_url = urljoin(base_url, src)
                if full_url not in seen and self._is_valid_image(full_url):
                    images.append(full_url)
                    seen.add(full_url)
        
        return images[:10]
    
    def _is_valid_image(self, url: str) -> bool:
        """التحقق من صورة صالحة"""
        skip = [r'icon', r'logo', r'avatar', r'button', r'pixel', r'1x1', r'\.gif$', r'\.ico$']
        url_lower = url.lower()
        return not any(re.search(p, url_lower) for p in skip)
    
    def _extract_videos(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """استخراج الفيديو"""
        videos = []
        
        for video in soup.find_all('video'):
            src = video.get('src')
            if src:
                videos.append(urljoin(base_url, src))
        
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if any(d in src for d in ['youtube.com', 'vimeo.com', 'dailymotion']):
                videos.append(src)
        
        return videos[:5]
    
    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        """استخراج الوصف"""
        for prop in ['og:description', 'description']:
            meta = soup.find('meta', attrs={'property': prop}) or soup.find('meta', attrs={'name': prop})
            if meta and meta.get('content'):
                return meta['content'].strip()
        return ""
    
    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """استخراج التاريخ"""
        for attr, value in [('property', 'article:published_time'), ('name', 'date')]:
            meta = soup.find('meta', attrs={attr: value})
            if meta and meta.get('content'):
                return meta['content']
        
        time_tag = soup.find('time')
        if time_tag:
            return time_tag.get('datetime') or time_tag.get_text(strip=True)
        
        return None
    
    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """استخراج الكاتب"""
        meta = soup.find('meta', attrs={'name': 'author'})
        if meta and meta.get('content'):
            return meta['content']
        
        author_link = soup.find('a', rel='author')
        if author_link:
            return author_link.get_text(strip=True)
        
        return None
    
    # ============================================
    # 🔧 Browser Management
    # ============================================
    
    def _init_browser(self):
        """تهيئة المتصفح"""
        if not PLAYWRIGHT_AVAILABLE:
            return
        
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
    
    def _close_browser(self):
        """إغلاق المتصفح"""
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except:
            pass
        finally:
            self._browser = None
            self._playwright = None
    
    def __del__(self):
        """Cleanup"""
        self._close_browser()


# ============================================
# 🚀 Helper Functions
# ============================================

def smart_scrape(url: str, use_browser: bool = True) -> ScrapeResult:
    """دالة مختصرة للسحب الذكي"""
    scraper = SmartScraper(use_browser=use_browser)
    result = scraper.scrape(url)
    scraper._close_browser()
    return result


def scrape_article(url: str) -> ScrapeResult:
    """سحب مقال"""
    return smart_scrape(url)


def get_article_links(url: str) -> List[str]:
    """الحصول على روابط المقالات من صفحة"""
    scraper = SmartScraper()
    result = scraper.scrape(url)
    scraper._close_browser()
    return result.article_links