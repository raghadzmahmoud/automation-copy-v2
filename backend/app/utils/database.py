#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🗄️ Database Utilities - Updated for New Schema
أدوات قاعدة البيانات - محدّث حسب Schema الجديد

📊 Source Types (from source_types table):
   - جدول source_types هو المرجع
   - الكود يجلب الـ ID بالاسم
"""

import psycopg2
from datetime import datetime, timezone
from typing import Optional, Dict, List, Set
from urllib.parse import urlparse
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
        return 1
    
    try:
        cursor = conn.cursor()
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
# 📰 Source Types (from Database)
# ============================================

def get_source_type_id(type_name: str) -> int:
    """
    ✅ جلب source_type_id من جدول source_types
    
    Args:
        type_name: اسم النوع ("RSS", "URL Scrape", "Telegram", "API", "Manual")
    
    Returns:
        int: الـ ID من الـ Database
    
    Example:
        rss_id = get_source_type_id("RSS")           # يجلب ID الـ RSS
        url_id = get_source_type_id("URL Scrape")    # يجلب ID الـ URL Scrape
    """
    conn = get_db_connection()
    if not conn:
        print(f"⚠️ Cannot get source_type_id, DB not connected")
        return 3  # default
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM source_types 
            WHERE LOWER(name) = LOWER(%s)
            LIMIT 1
        """, (type_name,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return result[0]
        else:
            print(f"⚠️ Source type '{type_name}' not found in database")
            return 3  # default: URL Scrape
            
    except Exception as e:
        print(f"⚠️ Error getting source_type_id: {e}")
        if conn:
            conn.close()
        return 3


def get_source_type_name(source_type_id: int) -> str:
    """
    الحصول على اسم نوع المصدر من ID
    """
    conn = get_db_connection()
    if not conn:
        return 'URL Scrape'
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM source_types WHERE id = %s",
            (source_type_id,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result[0] if result else 'URL Scrape'
        
    except Exception as e:
        print(f"⚠️ Error getting source_type_name: {e}")
        if conn:
            conn.close()
        return 'URL Scrape'


def get_all_source_types() -> Dict[str, int]:
    """
    جلب كل أنواع المصادر من الـ Database
    
    Returns:
        Dict: {"RSS": 1, "URL Scrape": 3, ...}
    """
    conn = get_db_connection()
    if not conn:
        return {}
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name, id FROM source_types")
        
        types = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.close()
        conn.close()
        return types
        
    except Exception as e:
        print(f"⚠️ Error getting source types: {e}")
        if conn:
            conn.close()
        return {}


# ============================================
# 📰 Sources
# ============================================

def get_source_id(source_name: str) -> int:
    """
    الحصول على source ID من الاسم
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


def get_source_by_url(url: str) -> Optional[Dict]:
    """
    ✅ البحث عن مصدر بالـ URL
    """
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, source_type_id, url, is_active, last_fetched
            FROM sources 
            WHERE url = %s
        """, (url,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return {
                'id': result[0],
                'name': result[1],
                'source_type_id': result[2],
                'url': result[3],
                'is_active': result[4],
                'last_fetched': result[5]
            }
        return None
        
    except Exception as e:
        print(f"⚠️ Error getting source by url: {e}")
        if conn:
            conn.close()
        return None


def get_source_by_domain(domain: str) -> Optional[Dict]:
    """
    ✅ البحث عن مصدر بالـ Domain
    """
    domain = domain.replace('www.', '').lower()
    
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, source_type_id, url, is_active, last_fetched
            FROM sources 
            WHERE LOWER(name) = %s OR url LIKE %s
            LIMIT 1
        """, (domain, f'%{domain}%'))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return {
                'id': result[0],
                'name': result[1],
                'source_type_id': result[2],
                'url': result[3],
                'is_active': result[4],
                'last_fetched': result[5]
            }
        return None
        
    except Exception as e:
        print(f"⚠️ Error getting source by domain: {e}")
        if conn:
            conn.close()
        return None


def get_or_create_source(
    source_url: str, 
    source_type_id: int = None,
    source_name: str = None
) -> int:
    """
    ✅ الحصول على أو إنشاء مصدر (بدون تكرار)
    
    Args:
        source_url: رابط المصدر (RSS feed أو الموقع)
        source_type_id: ID نوع المصدر (يجلب من get_source_type_id)
        source_name: اسم المصدر (اختياري)
    
    Returns:
        int: source_id
    """
    # استخراج الدومين
    try:
        parsed = urlparse(source_url)
        domain = parsed.netloc.replace('www.', '').lower()
        
        if not source_name:
            source_name = domain
    except:
        domain = source_url
        source_name = source_url
    
    # Default source_type_id
    if source_type_id is None:
        source_type_id = get_source_type_id("URL Scrape")
    
    conn = get_db_connection()
    if not conn:
        return 0
    
    try:
        cursor = conn.cursor()
        
        # 1️⃣ البحث بالـ URL الكامل
        cursor.execute(
            "SELECT id FROM sources WHERE url = %s",
            (source_url,)
        )
        result = cursor.fetchone()
        
        if result:
            print(f"   ✅ Found existing source by URL: ID={result[0]}")
            cursor.close()
            conn.close()
            return result[0]
        
        # 2️⃣ البحث بالـ Domain/Name
        cursor.execute(
            "SELECT id FROM sources WHERE LOWER(name) = %s",
            (domain,)
        )
        result = cursor.fetchone()
        
        if result:
            print(f"   ✅ Found existing source by domain: ID={result[0]}")
            cursor.execute(
                "UPDATE sources SET url = %s, updated_at = %s WHERE id = %s",
                (source_url, datetime.now(timezone.utc), result[0])
            )
            conn.commit()
            cursor.close()
            conn.close()
            return result[0]
        
        # 3️⃣ إنشاء مصدر جديد
        now = datetime.now(timezone.utc)
        cursor.execute(
            """
            INSERT INTO sources (name, url, source_type_id, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, true, %s, %s)
            RETURNING id
            """,
            (source_name, source_url, source_type_id, now, now)
        )
        new_id = cursor.fetchone()[0]
        conn.commit()
        
        print(f"   ✅ Created new source: ID={new_id}, Type ID={source_type_id}")
        
        cursor.close()
        conn.close()
        return new_id
        
    except Exception as e:
        print(f"⚠️ Error with source: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return 0


def get_source_last_fetched(source_id: int) -> Optional[datetime]:
    """
    الحصول على آخر وقت تم فيه السحب من المصدر
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


def get_active_sources(source_type_id: int = None) -> List[Dict]:
    """
    ✅ جلب المصادر النشطة
    
    Args:
        source_type_id: فلتر بنوع المصدر (اختياري)
    """
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        
        query = """
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
        """
        
        params = []
        if source_type_id:
            query += " AND s.source_type_id = %s"
            params.append(source_type_id)
        
        query += " ORDER BY s.id"
        
        cursor.execute(query, params)
        
        sources = []
        for row in cursor.fetchall():
            sources.append({
                'id': row[0],
                'name': row[1],
                'source_type_id': row[2],
                'url': row[3],
                'is_active': row[4],
                'last_fetched': row[5],
                'source_type_name': row[6] or 'URL Scrape',
                'type': row[6] or 'URL Scrape',
                'language_id': 1
            })
        
        cursor.close()
        conn.close()
        return sources
        
    except Exception as e:
        print(f"⚠️ Error getting active sources: {e}")
        if conn:
            conn.close()
        return []


# ============================================
# 📑 Categories
# ============================================

def get_or_create_category_id(category_name: str) -> int:
    """
    الحصول على أو إنشاء category ID
    """
    category_name = category_name.strip() if category_name else "أخرى"
    
    if not category_name or category_name == "uncategorized":
        category_name = "أخرى"
    
    conn = get_db_connection()
    if not conn:
        return 1
    
    try:
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id FROM categories WHERE name = %s",
            (category_name,)
        )
        result = cursor.fetchone()
        
        if result:
            cursor.close()
            conn.close()
            return result[0]
        
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
# 📥 Input Methods
# ============================================

def get_input_method_id(method_name: str = "scraper") -> int:
    """
    ✅ الحصول على input_method_id
    
    Args:
        method_name: اسم الطريقة (manual, rss, api, scraper)
    """
    conn = get_db_connection()
    if not conn:
        return 1
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM input_methods WHERE LOWER(name) = LOWER(%s)",
            (method_name,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result[0] if result else 1
        
    except Exception as e:
        print(f"⚠️ Error getting input_method_id: {e}")
        if conn:
            conn.close()
        return 1


# ============================================
# 🔍 Deduplication - جلب آخر 100 خبر
# ============================================

def get_recent_news_titles(source_id: int, limit: int = 100) -> Set[str]:
    """
    جلب عناوين آخر الأخبار من مصدر معين
    
    Args:
        source_id: ID المصدر
        limit: عدد الأخبار (افتراضي 100)
    
    Returns:
        set: مجموعة العناوين
    """
    conn = get_db_connection()
    if not conn:
        return set()
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title FROM raw_news
            WHERE source_id = %s
            ORDER BY collected_at DESC
            LIMIT %s
        """, (source_id, limit))
        
        titles = {row[0] for row in cursor.fetchall()}
        
        cursor.close()
        conn.close()
        return titles
        
    except Exception as e:
        print(f"⚠️ Error getting recent titles: {e}")
        if conn:
            conn.close()
        return set()


def get_all_recent_titles(limit: int = 100) -> Set[str]:
    """
    جلب عناوين آخر الأخبار من كل المصادر
    """
    conn = get_db_connection()
    if not conn:
        return set()
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title FROM raw_news
            ORDER BY collected_at DESC
            LIMIT %s
        """, (limit,))
        
        titles = {row[0] for row in cursor.fetchall()}
        
        cursor.close()
        conn.close()
        return titles
        
    except Exception as e:
        print(f"⚠️ Error getting all recent titles: {e}")
        if conn:
            conn.close()
        return set()


# ============================================
# 📰 News - Save (مع source_type_id)
# ============================================

def save_news_item(news: Dict, existing_titles: Set[str] = None) -> bool:
    """
    ✅ حفظ خبر في raw_news
    
    Required fields:
        - title: عنوان الخبر
        - source_id: ID المصدر (من جدول sources)
        - source_type_id: نوع المصدر (يجلب من get_source_type_id)
        - source_url: رابط الخبر نفسه ✅
    
    Args:
        news: بيانات الخبر
        existing_titles: مجموعة العناوين الموجودة (للتحقق السريع)
    """
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        
        title = news.get("title", "").strip()
        source_id = news.get("source_id")
        source_type_id = news.get("source_type_id")  # ✅ نوع المصدر
        source_url = news.get("source_url", "")      # ✅ رابط الخبر
        
        # التحقق من البيانات الأساسية
        if not title or not source_id:
            print(f"   ⚠️ Skip: Missing title or source_id")
            cursor.close()
            conn.close()
            return False

        # ----------------------------------
        # 🛑 Deduplication
        # ----------------------------------
        if existing_titles is not None:
            if title in existing_titles:
                print(f"   ⏭️ Skip (exists): {title[:50]}...")
                cursor.close()
                conn.close()
                return False
        else:
            cursor.execute("""
                SELECT id FROM raw_news
                WHERE title = %s AND source_id = %s
                LIMIT 1
            """, (title, source_id))
            
            if cursor.fetchone():
                print(f"   ⏭️ Skip (duplicate): {title[:50]}...")
                cursor.close()
                conn.close()
                return False

        # ----------------------------------
        # 🧾 Insert (مع source_type_id)
        # ----------------------------------
        insert_query = """
            INSERT INTO raw_news (
                title,
                content_text,
                content_img,
                content_video,
                tags,
                source_id,
                source_type_id,
                language_id,
                category_id,
                source_url,
                uploaded_file_id,
                original_text,
                metadata,
                published_at,
                collected_at
            ) VALUES (
                %(title)s,
                %(content_text)s,
                %(content_img)s,
                %(content_video)s,
                %(tags)s,
                %(source_id)s,
                %(source_type_id)s,
                %(language_id)s,
                %(category_id)s,
                %(source_url)s,
                %(uploaded_file_id)s,
                %(original_text)s,
                %(metadata)s,
                %(published_at)s,
                %(collected_at)s
            )
        """

        payload = {
            "title": title,
            "content_text": news.get("content_text") or news.get("content", ""),
            "content_img": news.get("content_img"),
            "content_video": news.get("content_video"),
            "tags": news.get("tags"),
            "source_id": source_id,
            "source_type_id": source_type_id,
            "language_id": news.get("language_id", 1),
            "category_id": news.get("category_id", 1),
            "source_url": source_url or None,
            "uploaded_file_id": news.get("uploaded_file_id"),
            "original_text": news.get("original_text"),
            "metadata": news.get("metadata"),
            "published_at": news.get("published_at"),
            "collected_at": news.get("collected_at", datetime.now(timezone.utc)),
        }

        cursor.execute(insert_query, payload)
        conn.commit()

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error saving raw_news: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def save_news_batch(news_list: List[Dict], source_id: int = None) -> int:
    """
    ✅ حفظ مجموعة أخبار مع Deduplication محسّن
    
    يجلب آخر 100 خبر مرة واحدة ثم يفحص كل خبر
    """
    if not news_list:
        return 0
    
    # جلب آخر 100 خبر من المصدر (مرة واحدة فقط)
    if source_id:
        existing_titles = get_recent_news_titles(source_id, limit=100)
    else:
        existing_titles = get_all_recent_titles(limit=100)
    
    print(f"   📋 Loaded {len(existing_titles)} existing titles for deduplication")
    
    saved_count = 0
    skipped_count = 0
    
    for news in news_list:
        title = news.get("title", "").strip()
        
        # التحقق السريع من المجموعة
        if title in existing_titles:
            print(f"   ⏭️ Skip: {title[:50]}...")
            skipped_count += 1
            continue
        
        # محاولة الحفظ
        if save_news_item(news, existing_titles):
            saved_count += 1
            existing_titles.add(title)
        else:
            skipped_count += 1
    
    print(f"   📊 Results: Saved={saved_count}, Skipped={skipped_count}")
    return saved_count


def check_news_exists(title: str, source_id: int) -> bool:
    """
    التحقق من وجود خبر
    """
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM raw_news
            WHERE title = %s AND source_id = %s
            LIMIT 1
        """, (title, source_id))
        
        exists = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        
        return exists
        
    except Exception as e:
        print(f"⚠️ Error checking news: {e}")
        if conn:
            conn.close()
        return False


def check_news_exists_by_url(source_url: str) -> bool:
    """
    التحقق من وجود خبر بالـ URL
    """
    if not source_url:
        return False
    
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM raw_news
            WHERE source_url = %s
            LIMIT 1
        """, (source_url,))
        
        exists = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        
        return exists
        
    except Exception as e:
        print(f"⚠️ Error checking news by url: {e}")
        if conn:
            conn.close()
        return False