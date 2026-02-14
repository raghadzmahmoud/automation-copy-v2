#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
➕ Add Missing Tasks
إضافة المهام المفقودة إلى قاعدة البيانات
"""

import os
import sys
import psycopg2
from datetime import datetime, timezone

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settings import DB_CONFIG


def add_missing_tasks():
    """إضافة المهام المفقودة"""
    print("➕ Adding missing tasks...")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # المهام المطلوبة
        required_tasks = [
            {
                'name': 'Audio Transcription',
                'task_type': 'audio_transcription',
                'schedule_pattern': '*/5 * * * *',
                'status': 'active',
                'max_concurrent_runs': 2
            },
            {
                'name': 'Reel Generation',
                'task_type': 'reel_generation',
                'schedule_pattern': '*/15 * * * *',
                'status': 'active',
                'max_concurrent_runs': 2
            },
            {
                'name': 'Social Media Image Generation',
                'task_type': 'social_media_image_generation',
                'schedule_pattern': '*/15 * * * *',
                'status': 'active',
                'max_concurrent_runs': 2
            },
            {
                'name': 'Telegram Publishing',
                'task_type': 'telegram_publishing',
                'schedule_pattern': '*/10 * * * *',
                'status': 'active',
                'max_concurrent_runs': 1
            },
            {
                'name': 'Facebook Publishing',
                'task_type': 'facebook_publishing',
                'schedule_pattern': '*/10 * * * *',
                'status': 'active',
                'max_concurrent_runs': 1
            },
            {
                'name': 'Instagram Publishing',
                'task_type': 'instagram_publishing',
                'schedule_pattern': '*/10 * * * *',
                'status': 'active',
                'max_concurrent_runs': 1
            }
        ]
        
        # التحقق من المهام الموجودة
        cursor.execute("SELECT task_type FROM scheduled_tasks")
        existing_tasks = {row[0] for row in cursor.fetchall()}
        
        added_count = 0
        for task in required_tasks:
            if task['task_type'] not in existing_tasks:
                cursor.execute("""
                    INSERT INTO scheduled_tasks (
                        name, task_type, schedule_pattern, status, 
                        last_run_at, created_at, execution_order, 
                        next_run_at, fail_count, last_status, max_concurrent_runs
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    task['name'],
                    task['task_type'],
                    task['schedule_pattern'],
                    task['status'],
                    None,
                    datetime.now(timezone.utc),
                    0,
                    datetime.now(timezone.utc),
                    0,
                    'ready',
                    task['max_concurrent_runs']
                ))
                
                new_id = cursor.fetchone()[0]
                print(f"   ✅ Added: {task['name']} (ID: {new_id})")
                added_count += 1
            else:
                print(f"   ⏭️  Already exists: {task['name']}")
        
        conn.commit()
        
        # عرض المهام الحالية
        cursor.execute("""
            SELECT task_type, status, schedule_pattern, max_concurrent_runs
            FROM scheduled_tasks
            ORDER BY task_type
        """)
        
        print(f"\n📋 All tasks in database ({cursor.rowcount}):")
        for row in cursor.fetchall():
            task_type, status, schedule_pattern, max_concurrent = row
            print(f"   • {task_type}: {status} | {schedule_pattern} | max: {max_concurrent}")
        
        cursor.close()
        conn.close()
        
        print(f"\n✅ Added {added_count} missing tasks!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error adding missing tasks: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


if __name__ == "__main__":
    success = add_missing_tasks()
    sys.exit(0 if success else 1)