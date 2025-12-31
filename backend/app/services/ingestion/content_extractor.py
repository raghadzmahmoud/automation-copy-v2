#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🤖 Content Extractor using LLM
استخراج الأخبار من المحتوى الخام باستخدام Gemini
"""

import json
import time
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from google import genai

# Import settings - يعمل من backend/ مباشرة
try:
    from settings import GEMINI_API_KEY
    # محاولة استيراد الموديل الجديد
    try:
        from settings import GEMINI_EXTRACTION_MODEL
        EXTRACTION_MODEL = GEMINI_EXTRACTION_MODEL
    except ImportError:
        from settings import GEMINI_MODEL
        EXTRACTION_MODEL = GEMINI_MODEL
except ImportError:
    # Fallback إذا كان يعمل من مكان آخر
    import os
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    EXTRACTION_MODEL = os.getenv('GEMINI_EXTRACTION_MODEL', 'gemini-2.5-flash-lite')


# تهيئة Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)


# التصنيفات الصالحة (نفس classifier.py)
VALID_CATEGORIES = [
    'سياسة', 'اقتصاد', 'رياضة', 'تكنولوجيا', 'صحة',
    'ثقافة', 'محلي', 'دولي', 'عسكري', 'اجتماعي', 'فن', 'تعليم'
]


@dataclass
class ExtractedNews:
    """خبر مستخرج"""
    title: str
    content: str
    category: str
    tags: List[str]
    
    # اختياري
    published_date: Optional[str] = None
    author: Optional[str] = None
    image_url: Optional[str] = None
    
    # للتخزين
    tags_str: str = ""
    
    def __post_init__(self):
        """تحويل tags لـ string"""
        if self.tags and not self.tags_str:
            self.tags_str = ", ".join(self.tags)


@dataclass
class ExtractionResult:
    """نتيجة الاستخراج"""
    success: bool
    news_items: List[ExtractedNews] = field(default_factory=list)
    total_extracted: int = 0
    error_message: Optional[str] = None
    raw_response: Optional[str] = None


class ContentExtractor:
    """
    🤖 Content Extractor
    يستخرج الأخبار من المحتوى الخام باستخدام LLM
    """
    
    # الحد الأقصى للمحتوى (للحفاظ على context window)
    MAX_CONTENT_LENGTH = 30000  # ~30K chars للنص
    
    def __init__(self, model: str = None):
        """
        تهيئة المستخرج
        
        Args:
            model: اسم موديل Gemini (افتراضي: GEMINI_EXTRACTION_MODEL)
        """
        self.model = model or EXTRACTION_MODEL
    
    def extract_news(
        self, 
        content: str, 
        source_url: str = "",
        available_images: List[str] = None,
        max_retries: int = 3
    ) -> ExtractionResult:
        """
        استخراج الأخبار من المحتوى
        
        Args:
            content: المحتوى الخام
            source_url: رابط المصدر (للمساعدة في التحليل)
            available_images: قائمة الصور المتاحة
            max_retries: عدد المحاولات
        
        Returns:
            ExtractionResult: نتيجة الاستخراج
        """
        if not content or len(content.strip()) < 50:
            return ExtractionResult(
                success=False,
                error_message="المحتوى قصير جداً أو فارغ"
            )
        
        # اقتطاع المحتوى إذا كان طويلاً جداً
        if len(content) > self.MAX_CONTENT_LENGTH:
            content = content[:self.MAX_CONTENT_LENGTH]
            print(f"   ⚠️ Content truncated to {self.MAX_CONTENT_LENGTH} chars")
        
        # بناء الـ prompt
        prompt = self._build_extraction_prompt(content, source_url, available_images)
        
        # المحاولات
        for attempt in range(max_retries):
            try:
                # استدعاء LLM
                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt
                )
                
                result_text = response.text.strip()
                
                # تحليل الرد
                news_items = self._parse_response(result_text, available_images)
                
                if news_items:
                    return ExtractionResult(
                        success=True,
                        news_items=news_items,
                        total_extracted=len(news_items),
                        raw_response=result_text
                    )
                else:
                    raise ValueError("لم يتم استخراج أي أخبار")
                    
            except json.JSONDecodeError as e:
                print(f"   ⚠️ Attempt {attempt + 1}: JSON error - {str(e)[:50]}")
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                    
            except Exception as e:
                print(f"   ⚠️ Attempt {attempt + 1}: {str(e)[:50]}")
                if attempt < max_retries - 1:
                    time.sleep(4)
                    continue
        
        return ExtractionResult(
            success=False,
            error_message=f"فشل الاستخراج بعد {max_retries} محاولات"
        )
    
    def _build_extraction_prompt(
        self, 
        content: str, 
        source_url: str,
        available_images: List[str] = None
    ) -> str:
        """بناء prompt الاستخراج"""
        
        images_section = ""
        if available_images:
            images_list = "\n".join([f"  [{i+1}] {img}" for i, img in enumerate(available_images[:10])])
            images_section = f"""
