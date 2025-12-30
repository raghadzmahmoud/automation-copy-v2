#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🗄️ Database Utilities - Updated for New Schema
أدوات قاعدة البيانات - محدّث حسب Schema الجديد
"""

import psycopg2
from datetime import datetime, timezone
from typing import Optional, Dict, List
from settings import DB_CONFIG


def get_db_connection():
    """إنشاء اتصال بقاعدة البيانات"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None


# ============================================
# 🌐 Languages
# ============================================

def get_language_id(language_code: str) -> int:
    """
    الحصول على language ID من الكود
    
    Args:
        language_code: كود اللغة (ar, en, he, fr)
    
    Returns:
        int: language ID (افتراضي 1 للعربية)
    """
    conn = get_db_connection()
    if not conn:
        return 1  # default: Arabic
    
    try:
        cursor = conn.cursor()
        # ✅ تحديث: استخدام `code` بدلاً من `name`
        cursor.execute(
            "SELECT id FROM language WHERE code = %s",
            (language_code,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result[0] if result else 1
        
    except Exception as e:
        print(f"⚠️ Error getting language_id: {e}")
        if conn:
            conn.close()
        return 1


def get_language_name(language_id: int) -> str:
    """الحصول على اسم اللغة من ID"""
    conn = get_db_connection()
    if not conn:
        return 'ar'
    
    try:
        cursor = conn.cursor()
        # ✅ إرجاع `code` للتوافق
        cursor.execute("SELECT code FROM language WHERE id = %s", (language_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result[0] if result else 'ar'
        
    except Exception as e:
        print(f"⚠️ Error getting language code: {e}")
        if conn:
            conn.close()
        return 'ar'


# ============================================
# 📰 Sources
# ============================================

def get_source_id(source_name: str) -> int:
    """
    الحصول على source ID من الاسم
    
    Args:
        source_name: اسم المصدر
    
    Returns:
        int: source ID (0 إذا لم يُعثر عليه)
    """
    conn = get_db_connection()
    if not conn:
        return 0
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM sources WHERE name = %s",
            (source_name,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result[0] if result else 0
        
    except Exception as e:
        print(f"⚠️ Error getting source_id: {e}")
        if conn:
            conn.close()
        return 0


def get_source_last_fetched(source_id: int) -> Optional[datetime]:
    """
    الحصول على آخر وقت تم فيه السحب من المصدر
    
    Args:
        source_id: ID المصدر
    
    Returns:
        datetime: آخر وقت سحب، أو None
    """
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT last_fetched FROM sources WHERE id = %s",
            (source_id,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result and result[0]:
            # تأكد من أن التاريخ UTC
            dt = result[0]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        return None
            
    except Exception as e:
        print(f"⚠️ Error reading last_fetched: {e}")
        if conn:
            conn.close()
        return None


def update_source_last_fetched(source_id: int, timestamp: datetime = None):
    """
    تحديث آخر وقت تم فيه السحب من المصدر
    
    Args:
        source_id: ID المصدر
        timestamp: الوقت الجديد (افتراضياً: الآن UTC)
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE sources 
            SET last_fetched = %s, updated_at = %s
            WHERE id = %s
            """,
            (timestamp, timestamp, source_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
                
    except Exception as e:
        print(f"⚠️ Error updating last_fetched: {e}")
        if conn:
            conn.rollback()
            conn.close()


def get_active_sources() -> List[Dict]:
    """
    ✅ UPDATED: جلب كل المصادر النشطة
    
    Returns:
        List[Dict]: قائمة المصادر مع source_type_id
    """
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        # ✅ تحديث: استخدام الحقول الصحيحة من Schema الجديد
        cursor.execute("""
            SELECT 
                s.id, 
                s.name, 
                s.source_type_id, 
                s.url, 
                s.is_active, 
                s.last_fetched,
                st.name as source_type_name
            FROM sources s
            LEFT JOIN source_types st ON s.source_type_id = st.id
            WHERE s.is_active = true
            ORDER BY s.id
        """)
        
        sources = []
        for row in cursor.fetchall():
            sources.append({
                'id': row[0],
                'name': row[1],
                'source_type_id': row[2],
                'url': row[3],
                'is_active': row[4],
                'last_fetched': row[5],
                'source_type_name': row[6] or 'rss',  # default to 'rss'
                # ✅ Backward compatibility
                'type': row[6] or 'rss',
                'language_id': 1  # default Arabic
            })
        
        cursor.close()
        conn.close()
        return sources
        
    except Exception as e:
        print(f"⚠️ Error getting active sources: {e}")
        if conn:
            conn.close()
        return []


def get_source_type_id(type_name: str) -> int:
    """
    ✅ NEW: الحصول على source_type_id من الاسم
    
    Args:
        type_name: اسم النوع (rss, html, api)
    
    Returns:
        int: source_type_id (0 if not found)
    """
    conn = get_db_connection()
    if not conn:
        return 0
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM source_types WHERE name = %s",
            (type_name,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result[0] if result else 0
        
    except Exception as e:
        print(f"⚠️ Error getting source_type_id: {e}")
        if conn:
            conn.close()
        return 0


# ============================================
# 📑 Categories
# ============================================

def get_or_create_category_id(category_name: str) -> int:
    """
    الحصول على أو إنشاء category ID
    
    Args:
        category_name: اسم التصنيف
    
    Returns:
        int: category ID
    """
    category_name = category_name.strip()
    
    if not category_name or category_name == "uncategorized":
        category_name = "أخرى"
    
    conn = get_db_connection()
    if not conn:
        return 1  # default category
    
    try:
        cursor = conn.cursor()
        
        # محاولة الحصول على الـ category
        cursor.execute(
            "SELECT id FROM categories WHERE name = %s",
            (category_name,)
        )
        result = cursor.fetchone()
        
        if result:
            cursor.close()
            conn.close()
            return result[0]
        
        # إنشاء category جديد
        now = datetime.now(timezone.utc)
        cursor.execute(
            """
            INSERT INTO categories (name, created_at, updated_at)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (category_name, now, now)
        )
        new_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return new_id
        
    except Exception as e:
        print(f"⚠️ Error with category: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return 1


def get_category_name(category_id: int) -> str:
    """الحصول على اسم التصنيف من ID"""
    conn = get_db_connection()
    if not conn:
        return 'أخرى'
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM categories WHERE id = %s", (category_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result[0] if result else 'أخرى'
        
    except Exception as e:
        print(f"⚠️ Error getting category name: {e}")
        if conn:
            conn.close()
        return 'أخرى'


# ============================================
# 📰 News
# ============================================

def save_news_item(news: Dict) -> bool:
    """
    حفظ خبر واحد في قاعدة البيانات
    
    Args:
        news: dictionary يحتوي على بيانات الخبر
    
    Returns:
        bool: True if successful
    """
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # التحقق من عدم وجود خبر مكرر
        cursor.execute("""
            SELECT id FROM raw_news 
            WHERE title = %s AND source_id = %s
            LIMIT 1
        """, (news['title'], news['source_id']))
        
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return False  # موجود مسبقاً
        
        # إدراج الخبر
        insert_query = """
            INSERT INTO raw_news (
                title, content_text, content_img, content_video, 
                tags, source_id, language_id, category_id,
                published_at, collected_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        # ✅ دعم كلا الاسمين
        content_value = news.get('content_text') or news.get('content', '')

        cursor.execute(insert_query, (
            news.get('title'),
            content_value,
            news.get('content_img', ''),
            news.get('content_video', ''),
            news.get('tags', ''),
            news.get('source_id'),
            news.get('language_id', 1),
            news.get('category_id', 1),
            news.get('published_at'),
            news.get('collected_at', datetime.now(timezone.utc))
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"⚠️ Error saving news: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def save_news_batch(news_list: List[Dict]) -> int:
    """
    حفظ دفعة من الأخبار
    
    Returns:
        int: عدد الأخبار المحفوظة
    """
    saved_count = 0
    
    for news in news_list:
        if save_news_item(news):
            saved_count += 1
    
    return saved_count