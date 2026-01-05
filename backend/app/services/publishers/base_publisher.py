#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🌐 Base Publisher Class
قاعدة مشتركة لكل منصات السوشال ميديا

هذا الكلاس يوفر:
- جلب المحتوى من الـ API
- جلب الصور (Generated / Original)
- جلب التقرير الكامل
- تنسيق الهاشتاجات
"""

import re
import json
import requests
from io import BytesIO
from typing import Dict, Optional, Tuple
from abc import ABC, abstractmethod


class BaseSocialPublisher(ABC):
    """
    Base class for all social media publishers
    
    كل platform يرث من هذا الكلاس ويعمل override للـ publish method
    """
    
    def __init__(self, api_base_url: str):
        """
        Args:
            api_base_url: Base URL للـ API (مثلاً: http://localhost:8000)
        """
        self.api_base_url = api_base_url.rstrip('/')
    
    # ==========================================
    # 📊 Data Fetching Methods (مشتركة)
    # ==========================================
    
    def get_social_content(self, report_id: int, platform: str) -> Optional[Dict]:
        """
        جلب محتوى السوشال ميديا من الـ API
        
        Args:
            report_id: ID التقرير
            platform: 'facebook', 'instagram', 'twitter', etc.
        
        Returns:
            {'title': '...', 'content': '...', 'hashtags': '...'}
        """
        try:
            url = f"{self.api_base_url}/api/v1/social-media/by-report/{report_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Failed to get social content: {response.status_code}")
                return None
            
            data = response.json()
            content_json = data.get('content', '{}')
            
            # Parse JSON
            social_posts = json.loads(content_json)
            platform_data = social_posts.get(platform, {})
            
            if not platform_data:
                print(f"⚠️  No {platform} content found")
                return None
            
            return {
                'title': platform_data.get('title', ''),
                'content': platform_data.get('content', ''),
                'raw': platform_data  # للاحتياط
            }
        
        except Exception as e:
            print(f"❌ Error getting social content: {e}")
            return None
    
    def get_image(self, report_id: int, prefer_generated: bool = True) -> Optional[BytesIO]:
        """
        جلب الصورة (Generated أولاً، ثم Original)
        
        Args:
            report_id: ID التقرير
            prefer_generated: لو True يجرب Generated أولاً
        
        Returns:
            BytesIO object of the image, or None
        """
        
        # Try Generated Image first
        if prefer_generated:
            generated_img = self._get_generated_image(report_id)
            if generated_img:
                return generated_img
        
        # Fallback to Original Image
        original_img = self._get_original_image(report_id)
        if original_img:
            return original_img
        
        print("❌ No image found (neither generated nor original)")
        return None
    
    def _get_generated_image(self, report_id: int) -> Optional[BytesIO]:
        """جلب الصورة المولدة من الـ AI"""
        try:
            url = f"{self.api_base_url}/api/v1/images/by-report/{report_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            image_url = data.get('file_url')
            
            if not image_url:
                return None
            
            # Download image
            img_response = requests.get(
                image_url,
                headers={'User-Agent': 'Mozilla/5.0'},
                stream=True,
                timeout=15
            )
            
            if img_response.status_code == 200:
                print("✅ Using Generated Image")
                return BytesIO(img_response.content)
            
            return None
        
        except Exception as e:
            print(f"⚠️  Generated image failed: {e}")
            return None
    
    def _get_original_image(self, report_id: int) -> Optional[BytesIO]:
        """جلب الصورة الأصلية من الأخبار"""
        try:
            url = f"{self.api_base_url}/api/v1/reports/reports/{report_id}/raw-news-images"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            # افترض أن الـ API يرجع list من الصور
            if isinstance(data, list) and len(data) > 0:
                image_url = data[0].get('url') or data[0].get('image_url')
            elif isinstance(data, dict):
                image_url = data.get('url') or data.get('image_url')
            else:
                return None
            
            if not image_url:
                return None
            
            # Download image
            img_response = requests.get(
                image_url,
                headers={'User-Agent': 'Mozilla/5.0'},
                stream=True,
                timeout=15
            )
            
            if img_response.status_code == 200:
                print("✅ Using Original Image")
                return BytesIO(img_response.content)
            
            return None
        
        except Exception as e:
            print(f"⚠️  Original image failed: {e}")
            return None
    
    def get_full_report(self, report_id: int) -> Optional[str]:
        """
        جلب التقرير الكامل (للكومنت)
        
        Returns:
            النص الكامل للتقرير
        """
        try:
            url = f"{self.api_base_url}/api/v1/reports/{report_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Failed to get report: {response.status_code}")
                return None
            
            data = response.json()
            
            # افترض أن الـ API يرجع object فيه title و content
            title = data.get('title', '')
            content = data.get('content', '') or data.get('body', '')
            
            if title and content:
                return f"{title}\n\n{content}"
            elif content:
                return content
            elif title:
                return title
            
            print("⚠️  Report has no content")
            return None
        
        except Exception as e:
            print(f"❌ Error getting report: {e}")
            return None
    
    # ==========================================
    # 🎨 Formatting Methods (مشتركة)
    # ==========================================
    
    @staticmethod
    def format_hashtags(text: str) -> str:
        """
        تنسيق الهاشتاجات بشكل احترافي:
        - فصل الهاشتاجات الملتصقة
        - إضافة _ بين الكلمات الملتصقة
        
        مثال:
        "#مهرجانالمؤسس#الهجن" → "#مهرجان_المؤسس #الهجن"
        """
        
        # استخراج الهاشتاجات
        hashtags = re.findall(r'#\w+', text)
        
        if not hashtags:
            return text
        
        # تنسيق كل هاشتاج
        formatted = []
        for tag in hashtags:
            # إزالة #
            tag_text = tag[1:]
            
            # فصل الكلمات بـ _
            # نبحث عن الحروف الكبيرة أو الأرقام
            spaced = re.sub(r'([a-z])([A-Z])', r'\1_\2', tag_text)
            spaced = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', spaced)
            
            formatted.append(f'#{spaced}')
        
        # استبدال الهاشتاجات القديمة بالجديدة
        result = text
        for old, new in zip(hashtags, formatted):
            result = result.replace(old, new, 1)
        
        # فصل الهاشتاجات الملتصقة
        result = re.sub(r'(#\w+)(#\w+)', r'\1 \2', result)
        
        return result
    
    @staticmethod
    def format_facebook_post(title: str, content: str) -> str:
        """
        تنسيق بوست فيسبوك:
        Title
        
        Content
        
        #hashtags
        """
        
        # فصل المحتوى عن الهاشتاجات
        content_parts = content.rsplit('\n#', 1)
        
        if len(content_parts) == 2:
            main_content = content_parts[0].strip()
            hashtags = '#' + content_parts[1].strip()
            hashtags = BaseSocialPublisher.format_hashtags(hashtags)
        else:
            main_content = content.strip()
            hashtags = ''
        
        # تجميع البوست
        parts = []
        
        if title:
            parts.append(title.strip())
        
        if main_content:
            parts.append(main_content)
        
        if hashtags:
            parts.append(hashtags)
        
        return '\n\n'.join(parts)
    
    # ==========================================
    # 🚀 Abstract Method (كل platform يعمله)
    # ==========================================
    
    @abstractmethod
    def publish(self, report_id: int) -> Dict:
        """
        نشر على المنصة
        
        كل platform يعمل override لهذا الـ method
        
        Returns:
            {'success': bool, 'post_id': str, 'message': str}
        """
        pass