🖼️ الصور المتاحة:
{images_list}

عند ربط صورة بخبر، استخدم الرقم [1], [2], إلخ أو الرابط مباشرة.
"""
        
        prompt = f"""أنت محلل أخبار متخصص. مهمتك استخراج كل الأخبار من المحتوى التالي.

📰 المصدر: {source_url}
{images_section}

📄 المحتوى:
---
{content}
---

🎯 المطلوب:
استخرج كل خبر منفصل من المحتوى أعلاه. لكل خبر أعطني:

1. title: عنوان الخبر (واضح ومختصر)
2. content: محتوى الخبر (الفقرات المتعلقة به، 100-500 كلمة)
3. category: التصنيف من القائمة: {VALID_CATEGORIES}
4. tags: 5-10 كلمات مفتاحية (بدون مسافات، استخدم _ للربط)
5. published_date: تاريخ النشر إن وجد (أو null)
6. author: اسم الكاتب إن وجد (أو null)
7. image_index: رقم الصورة المناسبة من القائمة أعلاه (أو null)

📋 التنسيق المطلوب (JSON فقط):
```json
{{
  "news_count": 3,
  "news_items": [
    {{
      "title": "عنوان الخبر الأول",
      "content": "محتوى الخبر الكامل...",
      "category": "سياسة",
      "tags": ["فلسطين", "غزة", "الاحتلال"],
      "published_date": "2024-01-15",
      "author": "اسم الكاتب",
      "image_index": 1
    }},
    {{
      "title": "عنوان الخبر الثاني",
      "content": "...",
      "category": "اقتصاد",
      "tags": ["..."],
      "published_date": null,
      "author": null,
      "image_index": null
    }}
  ]
}}
```

⚠️ قواعد مهمة:
- استخرج كل خبر منفصل (قد يكون 1 أو 10 أو أكثر)
- لا تدمج أخبار مختلفة في خبر واحد
- المحتوى يجب أن يكون مفيد ومفهوم بذاته
- تجاهل الإعلانات والمحتوى غير الإخباري
- Tags بالعربية، استخدم _ بدل المسافة
- أجب بـ JSON فقط، بدون أي نص إضافي

