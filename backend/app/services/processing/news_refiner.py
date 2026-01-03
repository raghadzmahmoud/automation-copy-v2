#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
✨ News Refiner Service
تحويل النص العامي إلى خبر صحفي احترافي
"""

import google.generativeai as genai
from settings import GEMINI_API_KEY, GEMINI_MODEL
from typing import Optional, Dict
import re


class NewsRefiner:
    """
    تحويل الكلام العامي إلى خبر صحفي منمّق
    
    Usage:
        refiner = NewsRefiner()
        result = refiner.refine_to_news("اليوم صار في القدس احتجاجات...")
        # Returns: {'success': True, 'title': '...', 'content': '...'}
    """
    
    def __init__(self):
        """Initialize Gemini AI"""
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel(GEMINI_MODEL)
            print("✅ NewsRefiner initialized")
        except Exception as e:
            print(f"❌ NewsRefiner initialization failed: {e}")
            raise
    
    def refine_to_news(self, raw_text: str, max_retries: int = 3) -> Dict:
        """
        تحويل النص العامي إلى خبر صحفي احترافي
        
        Args:
            raw_text: النص العامي (من تسجيل المستخدم)
            max_retries: عدد المحاولات عند الفشل
        
        Returns:
            {
                'success': True/False,
                'title': 'عنوان الخبر (10-15 كلمة)',
                'content': 'محتوى الخبر (200-300 كلمة)',
                'original_text': 'النص الأصلي',
                'error': 'رسالة الخطأ (لو في)'
            }
        """
        
        if not raw_text or len(raw_text.strip()) < 10:
            return {
                'success': False,
                'error': 'النص قصير جداً (أقل من 10 أحرف)'
            }
        
        # ========================================
        # بناء الـ Prompt
        # ========================================
        prompt = self._build_prompt(raw_text)
        
        # ========================================
        # محاولات الاتصال بالـ AI
        # ========================================
        for attempt in range(max_retries):
            try:
                print(f"🤖 Refining text... (attempt {attempt + 1}/{max_retries})")
                
                # استدعاء Gemini
                response = self.model.generate_content(prompt)
                response_text = response.text.strip()
                
                # استخراج العنوان والمحتوى
                parsed = self._parse_response(response_text)
                
                if parsed['success']:
                    print(f"✅ Refined successfully!")
                    print(f"   Title: {parsed['title'][:50]}...")
                    print(f"   Content: {len(parsed['content'])} characters")
                    
                    return {
                        'success': True,
                        'title': parsed['title'],
                        'content': parsed['content'],
                        'original_text': raw_text
                    }
                else:
                    print(f"⚠️  Parsing failed, retrying...")
                    continue
                    
            except Exception as e:
                print(f"❌ Attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    # آخر محاولة فشلت
                    return {
                        'success': False,
                        'error': str(e),
                        'original_text': raw_text
                    }
                continue
        
        # كل المحاولات فشلت
        return {
            'success': False,
            'error': 'فشل تحويل النص بعد عدة محاولات',
            'original_text': raw_text
        }
    
    def _build_prompt(self, raw_text: str) -> str:
        """
        بناء الـ prompt للـ AI
        
        المطلوب من AI:
        1. تحويل الكلام العامي → فصحى
        2. إضافة تفاصيل صحفية
        3. تنسيق احترافي
        """
        
        prompt = f"""أنت محرر أخبار محترف. مهمتك تحويل النص العامي التالي إلى خبر صحفي احترافي.

النص الأصلي (عامي):
{raw_text}

المطلوب:
1. **العنوان**: عنوان جذاب وواضح (10-15 كلمة)
2. **المحتوى**: خبر صحفي احترافي  يتضمن:
   - مقدمة قوية
   - تفاصيل الحدث
   - سياق وخلفية
   - أسلوب صحفي رسمي

قواعد مهمة:
- استخدم الفصحى (بدون عامية)
- أسلوب صحفي محايد
- معلومات واقعية (بدون مبالغة) فقط من محتوى الخبر المُدخل بدون أي اضافة خارجية

صيغة الإجابة (التزم بها تماماً):
[العنوان]
عنوان الخبر هنا

[المحتوى]
محتوى الخبر هنا...
"""
        
        return prompt
    
    def _parse_response(self, response_text: str) -> Dict:
        """
        استخراج العنوان والمحتوى من response الـ AI
        
        Expected format:
        [العنوان]
        title here
        
        [المحتوى]
        content here
        """
        
        try:
            # Pattern 1: مع تاقات [العنوان] و [المحتوى]
            title_match = re.search(r'\[العنوان\]\s*\n\s*(.+?)(?:\n|$)', response_text, re.DOTALL)
            content_match = re.search(r'\[المحتوى\]\s*\n\s*(.+)', response_text, re.DOTALL)
            
            if title_match and content_match:
                title = title_match.group(1).strip()
                content = content_match.group(1).strip()
                
                # تنظيف
                title = self._clean_text(title)
                content = self._clean_text(content)
                
                # Validation
                if len(title) > 10 and len(content) > 50:
                    return {
                        'success': True,
                        'title': title,
                        'content': content
                    }
            
            # Pattern 2: لو AI ما التزم بالصيغة
            # نحاول نقسم النص: أول سطر = عنوان، الباقي = محتوى
            lines = response_text.strip().split('\n')
            if len(lines) >= 3:
                # أول سطر غير فارغ = عنوان
                title = None
                content_start = 0
                
                for i, line in enumerate(lines):
                    cleaned = line.strip()
                    if cleaned and not cleaned.startswith('['):
                        if title is None:
                            title = cleaned
                            content_start = i + 1
                        else:
                            # وجدنا العنوان، الباقي محتوى
                            break
                
                if title and content_start < len(lines):
                    content = '\n'.join(lines[content_start:]).strip()
                    content = self._clean_text(content)
                    
                    if len(title) > 10 and len(content) > 50:
                        return {
                            'success': True,
                            'title': title,
                            'content': content
                        }
            
            # فشل الاستخراج
            return {
                'success': False,
                'error': 'لم يتم العثور على العنوان والمحتوى'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'خطأ في استخراج النص: {str(e)}'
            }
    
    def _clean_text(self, text: str) -> str:
        """تنظيف النص من الرموز والمسافات الزائدة"""
        # إزالة markdown
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **bold**
        text = re.sub(r'\*(.+?)\*', r'\1', text)      # *italic*
        
        # إزالة تاقات
        text = re.sub(r'\[.+?\]', '', text)
        
        # إزالة مسافات زائدة
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text


# ============================================
# 🧪 Testing Function
# ============================================

def test_refiner():
    """Test the NewsRefiner"""
    print("\n" + "=" * 50)
    print("🧪 TESTING NEWS REFINER")
    print("=" * 50)
    
    refiner = NewsRefiner()
    
    # Test cases
    test_texts = [
        "اليوم صار في القدس احتجاجات كتير ناس نزلوا بسبب القرار الجديد",
        "سمعت إنه في حادث سير كبير على الطريق السريع وفي ناس انجرحوا",
        "الحكومة قررت تخفض الضرائب على المواطنين من الشهر الجاي"
    ]
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n{'=' * 50}")
        print(f"Test {i}")
        print(f"{'=' * 50}")
        print(f"📝 Original: {text}")
        
        result = refiner.refine_to_news(text)
        
        if result['success']:
            print(f"\n✅ Success!")
            print(f"📰 Title: {result['title']}")
            print(f"📄 Content:\n{result['content']}...")
        else:
            print(f"\n❌ Failed: {result.get('error')}")


if __name__ == "__main__":
    test_refiner()