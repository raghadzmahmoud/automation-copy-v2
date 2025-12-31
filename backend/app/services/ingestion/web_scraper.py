#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🌐 Web Scraper
سحب المحتوى من صفحات الويب
يدعم المواقع الديناميكية (JavaScript) والعادية
"""

import re
import requests
import warnings
from typing import Optional, List
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from datetime import datetime, timezone

# تجاهل تحذيرات SSL
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# محاولة استيراد Playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class ScrapedContent:
    """المحتوى المسحوب من الصفحة"""
    url: str
    domain: str
    
    title: str = ""
    raw_text: str = ""
    clean_text: str = ""
    
    images: List[str] = field(default_factory=list)
    videos: List[str] = field(default_factory=list)
    
    meta_description: str = ""
    meta_keywords: str = ""
    published_date: Optional[str] = None
    author: Optional[str] = None
    
    success: bool = False
    error_message: Optional[str] = None
    used_browser: bool = False
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WebScraper:
    """
    🌐 Web Scraper
    سحب وتنظيف محتوى صفحات الويب
    يكتشف تلقائياً المواقع الديناميكية
    """
    
    # العناصر التي يجب إزالتها
    REMOVE_TAGS = [
        'script', 'style', 'nav', 'header', 'footer', 
        'aside', 'iframe', 'noscript', 'form', 'button',
        'input', 'select', 'textarea', 'label'
    ]
    
    # أنماط يجب إزالتها
    REMOVE_PATTERNS = [
        r'ad[-_]?', r'ads[-_]?', r'advert', r'banner',
        r'sidebar', r'widget', r'popup', r'modal',
        r'cookie', r'newsletter', r'subscribe',
        r'social[-_]?share', r'share[-_]?button',
        r'comment', r'related[-_]?post', r'recommended'
    ]
    
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    ]
    
    def __init__(self, timeout: int = 30, use_browser: bool = True):
        self.timeout = timeout
        self.use_browser = use_browser and PLAYWRIGHT_AVAILABLE
        self.session = requests.Session()
        self._ua_index = 0
        
        if use_browser and not PLAYWRIGHT_AVAILABLE:
            print("⚠️ Playwright not installed. Install with: pip install playwright && playwright install chromium")
    
    def scrape(self, url: str, force_browser: bool = False) -> ScrapedContent:
        """سحب محتوى صفحة ويب"""
        domain = self._extract_domain(url)
        
        try:
            # محاولة 1: requests (سريع)
            if not force_browser:
                html = self._fetch_with_requests(url)
                if html:
                    content = self._parse_html(html, url, domain, used_browser=False)
                    
                    # إذا المحتوى كافي
                    if len(content.clean_text) >= 100:
                        return content
                    
                    # إذا المحتوى فارغ، جرب المتصفح
                    print(f"   ⚠️ Content too short ({len(content.clean_text)} chars), trying browser...")
            
            # محاولة 2: Playwright
            if self.use_browser:
                html = self._fetch_with_browser(url)
                if html:
                    return self._parse_html(html, url, domain, used_browser=True)
            
            return ScrapedContent(
                url=url,
                domain=domain,
                success=False,
                error_message="فشل في سحب المحتوى"
            )
            
        except Exception as e:
            return ScrapedContent(
                url=url,
                domain=domain,
                success=False,
                error_message=str(e)
            )
    
    def _fetch_with_requests(self, url: str) -> Optional[str]:
        """جلب بـ requests"""
        try:
            headers = {
                'User-Agent': self._get_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ar,en;q=0.9',
            }
            
            response = self.session.get(
                url,
                headers=headers,
                timeout=self.timeout,
                verify=False,
                allow_redirects=True
            )
            
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            
            return response.text
            
        except Exception:
            return None
    
    def _fetch_with_browser(self, url: str) -> Optional[str]:
        """جلب بـ Playwright"""
        if not PLAYWRIGHT_AVAILABLE:
            return None
        
        print(f"   🌐 Using browser for dynamic content...")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=self._get_user_agent(),
                    locale='ar-SA',
                    viewport={'width': 1920, 'height': 1080}
                )
                
                page = context.new_page()
                page.goto(url, wait_until='networkidle', timeout=self.timeout * 1000)
                page.wait_for_timeout(2000)
                
                html = page.content()
                browser.close()
                
                return html
                
        except Exception:
            return None
    
    def _parse_html(self, html: str, url: str, domain: str, used_browser: bool) -> ScrapedContent:
        """تحليل HTML"""
        if not html:
            return ScrapedContent(
                url=url,
                domain=domain,
                success=False,
                error_message="فشل في جلب الصفحة"
            )
        
        soup = BeautifulSoup(html, 'html.parser')
        
        title = self._extract_title(soup)
        raw_text = self._extract_raw_text(soup)
        clean_text = self._clean_text(raw_text)
        images = self._extract_images(soup, url)
        videos = self._extract_videos(soup, url)
        meta_desc = self._extract_meta_description(soup)
        meta_keywords = self._extract_meta_keywords(soup)
        pub_date = self._extract_published_date(soup)
        author = self._extract_author(soup)
        
        return ScrapedContent(
            url=url,
            domain=domain,
            title=title,
            raw_text=raw_text,
            clean_text=clean_text,
            images=images,
            videos=videos,
            meta_description=meta_desc,
            meta_keywords=meta_keywords,
            published_date=pub_date,
            author=author,
            success=True,
            used_browser=used_browser
        )
    
    def _get_user_agent(self) -> str:
        ua = self.USER_AGENTS[self._ua_index % len(self.USER_AGENTS)]
        self._ua_index += 1
        return ua
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'].strip()
        
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text().strip()
        
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()
        
        return ""
    
    def _extract_raw_text(self, soup: BeautifulSoup) -> str:
        soup_copy = BeautifulSoup(str(soup), 'html.parser')
        
        for tag in self.REMOVE_TAGS:
            for element in soup_copy.find_all(tag):
                element.decompose()
        
        for pattern in self.REMOVE_PATTERNS:
            for element in soup_copy.find_all(class_=re.compile(pattern, re.I)):
                element.decompose()
            for element in soup_copy.find_all(id=re.compile(pattern, re.I)):
                element.decompose()
        
        main_content = self._find_main_content(soup_copy)
        
        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
        else:
            text = soup_copy.get_text(separator='\n', strip=True)
        
        return text
    
    def _find_main_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        article = soup.find('article')
        if article:
            return article
        
        main = soup.find('main')
        if main:
            return main
        
        content_classes = [
            'content', 'article', 'post', 'entry', 'story',
            'news-content', 'article-content', 'post-content',
            'entry-content', 'story-content', 'main-content',
            'article-body', 'story-body', 'post-body'
        ]
        
        for class_name in content_classes:
            content_div = soup.find('div', class_=re.compile(class_name, re.I))
            if content_div:
                return content_div
        
        return None
    
    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        lines = [line.strip() for line in text.split('\n')]
        filtered_lines = [line for line in lines if not line or len(line) > 15]
        text = '\n'.join(filtered_lines)
        
        return text.strip()
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        images = []
        seen = set()
        
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            full_url = urljoin(base_url, og_image['content'])
            images.append(full_url)
            seen.add(full_url)
        
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src:
                full_url = urljoin(base_url, src)
                if full_url not in seen and self._is_valid_image(full_url):
                    images.append(full_url)
                    seen.add(full_url)
        
        return images[:10]
    
    def _extract_videos(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        videos = []
        seen = set()
        
        for video in soup.find_all('video'):
            src = video.get('src')
            if src:
                full_url = urljoin(base_url, src)
                if full_url not in seen:
                    videos.append(full_url)
                    seen.add(full_url)
            
            for source in video.find_all('source'):
                src = source.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    if full_url not in seen:
                        videos.append(full_url)
                        seen.add(full_url)
        
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if any(d in src for d in ['youtube.com', 'vimeo.com', 'dailymotion.com']):
                if src not in seen:
                    videos.append(src)
                    seen.add(src)
        
        return videos[:5]
    
    def _is_valid_image(self, url: str) -> bool:
        skip_patterns = [
            r'icon', r'logo', r'avatar', r'button',
            r'pixel', r'tracking', r'1x1', r'spacer',
            r'\.gif$', r'\.ico$', r'\.svg$'
        ]
        
        url_lower = url.lower()
        for pattern in skip_patterns:
            if re.search(pattern, url_lower):
                return False
        
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        return any(ext in url_lower for ext in valid_extensions)
    
    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            return og_desc['content'].strip()
        
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content'].strip()
        
        return ""
    
    def _extract_meta_keywords(self, soup: BeautifulSoup) -> str:
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords and meta_keywords.get('content'):
            return meta_keywords['content'].strip()
        return ""
    
    def _extract_published_date(self, soup: BeautifulSoup) -> Optional[str]:
        date_metas = [
            ('property', 'article:published_time'),
            ('property', 'og:published_time'),
            ('name', 'date'),
            ('name', 'pubdate'),
        ]
        
        for attr, value in date_metas:
            meta = soup.find('meta', attrs={attr: value})
            if meta and meta.get('content'):
                return meta['content']
        
        time_tag = soup.find('time')
        if time_tag:
            return time_tag.get('datetime') or time_tag.get_text()
        
        return None
    
    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        author_metas = [
            ('property', 'article:author'),
            ('name', 'author'),
        ]
        
        for attr, value in author_metas:
            meta = soup.find('meta', attrs={attr: value})
            if meta and meta.get('content'):
                return meta['content']
        
        author_link = soup.find('a', rel='author')
        if author_link:
            return author_link.get_text().strip()
        
        return None
    
    def _extract_domain(self, url: str) -> str:
        try:
            return urlparse(url).netloc
        except:
            return ""


def scrape_url(url: str, timeout: int = 30, use_browser: bool = True) -> ScrapedContent:
    """دالة مختصرة"""
    scraper = WebScraper(timeout=timeout, use_browser=use_browser)
    return scraper.scrape(url)