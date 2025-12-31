#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📝 Manual Input Service - معالجة الإدخال اليدوي للأخبار
يستقبل نص خام من المستخدم، يعالجه بـ AI، ويحفظه في raw_news

Path: backend/app/services/ingestion/manual_input.py
"""

import os
import sys
import re
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

import psycopg2
from google import genai

# ============================================
# Configuration (from environment)
# ============================================

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

DB_CONFIG = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 5432))
}

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')


# ============================================
# Data Classes
# ============================================

@dataclass
class ProcessedNews:
    """بيانات الخبر المُعالج"""
    title: str
    content: str
    category: str
    tags: list
    original_text: str
    success: bool = True
    error_message: str = ""


@dataclass 
class SaveResult:
    """نتيجة حفظ الخبر"""
    success: bool
    news_id: Optional[int] = None
    message: str = ""


# ============================================
# Valid Categories (must match DB)
# ============================================

VALID_CATEGORIES = [
    'سياسة',      # Politics
    'اقتصاد',     # Economy
    'رياضة',      # Sports
    'تكنولوجيا',  # Technology
    'صحة',        # Health
    'ثقافة',      # Culture
    'محلي',       # Local
    'دولي',       # International
    'عسكري',      # Military
    'اجتماعي',    # Social
    'فن',         # Art
    'تعليم',      # Education
    'أخرى'        # Other
]


# ============================================
# Manual Input Processor
# ============================================

class ManualInputProcessor:
    """
    معالج الإدخال اليدوي للأخبار
    
    يقوم بـ:
    1. استقبال نص خام من المستخدم
    2. معالجته بـ AI (ترتيب، عنوان، فصحى، تصنيف)
    3. حفظه في raw_news مع input_method_id = 5
    """
    
    # Manual Entry input_method_id from database
    INPUT_METHOD_ID = 5  # manual_entry
    
    def __init__(self):
        """تهيئة المعالج"""
        self.conn = None
        self.cursor = None
        self.client = None
        
        # اتصال بقاعدة البيانات
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print("✅ Database connection established")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise
        
        # تهيئة Gemini
        try:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
            print(f"✅ Gemini client ready (Model: {GEMINI_MODEL})")
        except Exception as e:
            print(f"❌ Gemini client failed: {e}")
            raise
    
    def process_and_save(self, raw_text: str, source_id: Optional[int] = None) -> SaveResult:
        """
        معالجة النص الخام وحفظه في قاعدة البيانات
        
        Args:
            raw_text: النص الخام من المستخدم
            source_id: معرف المصدر (اختياري، افتراضي None للإدخال اليدوي)
        
        Returns:
            SaveResult: نتيجة الحفظ
        """
        print("\n" + "="*60)
        print("📝 Processing Manual Input")
        print("="*60)
        
        # التحقق من النص
        if not raw_text or len(raw_text.strip()) < 20:
            return SaveResult(
                success=False,
                message="النص قصير جداً (يجب أن يكون 20 حرف على الأقل)"
            )
        
        # معالجة النص بـ AI
        processed = self._process_with_ai(raw_text)
        
        if not processed.success:
            return SaveResult(
                success=False,
                message=f"فشل في معالجة النص: {processed.error_message}"
            )
        
        # الحصول على category_id
        category_id = self._get_or_create_category(processed.category)
        
        # حفظ في قاعدة البيانات
        result = self._save_to_database(
            processed=processed,
            category_id=category_id,
            source_id=source_id
        )
        
        return result
    
    def _process_with_ai(self, raw_text: str, max_retries: int = 3) -> ProcessedNews:
        """
        معالجة النص بواسطة AI
        
        يقوم بـ:
        - إنشاء عنوان مناسب
        - تحويل النص للعربية الفصحى
        - ترتيب وتنظيم المحتوى
        - تصنيف الخبر
        - استخراج الوسوم
        """
        print(f"🤖 Processing with AI...")
        print(f"   📄 Original length: {len(raw_text)} chars")
        
        prompt = self._build_processing_prompt(raw_text)
        
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config={
                        'temperature': 0.3,  # Lower for more consistent output
                        'max_output_tokens': 2048
                    }
                )
                
                result_text = response.text.strip()
                
                # تحليل الرد
                parsed = self._parse_ai_response(result_text, raw_text)
                
                if parsed.success:
                    print(f"   ✅ Processed successfully")
                    print(f"   📌 Title: {parsed.title[:50]}...")
                    print(f"   📁 Category: {parsed.category}")
                    print(f"   🏷️ Tags: {', '.join(parsed.tags[:5])}")
                    return parsed
                else:
                    print(f"   ⚠️ Parse failed, attempt {attempt + 1}/{max_retries}")
                    time.sleep(1)
                    
            except Exception as e:
                print(f"   ⚠️ Error: {str(e)[:100]}, attempt {attempt + 1}/{max_retries}")
                time.sleep(2)
        
        # Fallback: استخدام النص الأصلي مع معالجة بسيطة
        return self._fallback_processing(raw_text)
    
    def _build_processing_prompt(self, raw_text: str) -> str:
        """بناء prompt المعالجة"""
        
        categories_str = "، ".join(VALID_CATEGORIES[:-1])  # exclude 'أخرى'
        
        prompt = f"""أنت محرر أخبار فلسطيني محترف. قم بمعالجة النص التالي وتحويله لخبر صحفي احترافي.

