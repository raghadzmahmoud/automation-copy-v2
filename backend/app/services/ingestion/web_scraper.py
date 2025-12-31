#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🌐 Web Scraper
سحب المحتوى من صفحات الويب
"""

import re
import requests
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from datetime import datetime, timezone


@dataclass
class ScrapedContent:
    """المحتوى المسحوب من الصفحة"""
    url: str
    domain: str
    
    # المحتوى الأساسي
    title: str = ""
    raw_text: str = ""           # النص الخام (كامل)
    clean_text: str = ""         # النص المنظف
    
    # الوسائط
    images: List[str] = field(default_factory=list)
    videos: List[str] = field(default_factory=list)
    
    # معلومات إضافية
    meta_description: str = ""
    meta_keywords: str = ""
    published_date: Optional[str] = None
    author: Optional[str] = None
    
    # حالة السحب
    success: bool = False
    error_message: Optional[str] = None
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WebScraper:
    """
    🌐 Web Scraper
    سحب وتنظيف محتوى صفحات الويب
    """
    
    # العناصر التي يجب إزالتها
    REMOVE_TAGS = [
        'script', 'style', 'nav', 'header', 'footer', 
        'aside', 'iframe', 'noscript', 'form', 'button',
        'input', 'select', 'textarea', 'label',
        'advertisement', 'ads', 'social-share', 'comments'
    ]
    
    # Classes/IDs التي تدل على إعلانات أو محتوى غير مهم
    REMOVE_PATTERNS = [
        r'ad[-_]?', r'ads[-_]?', r'advert', r'banner',
        r'sidebar', r'widget', r'popup', r'modal',
        r'cookie', r'newsletter', r'subscribe',
        r'social[-_]?share', r'share[-_]?button',
        r'comment', r'related[-_]?post', r'recommended'
    ]
    
    # User Agents للتبديل
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    ]
    
    def __init__(self, timeout: int = 30):
        """
        تهيئة الـ Scraper
        
        Args:
            timeout: مهلة الطلب بالثواني
        """
        self.timeout = timeout
        self.session = requests.Session()
        self._ua_index = 0
    
    def scrape(self, url: str) -> ScrapedContent:
        """
        سحب محتوى صفحة ويب
        
        Args:
            url: رابط الصفحة
        
        Returns:
            ScrapedContent: المحتوى المسحوب
        """
        domain = self._extract_domain(url)
        
        try:
            # جلب الصفحة
            html = self._fetch_page(url)
            
            if not html:
                return ScrapedContent(
                    url=url,
                    domain=domain,
                    success=False,
                    error_message="فشل في جلب الصفحة"
                )
            
            # تحليل HTML
            soup = BeautifulSoup(html, 'html.parser')
            
            # استخراج المحتوى
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
                success=True
            )
            
        except Exception as e:
            return ScrapedContent(
                url=url,
                domain=domain,
                success=False,
                error_message=str(e)
            )
    
    def _fetch_page(self, url: str) -> Optional[str]:
        """جلب HTML الصفحة"""
        try:
            headers = {
                'User-Agent': self._get_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ar,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            response = self.session.get(
                url,
                headers=headers,
                timeout=self.timeout,
                verify=False,
                allow_redirects=True
            )
            
            response.raise_for_status()
            
            # محاولة تحديد الترميز الصحيح
            response.encoding = response.apparent_encoding or 'utf-8'
            
            return response.text
            
        except Exception as e:
            print(f"❌ Fetch error: {e}")
            return None
    
    def _get_user_agent(self) -> str:
        """الحصول على User Agent (تبديل دوري)"""
        ua = self.USER_AGENTS[self._ua_index % len(self.USER_AGENTS)]
        self._ua_index += 1
        return ua
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """استخراج عنوان الصفحة"""
        # محاولة من og:title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'].strip()
        
        # محاولة من title tag
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text().strip()
        
        # محاولة من h1
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()
        
        return ""
    
    def _extract_raw_text(self, soup: BeautifulSoup) -> str:
        """استخراج النص الخام من الصفحة"""
        # نسخة للعمل عليها
        soup_copy = BeautifulSoup(str(soup), 'html.parser')
        
        # إزالة العناصر غير المرغوبة
        for tag in self.REMOVE_TAGS:
            for element in soup_copy.find_all(tag):
                element.decompose()
        
        # إزالة العناصر بناءً على class/id
        for pattern in self.REMOVE_PATTERNS:
            # البحث في class
            for element in soup_copy.find_all(class_=re.compile(pattern, re.I)):
                element.decompose()
            # البحث في id
            for element in soup_copy.find_all(id=re.compile(pattern, re.I)):
                element.decompose()
        
        # محاولة إيجاد المحتوى الرئيسي
        main_content = self._find_main_content(soup_copy)
        
        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
        else:
            # fallback: كل النص
            text = soup_copy.get_text(separator='\n', strip=True)
        
        return text
    
    def _find_main_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """محاولة إيجاد المحتوى الرئيسي"""
        # البحث عن article
        article = soup.find('article')
        if article:
            return article
        
        # البحث عن main
        main = soup.find('main')
        if main:
            return main
        
        # البحث عن div بـ class شائعة للمحتوى
        content_classes = [
            'content', 'article', 'post', 'entry', 'story',
            'news-content', 'article-content', 'post-content',
            'entry-content', 'story-content', 'main-content'
        ]
        
        for class_name in content_classes:
            content_div = soup.find('div', class_=re.compile(class_name, re.I))
            if content_div:
                return content_div
        
        # البحث عن div بـ id شائعة
        content_ids = ['content', 'article', 'main', 'post', 'story']
        for id_name in content_ids:
            content_div = soup.find('div', id=re.compile(id_name, re.I))
            if content_div:
                return content_div
        
        return None
    
    def _clean_text(self, text: str) -> str:
        """تنظيف النص"""
        if not text:
            return ""
        
        # إزالة الأسطر الفارغة المتكررة
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # إزالة المسافات الزائدة
        text = re.sub(r'[ \t]+', ' ', text)
        
        # إزالة المسافات في بداية ونهاية كل سطر
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        # إزالة الأسطر القصيرة جداً (غالباً زبالة)
        lines = text.split('\n')
        filtered_lines = []
        for line in lines:
            # إبقاء الأسطر الفارغة للفصل، أو الأسطر بطول معقول
            if not line or len(line) > 20:
                filtered_lines.append(line)
        text = '\n'.join(filtered_lines)
        
        return text.strip()
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """استخراج روابط الصور"""
        images = []
        seen = set()
        
        # من img tags
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src:
                full_url = urljoin(base_url, src)
                if full_url not in seen and self._is_valid_image(full_url):
                    images.append(full_url)
                    seen.add(full_url)
        
        # من og:image
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            full_url = urljoin(base_url, og_image['content'])
            if full_url not in seen:
                images.insert(0, full_url)  # الأهم في البداية
        
        return images[:10]  # حد أقصى 10 صور
    
    def _extract_videos(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """استخراج روابط الفيديو"""
        videos = []
        seen = set()
        
        # من video tags
        for video in soup.find_all('video'):
            src = video.get('src')
            if src:
                full_url = urljoin(base_url, src)
                if full_url not in seen:
                    videos.append(full_url)
                    seen.add(full_url)
            
            # من source داخل video
            for source in video.find_all('source'):
                src = source.get('src')
                if src:
                    full_url = urljoin(base_url, src)
                    if full_url not in seen:
                        videos.append(full_url)
                        seen.add(full_url)
        
        # من iframes (YouTube, Vimeo, etc.)
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if any(domain in src for domain in ['youtube.com', 'vimeo.com', 'dailymotion.com']):
                if src not in seen:
                    videos.append(src)
                    seen.add(src)
        
        return videos[:5]  # حد أقصى 5 فيديوهات
    
    def _is_valid_image(self, url: str) -> bool:
        """التحقق من صحة رابط الصورة"""
        # تجاهل الصور الصغيرة والأيقونات
        skip_patterns = [
            r'icon', r'logo', r'avatar', r'button',
            r'pixel', r'tracking', r'1x1', r'spacer',
            r'\.gif$', r'\.ico$'
        ]
        
        url_lower = url.lower()
        for pattern in skip_patterns:
            if re.search(pattern, url_lower):
                return False
        
        # التحقق من امتداد الصورة
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        return any(ext in url_lower for ext in valid_extensions)
    
    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        """استخراج وصف الصفحة"""
        # og:description
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            return og_desc['content'].strip()
        
        # meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content'].strip()
        
        return ""
    
    def _extract_meta_keywords(self, soup: BeautifulSoup) -> str:
        """استخراج الكلمات المفتاحية"""
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords and meta_keywords.get('content'):
            return meta_keywords['content'].strip()
        return ""
    
    def _extract_published_date(self, soup: BeautifulSoup) -> Optional[str]:
        """استخراج تاريخ النشر"""
        # من meta tags
        date_metas = [
            ('property', 'article:published_time'),
            ('property', 'og:published_time'),
            ('name', 'date'),
            ('name', 'pubdate'),
            ('name', 'publish_date'),
        ]
        
        for attr, value in date_metas:
            meta = soup.find('meta', attrs={attr: value})
            if meta and meta.get('content'):
                return meta['content']
        
        # من time tag
        time_tag = soup.find('time')
        if time_tag:
            return time_tag.get('datetime') or time_tag.get_text()
        
        return None
    
    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """استخراج اسم الكاتب"""
        # من meta tags
        author_metas = [
            ('property', 'article:author'),
            ('name', 'author'),
            ('name', 'article:author'),
        ]
        
        for attr, value in author_metas:
            meta = soup.find('meta', attrs={attr: value})
            if meta and meta.get('content'):
                return meta['content']
        
        # من rel="author"
        author_link = soup.find('a', rel='author')
        if author_link:
            return author_link.get_text().strip()
        
        return None
    
    def _extract_domain(self, url: str) -> str:
        """استخراج الدومين"""
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return ""


# ============================================
# 🧪 دالة مساعدة للاستخدام المباشر
# ============================================

def scrape_url(url: str, timeout: int = 30) -> ScrapedContent:
    """
    دالة مختصرة لسحب محتوى صفحة
    
    Usage:
        from web_scraper import scrape_url
        
        content = scrape_url("https://example.com/news/article")
        print(content.clean_text)
    """
    scraper = WebScraper(timeout=timeout)
    return scraper.scrape(url)


# ============================================
# 🧪 Test
# ============================================

if __name__ == "__main__":
    # اختبار
    test_url = "https://www.aljazeera.net"
    
    print("=" * 60)
    print("🌐 Web Scraper Test")
    print("=" * 60)
    print(f"\n📎 URL: {test_url}")
    
    scraper = WebScraper()
    result = scraper.scrape(test_url)
    
    print(f"\n✅ Success: {result.success}")
    print(f"📰 Title: {result.title}")
    print(f"📝 Text Length: {len(result.clean_text)} chars")
    print(f"🖼️ Images: {len(result.images)}")
    print(f"🎬 Videos: {len(result.videos)}")
    
    if result.clean_text:
        print(f"\n📄 First 500 chars:")
        print("-" * 40)
        print(result.clean_text[:500])