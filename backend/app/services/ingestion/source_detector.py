#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔍 Source Detector
تحديد نوع المصدر من الرابط المدخل
"""

import re
from enum import Enum
from typing import Tuple, Optional
from dataclasses import dataclass
from urllib.parse import urlparse


class SourceType(Enum):
    """أنواع المصادر المدعومة"""
    WEB = "web"
    TELEGRAM_CHANNEL = "telegram_channel"
    TELEGRAM_POST = "telegram_post"
    RSS = "rss"
    UNKNOWN = "unknown"


@dataclass
class SourceInfo:
    """معلومات المصدر المكتشف"""
    source_type: SourceType
    url: str
    normalized_url: str
    is_valid: bool
    error_message: Optional[str] = None
    
    # معلومات إضافية حسب النوع
    telegram_username: Optional[str] = None
    telegram_post_id: Optional[int] = None
    domain: Optional[str] = None


class SourceDetector:
    """
    🔍 Source Detector
    يكتشف نوع المصدر ويتحقق من صحة الرابط
    """
    
    # Telegram patterns
    TELEGRAM_PATTERNS = [
        # https://t.me/channel_name
        r'^https?://t\.me/([a-zA-Z_][a-zA-Z0-9_]{3,})/?$',
        # https://t.me/channel_name/123 (post)
        r'^https?://t\.me/([a-zA-Z_][a-zA-Z0-9_]{3,})/(\d+)/?$',
        # https://telegram.me/channel_name
        r'^https?://telegram\.me/([a-zA-Z_][a-zA-Z0-9_]{3,})/?$',
        # https://telegram.me/channel_name/123 (post)
        r'^https?://telegram\.me/([a-zA-Z_][a-zA-Z0-9_]{3,})/(\d+)/?$',
    ]
    
    # RSS patterns (common extensions)
    RSS_PATTERNS = [
        r'\.rss$',
        r'\.xml$',
        r'/rss/?$',
        r'/feed/?$',
        r'/atom/?$',
        r'format=rss',
        r'format=xml',
        r'feed=rss',
    ]
    
    def detect(self, url: str) -> SourceInfo:
        """
        اكتشاف نوع المصدر من الرابط
        
        Args:
            url: الرابط المدخل
        
        Returns:
            SourceInfo: معلومات المصدر
        """
        # تنظيف الرابط
        url = url.strip()
        
        # التحقق من وجود رابط
        if not url:
            return SourceInfo(
                source_type=SourceType.UNKNOWN,
                url=url,
                normalized_url="",
                is_valid=False,
                error_message="الرابط فارغ"
            )
        
        # إضافة https إذا لم يكن موجود
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # التحقق من صحة الرابط
        if not self._is_valid_url(url):
            return SourceInfo(
                source_type=SourceType.UNKNOWN,
                url=url,
                normalized_url=url,
                is_valid=False,
                error_message="صيغة الرابط غير صحيحة"
            )
        
        # محاولة اكتشاف Telegram
        telegram_info = self._detect_telegram(url)
        if telegram_info:
            return telegram_info
        
        # محاولة اكتشاف RSS
        if self._is_rss_url(url):
            return SourceInfo(
                source_type=SourceType.RSS,
                url=url,
                normalized_url=url,
                is_valid=True,
                domain=self._extract_domain(url)
            )
        
        # افتراضياً: Web
        return SourceInfo(
            source_type=SourceType.WEB,
            url=url,
            normalized_url=url,
            is_valid=True,
            domain=self._extract_domain(url)
        )
    
    def _is_valid_url(self, url: str) -> bool:
        """التحقق من صحة صيغة الرابط"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def _detect_telegram(self, url: str) -> Optional[SourceInfo]:
        """اكتشاف روابط Telegram"""
        for pattern in self.TELEGRAM_PATTERNS:
            match = re.match(pattern, url, re.IGNORECASE)
            if match:
                groups = match.groups()
                username = groups[0]
                post_id = int(groups[1]) if len(groups) > 1 else None
                
                if post_id:
                    # منشور محدد
                    return SourceInfo(
                        source_type=SourceType.TELEGRAM_POST,
                        url=url,
                        normalized_url=f"https://t.me/{username}/{post_id}",
                        is_valid=True,
                        telegram_username=username,
                        telegram_post_id=post_id
                    )
                else:
                    # قناة
                    return SourceInfo(
                        source_type=SourceType.TELEGRAM_CHANNEL,
                        url=url,
                        normalized_url=f"https://t.me/{username}",
                        is_valid=True,
                        telegram_username=username
                    )
        
        return None
    
    def _is_rss_url(self, url: str) -> bool:
        """التحقق إذا كان RSS"""
        url_lower = url.lower()
        for pattern in self.RSS_PATTERNS:
            if re.search(pattern, url_lower):
                return True
        return False
    
    def _extract_domain(self, url: str) -> str:
        """استخراج الدومين من الرابط"""
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return ""


# ============================================
# 🧪 دوال مساعدة للاستخدام المباشر
# ============================================

def detect_source(url: str) -> SourceInfo:
    """
    دالة مختصرة لاكتشاف نوع المصدر
    
    Usage:
        from source_detector import detect_source
        
        info = detect_source("https://example.com/news")
        print(info.source_type)  # SourceType.WEB
    """
    detector = SourceDetector()
    return detector.detect(url)


def is_telegram_url(url: str) -> bool:
    """التحقق السريع إذا كان رابط Telegram"""
    info = detect_source(url)
    return info.source_type in [SourceType.TELEGRAM_CHANNEL, SourceType.TELEGRAM_POST]


def is_web_url(url: str) -> bool:
    """التحقق السريع إذا كان رابط ويب"""
    info = detect_source(url)
    return info.source_type == SourceType.WEB


# ============================================
# 🧪 Test
# ============================================

if __name__ == "__main__":
    # اختبار
    test_urls = [
        "https://www.aljazeera.net/news/2024/1/15/example",
        "https://t.me/TestChannel",
        "https://t.me/TestChannel/12345",
        "telegram.me/AnotherChannel",
        "https://example.com/rss",
        "https://example.com/feed.xml",
        "invalid-url",
        "",
        "www.example.com/news",
    ]
    
    detector = SourceDetector()
    
    print("=" * 60)
    print("🔍 Source Detector Test")
    print("=" * 60)
    
    for url in test_urls:
        info = detector.detect(url)
        print(f"\n📎 URL: {url}")
        print(f"   Type: {info.source_type.value}")
        print(f"   Valid: {info.is_valid}")
        if info.telegram_username:
            print(f"   Telegram User: @{info.telegram_username}")
        if info.telegram_post_id:
            print(f"   Post ID: {info.telegram_post_id}")
        if info.error_message:
            print(f"   ❌ Error: {info.error_message}")