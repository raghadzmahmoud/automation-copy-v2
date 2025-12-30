#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📰 News Scraper Service
خدمة جمع الأخبار من RSS feeds
"""

import time
import re
import feedparser
import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

from settings import GEMINI_API_KEY, GEMINI_MODEL
from app.config.user_config import user_config
from app.utils.database import (
    get_source_id,
    get_source_last_fetched,
    update_source_last_fetched,
    get_language_id,
    get_or_create_category_id,
    save_news_batch
)
from app.services.processing.classifier import classify_with_gemini


class NewsScraper:
    """
    News Scraper - سحب الأخبار من RSS feeds
    """
    
    def __init__(self):
        """تهيئة السحب"""
        self.timeout = user_config.scraping_timeout_seconds
        self.max_news_per_source = user_config.max_news_per_source
        
        # تتبع الأخبار المعالجة
        self.processed_titles = set()
    
    def scrape_rss(self, url: str, source_id: int, language_id: int) -> List[Dict]:
        """
        سحب أخبار من RSS feed
        
        Args:
            url: رابط RSS
            source_id: ID المصدر
            language_id: ID اللغة
        
        Returns:
            List[Dict]: قائمة الأخبار
        """
        news_list = []
        
        try:
            # جلب RSS feed
            feed = self._fetch_rss(url)
            
            if not feed.entries:
                print(f"   ⚠️  No entries found")
                return []
            
            print(f"   📊 Found {len(feed.entries)} entries")
            
            # last_fetched للفلترة
            last_fetched = get_source_last_fetched(source_id)
            
            # معالجة كل entry
            count = 0
            for idx, entry in enumerate(feed.entries, 1):
                # حد الأخبار
                if self.max_news_per_source and count >= self.max_news_per_source:
                    break
                
                try:
                    # استخراج البيانات
                    news_item = self._process_entry(
                        entry, 
                        source_id, 
                        language_id,
                        last_fetched
                    )
                    
                    if news_item:
                        news_list.append(news_item)
                        count += 1
                        
                        # طباعة التقدم
                        print(f"   [{count:3d}] ✓ {news_item['title'][:40]}...")
                        
                        # راحة بين الأخبار
                        time.sleep(3)
                
                except Exception as e:
                    print(f"   [{idx:3d}] ❌ Error: {str(e)[:50]}")
                    continue
            
            # تحديث last_fetched
            if news_list:
                update_source_last_fetched(source_id)
            
            return news_list
            
        except Exception as e:
            print(f"   ❌ Scraping error: {e}")
            return []
    
    def _fetch_rss(self, url: str):
        """جلب RSS feed"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/rss+xml, application/xml, */*',
            }
            
            response = requests.get(
                url,
                headers=headers,
                timeout=self.timeout,
                verify=False,
                allow_redirects=True
            )
            
            response.raise_for_status()
            return feedparser.parse(response.content)
            
        except Exception as e:
            print(f"   ❌ Fetch error: {e}")
            return feedparser.parse("")
    
    def _process_entry(
        self, 
        entry, 
        source_id: int, 
        language_id: int,
        last_fetched: Optional[datetime]
    ) -> Optional[Dict]:
        """معالجة entry واحد"""
        
        # استخراج العنوان
        title = self._clean_html(entry.get('title', ''))
        
        # فحص التكرار
        if self._is_duplicate(title):
            return None
        
        # استخراج التاريخ
        pub_date = self._extract_date(entry)
        if not pub_date:
            pub_date = datetime.now(timezone.utc)
        
        # فلترة القديم
        if last_fetched and pub_date.replace(tzinfo=timezone.utc) <= last_fetched.replace(tzinfo=timezone.utc):
            return None
        
        # استخراج المحتوى
        content = self._extract_content(entry)
        content_text = self._clean_html(content)
        
        # التحقق من الصحة
        if len(title) < 10 and len(content_text) < 20:
            return None
        
        # استخراج الصور والفيديو
        content_img = self._extract_image(entry)
        content_video = self._extract_video(entry)
        
        # التصنيف بالـ AI
        category_name, tags_str, tags_list, ai_success = classify_with_gemini(
            title, 
            content_text,
            max_retries=3
        )
        
        # الحصول على category_id
        category_id = get_or_create_category_id(category_name)
        
        # إضافة للمعالجة
        self.processed_titles.add(title.lower())
        
        return {
            'title': title,
            'content_text': content_text,
            'content_img': content_img,
            'content_video': content_video,
            'tags': tags_str,
            'source_id': source_id,
            'language_id': language_id,
            'category_id': category_id,
            'published_at': pub_date,
            'collected_at': datetime.now(timezone.utc)
        }
    
    def _extract_date(self, entry) -> Optional[datetime]:
        """استخراج التاريخ"""
        # محاولة published
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except:
                pass
        
        # محاولة updated
        if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            try:
                return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            except:
                pass
        
        # محاولة custom parsing
        if hasattr(entry, 'published') and entry.published:
            date_str = entry.published.strip()
            
            # DD/MM/YYYY - HH:MM
            match = re.match(r'(\d{2})/(\d{2})/(\d{4})\s*-?\s*(\d{2}):(\d{2})', date_str)
            if match:
                day, month, year, hour, minute = match.groups()
                try:
                    return datetime(
                        int(year), int(month), int(day),
                        int(hour), int(minute),
                        tzinfo=timezone.utc
                    )
                except:
                    pass
        
        return None
    
    def _extract_content(self, entry) -> str:
        """استخراج المحتوى"""
        if hasattr(entry, 'content') and entry.content:
            return entry.content[0].value
        elif hasattr(entry, 'summary'):
            return entry.summary
        elif hasattr(entry, 'description'):
            return entry.description
        return ""
    
    def _extract_image(self, entry) -> str:
        """استخراج رابط الصورة"""
        # من media_content
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if 'url' in media:
                    url = media['url']
                    if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                        return url
        
        # من المحتوى
        content = self._extract_content(entry)
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
        matches = re.findall(img_pattern, content)
        for match in matches:
            if any(ext in match.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                return match
        
        return ""
    
    def _extract_video(self, entry) -> str:
        """استخراج رابط الفيديو"""
        # من media_content
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if 'url' in media and media.get('type', '').startswith('video'):
                    return media['url']
        
        # من المحتوى
        content = self._extract_content(entry)
        video_pattern = r'https?://[^\s<>"]+\.(?:mp4|webm|ogg|m4v)'
        matches = re.findall(video_pattern, content, re.IGNORECASE)
        if matches:
            return matches[0]
        
        return ""
    
    def _clean_html(self, text: str) -> str:
        """إزالة HTML tags"""
        if not text:
            return ""
        
        # إزالة HTML tags
        text = re.sub(r'<.*?>', '', text)
        
        # فك ترميز HTML entities
        import html
        text = html.unescape(text)
        
        # تنظيف المسافات
        text = ' '.join(text.split())
        
        return text.strip()
    
    def _is_duplicate(self, title: str) -> bool:
        """فحص التكرار"""
        if not title:
            return False
        normalized = title.lower().strip()
        return normalized in self.processed_titles
    
    def save_news_items(self, news_list: List[Dict]) -> int:
        """
        حفظ الأخبار في قاعدة البيانات
        
        Returns:
            int: عدد الأخبار المحفوظة
        """
        return save_news_batch(news_list)