═══════════════════════════════════════
النص الأصلي:
═══════════════════════════════════════
{raw_text}

═══════════════════════════════════════
المطلوب منك:
═══════════════════════════════════════

1. **العنوان**: اكتب عنوان خبري جذاب (10-15 كلمة)
   - يجب أن يكون واضح ومباشر
   - يبدأ بفعل أو اسم فاعل

2. **المحتوى**: أعد صياغة النص بـ:
   - العربية الفصحى الواضحة
   - أسلوب صحفي احترافي
   - ترتيب منطقي للأفكار
   - فقرات منظمة
   - لا تضف معلومات غير موجودة في الأصل

3. **التصنيف**: اختر تصنيف واحد فقط من:
   {categories_str}

4. **الوسوم**: استخرج 3-5 وسوم (كلمات مفتاحية)

═══════════════════════════════════════
اكتب الرد بهذا الشكل بالضبط:
═══════════════════════════════════════

[العنوان]
اكتب العنوان هنا

[المحتوى]
اكتب المحتوى المُعاد صياغته هنا

[التصنيف]
اكتب التصنيف هنا

[الوسوم]
وسم1، وسم2، وسم3
"""
        return prompt
    
    def _parse_ai_response(self, response: str, original_text: str) -> ProcessedNews:
        """تحليل رد AI واستخراج البيانات"""
        
        try:
            # استخراج العنوان
            title_match = re.search(r'\[العنوان\][:\s]*(.+?)(?=\[المحتوى\])', response, re.DOTALL)
            title = title_match.group(1).strip() if title_match else ""
            
            # استخراج المحتوى
            content_match = re.search(r'\[المحتوى\][:\s]*(.+?)(?=\[التصنيف\])', response, re.DOTALL)
            content = content_match.group(1).strip() if content_match else ""
            
            # استخراج التصنيف
            category_match = re.search(r'\[التصنيف\][:\s]*(.+?)(?=\[الوسوم\])', response, re.DOTALL)
            category = category_match.group(1).strip() if category_match else "أخرى"
            
            # استخراج الوسوم
            tags_match = re.search(r'\[الوسوم\][:\s]*(.+?)$', response, re.DOTALL)
            tags_str = tags_match.group(1).strip() if tags_match else ""
            tags = [t.strip() for t in re.split(r'[،,]', tags_str) if t.strip()]
            
            # تنظيف
            title = self._clean_text(title)
            content = self._clean_text(content)
            category = self._normalize_category(category)
            
            # التحقق من الصحة
            if not title or len(title) < 10:
                return ProcessedNews(
                    title="", content="", category="", tags=[],
                    original_text=original_text,
                    success=False, error_message="العنوان قصير أو غير موجود"
                )
            
            if not content or len(content) < 50:
                return ProcessedNews(
                    title="", content="", category="", tags=[],
                    original_text=original_text,
                    success=False, error_message="المحتوى قصير أو غير موجود"
                )
            
            return ProcessedNews(
                title=title,
                content=content,
                category=category,
                tags=tags[:5],  # Max 5 tags
                original_text=original_text,
                success=True
            )
            
        except Exception as e:
            return ProcessedNews(
                title="", content="", category="", tags=[],
                original_text=original_text,
                success=False, error_message=str(e)
            )
    
    def _fallback_processing(self, raw_text: str) -> ProcessedNews:
        """معالجة احتياطية في حالة فشل AI"""
        print("   ⚠️ Using fallback processing")
        
        # استخراج أول جملة كعنوان
        sentences = re.split(r'[.،؟!]', raw_text)
        title = sentences[0].strip()[:100] if sentences else raw_text[:100]
        
        # تنظيف العنوان
        title = re.sub(r'^\s*[-–—•]\s*', '', title)
        
        if len(title) < 10:
            title = raw_text[:100].strip()
        
        return ProcessedNews(
            title=title,
            content=raw_text.strip(),
            category="أخرى",
            tags=[],
            original_text=raw_text,
            success=True
        )
    
    def _clean_text(self, text: str) -> str:
        """تنظيف النص"""
        if not text:
            return ""
        
        # إزالة markdown
        text = re.sub(r'\*\*|\*|__|_', '', text)
        text = re.sub(r'#+\s*', '', text)
        
        # إزالة أقواس زائدة
        text = re.sub(r'\[|\]', '', text)
        
        # تنظيف المسافات
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        
        return text.strip()
    
    def _normalize_category(self, category: str) -> str:
        """تطبيع التصنيف ليطابق القائمة"""
        category = category.strip()
        
        # البحث عن تطابق مباشر
        if category in VALID_CATEGORIES:
            return category
        
        # البحث عن تطابق جزئي
        for valid_cat in VALID_CATEGORIES:
            if valid_cat in category or category in valid_cat:
                return valid_cat
        
        return "أخرى"
    
    def _get_or_create_category(self, category_name: str) -> int:
        """الحصول على أو إنشاء category_id"""
        try:
            # محاولة الحصول على الـ category
            self.cursor.execute(
                "SELECT id FROM categories WHERE name = %s",
                (category_name,)
            )
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
            
            # إنشاء category جديد
            now = datetime.now(timezone.utc)
            self.cursor.execute(
                """
                INSERT INTO categories (name, created_at, updated_at)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (category_name, now, now)
            )
            new_id = self.cursor.fetchone()[0]
            self.conn.commit()
            
            print(f"   📁 Created new category: {category_name} (id={new_id})")
            return new_id
            
        except Exception as e:
            print(f"   ⚠️ Error with category: {e}")
            self.conn.rollback()
            return 1  # default category
    
    def _save_to_database(
        self, 
        processed: ProcessedNews, 
        category_id: int,
        source_id: Optional[int] = None
    ) -> SaveResult:
        """حفظ الخبر في قاعدة البيانات"""
        
        try:
            now = datetime.now(timezone.utc)
            tags_str = "، ".join(processed.tags) if processed.tags else ""
            
            # التحقق من التكرار
            self.cursor.execute(
                """
                SELECT id FROM raw_news 
                WHERE title = %s 
                LIMIT 1
                """,
                (processed.title,)
            )
            
            existing = self.cursor.fetchone()
            if existing:
                return SaveResult(
                    success=False,
                    news_id=existing[0],
                    message="الخبر موجود مسبقاً"
                )
            
            # إدراج الخبر الجديد
            self.cursor.execute(
                """
                INSERT INTO raw_news (
                    title, 
                    content_text, 
                    tags,
                    source_id,
                    language_id,
                    category_id,
                    input_method_id,
                    original_text,
                    metadata,
                    published_at,
                    collected_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    processed.title,
                    processed.content,
                    tags_str,
                    source_id,  # NULL for manual entry
                    1,  # language_id = 1 (Arabic)
                    category_id,
                    self.INPUT_METHOD_ID,  # 5 = manual_entry
                    processed.original_text,
                    '{}',  # metadata as empty JSON
                    now,  # published_at
                    now   # collected_at
                )
            )
            
            news_id = self.cursor.fetchone()[0]
            self.conn.commit()
            
            print(f"   💾 Saved to database with ID: {news_id}")
            
            return SaveResult(
                success=True,
                news_id=news_id,
                message=f"تم حفظ الخبر بنجاح (ID: {news_id})"
            )
            
        except Exception as e:
            self.conn.rollback()
            print(f"   ❌ Database error: {e}")
            return SaveResult(
                success=False,
                message=f"خطأ في قاعدة البيانات: {str(e)}"
            )
    
    def close(self):
        """إغلاق الاتصالات"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("🔒 Connections closed")


# ============================================
# Standalone Function (for easy import)
# ============================================

def process_manual_input(raw_text: str, source_id: Optional[int] = None) -> SaveResult:
    """
    دالة مستقلة لمعالجة الإدخال اليدوي
    
    Usage:
        from app.services.ingestion.manual_input import process_manual_input
        
        result = process_manual_input("نص الخبر هنا...")
        if result.success:
            print(f"تم الحفظ: {result.news_id}")
    """
    processor = ManualInputProcessor()
    try:
        return processor.process_and_save(raw_text, source_id)
    finally:
        processor.close()


# ============================================
# Test Section
# ============================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🧪 TESTING Manual Input Processor")
    print("="*70)
    
    # نص تجريبي (يمكن أن يكون بالعامية أو غير منظم)
    test_texts = [
        # اختبار 1: نص بالعامية الفلسطينية
        """
        مرحبا كيفكم 
        اليوم صار اشي كتير مهم بغزة، الاحتلال قصف عدة مناطق وفي شهداء وجرحى
        الناس خايفين كتير والمستشفيات مليانة
        الوضع صعب جدا والمساعدات مش واصلة
        """,
        
        # اختبار 2: نص أخباري غير منظم
        """
        افتتح رئيس الوزراء محمد مصطفى اليوم مشروع جديد في رام الله 
        المشروع بتكلفة 5 مليون دولار وبيوفر فرص عمل لـ 200 شخص
        حضر الافتتاح عدد من الوزراء والمسؤولين
        المشروع في مجال التكنولوجيا
        """,
        
        # اختبار 3: خبر رياضي قصير
        """
        فاز نادي هلال القدس على شباب الخليل 2-1 في مباراة مثيرة ضمن دوري المحترفين
        سجل الأهداف اللاعب أحمد وياسر
        """
    ]
    
    # اختبار واحد فقط (الأول)
    print("\n📝 Test 1: Processing Palestinian dialect text")
    print("-" * 50)
    
    processor = ManualInputProcessor()
    
    try:
        result = processor.process_and_save(test_texts[0])
        
        print("\n" + "="*50)
        print("📊 RESULT:")
        print("="*50)
        print(f"Success: {result.success}")
        print(f"News ID: {result.news_id}")
        print(f"Message: {result.message}")
        
        # إذا نجح، نجلب الخبر من قاعدة البيانات للتحقق
        if result.success and result.news_id:
            print("\n📰 Verifying saved news:")
            processor.cursor.execute(
                """
                SELECT id, title, content_text, category_id, input_method_id, tags
                FROM raw_news WHERE id = %s
                """,
                (result.news_id,)
            )
            row = processor.cursor.fetchone()
            if row:
                print(f"   ID: {row[0]}")
                print(f"   Title: {row[1]}")
                print(f"   Content: {row[2][:100]}...")
                print(f"   Category ID: {row[3]}")
                print(f"   Input Method ID: {row[4]}")
                print(f"   Tags: {row[5]}")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        processor.close()
    
    print("\n" + "="*70)
    print("✅ Test completed!")
    print("="*70)