الرد:"""
        
        return prompt
    
    def _parse_response(
        self, 
        response_text: str,
        available_images: List[str] = None
    ) -> List[ExtractedNews]:
        """تحليل رد LLM"""
        
        # تنظيف الرد
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        response_text = response_text.replace('`', '').strip()
        
        # استخراج JSON
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        
        if start_idx == -1 or end_idx == -1:
            raise ValueError("No JSON found in response")
        
        json_str = response_text[start_idx:end_idx+1]
        data = json.loads(json_str)
        
        # استخراج الأخبار
        news_items = []
        items_data = data.get('news_items', [])
        
        if not items_data:
            # محاولة بتنسيق مختلف
            if isinstance(data, list):
                items_data = data
            else:
                raise ValueError("No news_items found")
        
        for item in items_data:
            try:
                # استخراج البيانات
                title = item.get('title', '').strip()
                content = item.get('content', '').strip()
                category = item.get('category', 'محلي').strip()
                tags = item.get('tags', [])
                
                # التحقق من البيانات الأساسية
                if not title or not content:
                    continue
                
                if len(title) < 5 or len(content) < 30:
                    continue
                
                # تصحيح التصنيف
                if category not in VALID_CATEGORIES:
                    category = self._fix_category(category)
                
                # تنظيف Tags
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(',')]
                
                cleaned_tags = self._clean_tags(tags)
                
                # ربط الصورة
                image_url = None
                image_index = item.get('image_index')
                if image_index and available_images:
                    try:
                        idx = int(image_index) - 1  # 1-based to 0-based
                        if 0 <= idx < len(available_images):
                            image_url = available_images[idx]
                    except:
                        pass
                
                # إنشاء الخبر
                news = ExtractedNews(
                    title=title,
                    content=content,
                    category=category,
                    tags=cleaned_tags,
                    published_date=item.get('published_date'),
                    author=item.get('author'),
                    image_url=image_url
                )
                
                news_items.append(news)
                
            except Exception as e:
                print(f"   ⚠️ Error parsing news item: {str(e)[:50]}")
                continue
        
        return news_items
    
    def _fix_category(self, category: str) -> str:
        """محاولة تصحيح التصنيف"""
        category_lower = category.lower()
        
        mappings = {
            'سياس': 'سياسة',
            'حكوم': 'سياسة',
            'انتخاب': 'سياسة',
            'اقتصاد': 'اقتصاد',
            'مال': 'اقتصاد',
            'تجار': 'اقتصاد',
            'رياض': 'رياضة',
            'كرة': 'رياضة',
            'تقني': 'تكنولوجيا',
            'تكنولوج': 'تكنولوجيا',
            'صح': 'صحة',
            'طب': 'صحة',
            'عسكر': 'عسكري',
            'جيش': 'عسكري',
            'حرب': 'عسكري',
            'ثقاف': 'ثقافة',
            'فن': 'فن',
            'تعليم': 'تعليم',
            'دول': 'دولي',
            'عالم': 'دولي',
        }
        
        for key, value in mappings.items():
            if key in category_lower:
                return value
        
        return 'محلي'  # default
    
    def _clean_tags(self, tags: List) -> List[str]:
        """تنظيف Tags"""
        cleaned = []
        
        for tag in tags[:12]:
            tag = str(tag).strip()
            if not tag:
                continue
            
            # استبدال المسافات
            tag = tag.replace(' ', '_')
            
            # إزالة الرموز
            tag = re.sub(r'[,،.:\'"؟?!]', '', tag)
            
            if len(tag) > 1:
                cleaned.append(tag)
        
        return cleaned


# ============================================
# 🔗 دالة للتكامل مع النظام الموجود
# ============================================

def extract_and_prepare_news(
    content: str,
    source_url: str,
    source_id: int,
    language_id: int = 1,
    available_images: List[str] = None
) -> List[Dict]:
    """
    استخراج الأخبار وتحضيرها للحفظ في raw_news
    
    Args:
        content: المحتوى الخام
        source_url: رابط المصدر
        source_id: ID المصدر في DB
        language_id: ID اللغة
        available_images: قائمة الصور
    
    Returns:
        List[Dict]: قائمة جاهزة للحفظ في raw_news
    """
    extractor = ContentExtractor()
    result = extractor.extract_news(content, source_url, available_images)
    
    if not result.success:
        print(f"   ❌ Extraction failed: {result.error_message}")
        return []
    
    # تحويل للتنسيق المطلوب
    news_list = []
    
    for news in result.news_items:
        news_dict = {
            'title': news.title,
            'content_text': news.content,
            'content_img': news.image_url or '',
            'content_video': '',
            'tags': news.tags_str,
            'source_id': source_id,
            'language_id': language_id,
            'category_id': None,  # سيتم تعيينه لاحقاً
            'category_name': news.category,  # للاستخدام مع get_or_create_category_id
            'published_at': _parse_date(news.published_date),
            'collected_at': datetime.now(timezone.utc)
        }
        
        news_list.append(news_dict)
    
    print(f"   ✅ Extracted {len(news_list)} news items")
    return news_list


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """تحويل string لـ datetime"""
    if not date_str:
        return datetime.now(timezone.utc)
    
    try:
        # محاولة عدة تنسيقات
        formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%d/%m/%Y',
            '%d-%m-%Y',
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except:
                continue
        
        return datetime.now(timezone.utc)
        
    except:
        return datetime.now(timezone.utc)


# ============================================
# 🧪 Test
# ============================================

if __name__ == "__main__":
    # اختبار بسيط
    test_content = """
    عنوان: الحكومة تعلن عن خطة اقتصادية جديدة
    
    أعلنت الحكومة اليوم عن خطة اقتصادية شاملة تهدف إلى تحسين الوضع المعيشي للمواطنين.
    وقال وزير المالية في مؤتمر صحفي إن الخطة تتضمن تخفيضات ضريبية وزيادة في الرواتب.
    
    ---
    
    رياضة: المنتخب الوطني يفوز على نظيره الأردني
    
    حقق المنتخب الوطني لكرة القدم فوزاً مهماً على نظيره الأردني بنتيجة 2-1.
    سجل الأهداف كل من محمد صلاح ويوسف أحمد في الشوط الثاني.
    """
    
    print("=" * 60)
    print("🤖 Content Extractor Test")
    print("=" * 60)
    
    extractor = ContentExtractor()
    result = extractor.extract_news(test_content, "https://example.com")
    
    print(f"\n✅ Success: {result.success}")
    print(f"📰 News Count: {result.total_extracted}")
    
    for i, news in enumerate(result.news_items, 1):
        print(f"\n--- News #{i} ---")
        print(f"📌 Title: {news.title}")
        print(f"📁 Category: {news.category}")
        print(f"🏷️ Tags: {news.tags_str}")
        print(f"📝 Content: {news.content[:100]}...")