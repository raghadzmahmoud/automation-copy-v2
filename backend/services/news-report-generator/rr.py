#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔧 Setup Audio Generation
إضافة Content Type و Scheduled Task لتوليد الصوت
"""
import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

# تحميل المتغيرات من .env
load_dotenv()

# قراءة إعدادات قاعدة البيانات من .env
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 5432))
}


def setup_audio_generation():
    """إضافة Audio Generation إلى قاعدة البيانات"""
    
    print("=" * 70)
    print("🔧 Setup Audio Generation")
    print("=" * 70)
    
    try:
        # الاتصال بقاعدة البيانات
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print("✅ Connected to database")
        print(f"   Host: {DB_CONFIG['host']}")
        print(f"   Database: {DB_CONFIG['dbname']}")
        
        # 1️⃣ إضافة Content Type للصوت
        print("\n1️⃣ Adding Content Type...")
        
        cursor.execute("""
            INSERT INTO content_types (id, name, description, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                updated_at = EXCLUDED.updated_at
            RETURNING id, name
        """, (
            7,
            'Audio Generation',
            'AI-generated audio for news',
            datetime.now(),
            datetime.now()
        ))
        
        content_type = cursor.fetchone()
        conn.commit()
        
        print(f"   ✅ Content Type: ID={content_type[0]}, Name={content_type[1]}")
        
        # 2️⃣ إضافة Scheduled Task
        print("\n2️⃣ Adding Scheduled Task...")
        
        # فحص إذا كانت المهمة موجودة
        cursor.execute("""
            SELECT id, name, status FROM scheduled_tasks
            WHERE task_type = 'audio_generation'
        """)
        
        existing_task = cursor.fetchone()
        
        if existing_task:
            print(f"   ℹ️  Task already exists:")
            print(f"      ID: {existing_task[0]}")
            print(f"      Name: {existing_task[1]}")
            print(f"      Status: {existing_task[2]}")
            
            # تحديث المهمة الموجودة
            cursor.execute("""
                UPDATE scheduled_tasks
                SET name = %s,
                    schedule_pattern = %s,
                    status = %s
                WHERE task_type = %s
                RETURNING id, name, schedule_pattern, status
            """, (
                'Audio Generation',
                '0 * * * *',  # كل ساعة
                'active',
                'audio_generation'
            ))
            
            task = cursor.fetchone()
            conn.commit()
            
            print(f"   ✅ Task updated:")
            print(f"      ID: {task[0]}")
            print(f"      Name: {task[1]}")
            print(f"      Schedule: {task[2]}")
            print(f"      Status: {task[3]}")
        else:
            # إضافة مهمة جديدة
            cursor.execute("""
                INSERT INTO scheduled_tasks (
                    name,
                    task_type,
                    schedule_pattern,
                    status,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, name, schedule_pattern, status
            """, (
                'Audio Generation',
                'audio_generation',
                '0 * * * *',  # كل ساعة
                'active',
                datetime.now()
            ))
            
            task = cursor.fetchone()
            conn.commit()
            
            print(f"   ✅ Task created:")
            print(f"      ID: {task[0]}")
            print(f"      Name: {task[1]}")
            print(f"      Schedule: {task[2]}")
            print(f"      Status: {task[3]}")
        
        # 3️⃣ عرض جميع Content Types
        print("\n" + "=" * 70)
        print("📋 All Content Types:")
        print("=" * 70)
        
        cursor.execute("""
            SELECT id, name, description
            FROM content_types
            ORDER BY id
        """)
        
        types = cursor.fetchall()
        
        for ct in types:
            print(f"\n{ct[0]}. {ct[1]}")
            if ct[2]:
                print(f"   {ct[2]}")
        
        # 4️⃣ عرض جميع Scheduled Tasks
        print("\n" + "=" * 70)
        print("⏰ All Scheduled Tasks:")
        print("=" * 70)
        
        cursor.execute("""
            SELECT id, name, task_type, schedule_pattern, status
            FROM scheduled_tasks
            ORDER BY id
        """)
        
        tasks = cursor.fetchall()
        
        for t in tasks:
            print(f"\n{t[0]}. {t[1]}")
            print(f"   Type: {t[2]}")
            print(f"   Schedule: {t[3]}")
            print(f"   Status: {t[4]}")
        
        print("\n" + "=" * 70)
        print("✅ Setup completed successfully!")
        print("=" * 70)
        
        print("\n📝 Next Steps:")
        print("   1. Install: pip install google-cloud-texttospeech --break-system-packages")
        print("   2. Set GOOGLE_APPLICATION_CREDENTIALS in .env")
        print("   3. Move audio_generator.py to app/services/")
        print("   4. Move audio_routes.py to app/api/")
        print("   5. Move audio_generation_job.py to cron/")
        print("   6. Update api_service.py")
        print("   7. Update start_worker.py")
        print("   8. Test: python -m app.services.audio_generator 1")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    setup_audio_generation()