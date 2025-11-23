#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔧 Remote Database Setup Script
اختبار الاتصال وإدخال البيانات الأساسية في قاعدة البيانات المستضافة
"""

import psycopg2
import sys
from datetime import datetime

# ========================================
# إعدادات قاعدة البيانات المستضافة
# ========================================
DB_CONFIG = {
    'dbname': 'automation_db_mbly',
    'user': 'automation_db_mbly_user',
    'password': 'i33hAvmcwOmFoo54S4Wlv4cslk14ziha',
    'host': 'dpg-d4co200dl3ps73bk1ufg-a.oregon-postgres.render.com',
    'port': 5432,
    'sslmode': 'require'  # مطلوب للاتصال الخارجي
}


def test_connection():
    """اختبار الاتصال بقاعدة البيانات"""
    print("=" * 70)
    print("🔌 Testing Connection to Remote Database (Render)")
    print("=" * 70)
    print(f"   Host: {DB_CONFIG['host']}")
    print(f"   Database: {DB_CONFIG['dbname']}")
    print(f"   User: {DB_CONFIG['user']}")
    print("-" * 70)
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # اختبار الاتصال
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✅ Connection Successful!")
        print(f"   PostgreSQL Version: {version[:50]}...")
        
        # اختبار الوقت
        cursor.execute("SELECT NOW();")
        server_time = cursor.fetchone()[0]
        print(f"   Server Time: {server_time}")
        
        cursor.close()
        conn.close()
        
        print("-" * 70)
        print("✅ Database connection test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Connection FAILED!")
        print(f"   Error: {e}")
        return False


def insert_initial_data():
    """إدخال البيانات الأساسية"""
    print("\n" + "=" * 70)
    print("📥 Inserting Initial Data")
    print("=" * 70)
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # ========================================
        # SECTION 1: Languages (اللغات)
        # ========================================
        print("\n1️⃣ Inserting Languages...")
        cursor.execute("""
            INSERT INTO language (id, code, name) VALUES
            (1, 'ar', 'العربية'),
            (2, 'en', 'English'),
            (3, 'he', 'עברית'),
            (4, 'fr', 'Français')
            ON CONFLICT (id) DO NOTHING;
        """)
        print(f"   ✅ Languages inserted (affected: {cursor.rowcount})")
        
        # ========================================
        # SECTION 2: Source Types (أنواع المصادر)
        # ========================================
        print("\n2️⃣ Inserting Source Types...")
        cursor.execute("""
            INSERT INTO source_types (id, name, description, created_at, updated_at) VALUES
            (1, 'RSS', 'RSS Feed', NOW(), NOW()),
            (2, 'API', 'REST API', NOW(), NOW()),
            (3, 'HTML Scrape', 'HTML Web Scraping', NOW(), NOW())
            ON CONFLICT (id) DO NOTHING;
        """)
        print(f"   ✅ Source Types inserted (affected: {cursor.rowcount})")
        
        # ========================================
        # SECTION 3: Sources (المصادر)
        # ========================================
        print("\n3️⃣ Inserting Sources...")
        cursor.execute("""
            INSERT INTO sources (id, name, source_type_id, url, is_active, last_fetched, created_at, updated_at) VALUES
            (1, 'PBC', 1, 'https://www.pbc.ps/feed/', true, NULL, NOW(), NOW()),
            (2, 'Arab48', 1, 'https://www.arab48.com/rss', true, NULL, NOW(), NOW()),
            (3, 'Quds Press', 1, 'https://qudspress.com/feed/', true, NULL, NOW(), NOW()),
            (4, 'Al-Sharq', 1, 'https://al-sharq.com/rss/latestNews', true, NULL, NOW(), NOW()),
            (5, 'Palestine Info', 1, 'https://palinfo.com/feed/', true, NULL, NOW(), NOW())
            ON CONFLICT (id) DO NOTHING;
        """)
        print(f"   ✅ Sources inserted (affected: {cursor.rowcount})")
        
        # ========================================
        # SECTION 4: Categories (التصنيفات)
        # ========================================
        print("\n4️⃣ Inserting Categories...")
        cursor.execute("""
            INSERT INTO categories (id, name, created_at, updated_at) VALUES
            (1, 'سياسة', NOW(), NOW()),
            (2, 'اقتصاد', NOW(), NOW()),
            (3, 'رياضة', NOW(), NOW()),
            (4, 'تكنولوجيا', NOW(), NOW()),
            (5, 'صحة', NOW(), NOW()),
            (6, 'ثقافة', NOW(), NOW()),
            (7, 'محلي', NOW(), NOW()),
            (8, 'دولي', NOW(), NOW()),
            (9, 'عسكري', NOW(), NOW()),
            (10, 'اجتماعي', NOW(), NOW()),
            (11, 'فن', NOW(), NOW()),
            (12, 'تعليم', NOW(), NOW()),
            (13, 'أخرى', NOW(), NOW())
            ON CONFLICT (id) DO NOTHING;
        """)
        print(f"   ✅ Categories inserted (affected: {cursor.rowcount})")
        
        # ========================================
        # SECTION 5: Scheduled Tasks (المهام المجدولة)
        # ========================================
        print("\n5️⃣ Inserting Scheduled Tasks...")
        cursor.execute("""
            INSERT INTO scheduled_tasks (id, name, task_type, schedule_pattern, status, next_run_at, created_at) VALUES
            (1, 'News Scraping', 'scraping', '*/10 * * * *', 'active', NOW(), NOW()),
            (2, 'News Clustering', 'clustering', '0 * * * *', 'active', NOW(), NOW()),
            (3, 'Report Generation', 'report_generation', '0 */2 * * *', 'active', NOW(), NOW())
            ON CONFLICT (id) DO NOTHING;
        """)
        print(f"   ✅ Scheduled Tasks inserted (affected: {cursor.rowcount})")
        
        # حفظ التغييرات
        conn.commit()
        
        print("\n" + "-" * 70)
        print("✅ All initial data inserted successfully!")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Error inserting data: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def verify_data():
    """التحقق من البيانات المدخلة"""
    print("\n" + "=" * 70)
    print("🔍 Verifying Inserted Data")
    print("=" * 70)
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # التحقق من اللغات
        cursor.execute("SELECT COUNT(*) FROM language;")
        lang_count = cursor.fetchone()[0]
        print(f"   📌 Languages: {lang_count}")
        
        # التحقق من أنواع المصادر
        cursor.execute("SELECT COUNT(*) FROM source_types;")
        st_count = cursor.fetchone()[0]
        print(f"   📌 Source Types: {st_count}")
        
        # التحقق من المصادر
        cursor.execute("SELECT COUNT(*) FROM sources WHERE is_active = true;")
        src_count = cursor.fetchone()[0]
        print(f"   📌 Active Sources: {src_count}")
        
        # التحقق من التصنيفات
        cursor.execute("SELECT COUNT(*) FROM categories;")
        cat_count = cursor.fetchone()[0]
        print(f"   📌 Categories: {cat_count}")
        
        # التحقق من المهام المجدولة
        cursor.execute("SELECT COUNT(*) FROM scheduled_tasks;")
        task_count = cursor.fetchone()[0]
        print(f"   📌 Scheduled Tasks: {task_count}")
        
        # عرض المصادر النشطة
        print("\n" + "-" * 70)
        print("📰 Active Sources:")
        cursor.execute("""
            SELECT s.name, st.name as type, s.url 
            FROM sources s 
            JOIN source_types st ON s.source_type_id = st.id
            WHERE s.is_active = true
            ORDER BY s.id;
        """)
        for row in cursor.fetchall():
            print(f"   • {row[0]} ({row[1]}): {row[2][:40]}...")
        
        cursor.close()
        conn.close()
        
        print("\n" + "-" * 70)
        print("✅ Data verification completed!")
        return True
        
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False


def main():
    """الدالة الرئيسية"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " 🚀 Remote Database Setup Script ".center(68) + "║")
    print("║" + " Render PostgreSQL Database ".center(68) + "║")
    print("╚" + "═" * 68 + "╝")
    print("\n")
    
    # الخطوة 1: اختبار الاتصال
    if not test_connection():
        print("\n❌ Cannot proceed without database connection!")
        sys.exit(1)
    
    # الخطوة 2: إدخال البيانات
    if not insert_initial_data():
        print("\n❌ Failed to insert initial data!")
        sys.exit(1)
    
    # الخطوة 3: التحقق من البيانات
    if not verify_data():
        print("\n⚠️ Data verification had issues!")
    
    # النهاية
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " 🎉 Setup Completed Successfully! ".center(68) + "║")
    print("╚" + "═" * 68 + "╝")
    print("\n")
    print("📝 Next Steps:")
    print("   1. Copy the updated .env file to your project")
    print("   2. Run: python cron/scraper_job.py")
    print("   3. Run: python cron/clustering_job.py")
    print("   4. Run: python cron/reports_job.py")
    print("\n")


if __name__ == "__main__":
    main()