#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔧 Setup Scheduled Tasks
تنظيف وإضافة جميع المهام المجدولة
"""
import psycopg2
from datetime import datetime
from settings import DB_CONFIG


def setup_scheduled_tasks():
    """تنظيف وإضافة جميع المهام المجدولة"""
    
    print("=" * 70)
    print("🔧 Setting up Scheduled Tasks")
    print("=" * 70)
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print("✅ Connected to database")
        
        # 1️⃣ حذف البيانات القديمة
        print("\n🗑️  Cleaning old data...")
        
        # حذف الـ logs أولاً (بسبب FK)
        cursor.execute("DELETE FROM scheduled_task_logs")
        logs_deleted = cursor.rowcount
        print(f"   ✓ Deleted {logs_deleted} task logs")
        
        # حذف الـ tasks
        cursor.execute("DELETE FROM scheduled_tasks")
        tasks_deleted = cursor.rowcount
        print(f"   ✓ Deleted {tasks_deleted} scheduled tasks")
        
        # إعادة تعيين الـ sequence
        cursor.execute("ALTER SEQUENCE scheduled_tasks_id_seq RESTART WITH 1")
        print(f"   ✓ Reset ID sequence")
        
        conn.commit()
        
        # 2️⃣ إضافة المهام الجديدة
        print("\n➕ Adding scheduled tasks...")
        
        tasks = [
            {
                'name': 'News Scraping',
                'task_type': 'scraping',
                'schedule_pattern': '*/10 * * * *',  # كل 10 دقائق
                'description': 'Scrape news from RSS feeds every 10 minutes'
            },
            {
                'name': 'News Clustering',
                'task_type': 'clustering',
                'schedule_pattern': '0 * * * *',  # كل ساعة
                'description': 'Cluster similar news articles every hour'
            },
            {
                'name': 'Report Generation',
                'task_type': 'report_generation',
                'schedule_pattern': '0 * * * *',  # كل ساعة
                'description': 'Generate reports from clusters every hour'
            },
            {
                'name': 'Social Media Content Generation',
                'task_type': 'social_media_generation',
                'schedule_pattern': '0 * * * *',  # كل ساعة
                'description': 'Generate social media posts from reports every hour'
            }
        ]
        
        now = datetime.now()
        
        for task in tasks:
            cursor.execute("""
                INSERT INTO scheduled_tasks (
                    name,
                    task_type,
                    schedule_pattern,
                    status,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                task['name'],
                task['task_type'],
                task['schedule_pattern'],
                'active',
                now
            ))
            
            task_id = cursor.fetchone()[0]
            print(f"   ✓ {task_id}. {task['name']}")
            print(f"      Type: {task['task_type']}")
            print(f"      Schedule: {task['schedule_pattern']}")
        
        conn.commit()
        
        # 3️⃣ عرض النتائج النهائية
        print("\n" + "=" * 70)
        print("📋 All Scheduled Tasks:")
        print("=" * 70)
        
        cursor.execute("""
            SELECT id, name, task_type, schedule_pattern, status
            FROM scheduled_tasks
            ORDER BY id
        """)
        
        rows = cursor.fetchall()
        
        for row in rows:
            print(f"\n{row[0]}. {row[1]}")
            print(f"   Type: {row[2]}")
            print(f"   Schedule: {row[3]}")
            print(f"   Status: {row[4]}")
        
        print("\n" + "=" * 70)
        print("✅ Setup completed successfully!")
        print("=" * 70)
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    setup_scheduled_tasks()