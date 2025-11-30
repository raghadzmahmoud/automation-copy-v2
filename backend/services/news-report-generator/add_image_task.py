#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔧 Add Image Generation Scheduled Task
"""
import psycopg2
from datetime import datetime
from settings import DB_CONFIG


def add_image_generation_task():
    """إضافة مهمة توليد الصور"""
    
    print("=" * 70)
    print("🔧 Adding Image Generation Scheduled Task")
    print("=" * 70)
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print("✅ Connected to database")
        
        # فحص إذا كانت المهمة موجودة
        cursor.execute("""
            SELECT id FROM scheduled_tasks
            WHERE task_type = 'image_generation'
        """)
        
        existing = cursor.fetchone()
        
        if existing:
            print(f"\n⚠️  Image generation task already exists (ID: {existing[0]})")
            print("   Skipping...")
        else:
            # إضافة المهمة الجديدة
            print("\n➕ Adding new task...")
            
            now = datetime.now()
            
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
                'Image Generation',
                'image_generation',
                '0 * * * *',  # كل ساعة
                'active',
                now
            ))
            
            task_id = cursor.fetchone()[0]
            conn.commit()
            
            print(f"   ✅ Task added successfully (ID: {task_id})")
        
        # عرض جميع المهام
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
    add_image_generation_task()