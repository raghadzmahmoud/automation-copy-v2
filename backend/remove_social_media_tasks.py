#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🗑️ Remove Social Media and Reel Generation Tasks
حذف مهام وسائل التواصل الاجتماعي وتوليد الريلز
"""

import os
import sys
import psycopg2
from datetime import datetime, timezone

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settings import DB_CONFIG


def remove_reel_tasks_only():
    """حذف مهام reel generation فقط"""
    print("🗑️ Removing reel generation tasks...")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # قائمة المهام المراد حذفها (reel_generation فقط)
        tasks_to_remove = [
            'reel_generation'
        ]
        
        print("\n📋 Tasks to be removed:")
        for task in tasks_to_remove:
            print(f"   • {task}")
        
        print(f"\n✅ Keeping: social_media_generation (توليد محتوى السوشال ميديا)")
        
        # التحقق من المهام الموجودة
        cursor.execute("""
            SELECT task_type, status, name
            FROM scheduled_tasks
            WHERE task_type = ANY(%s)
        """, (tasks_to_remove,))
        
        existing_tasks = cursor.fetchall()
        
        if not existing_tasks:
            print("\n✅ No reel generation tasks found in database")
            cursor.close()
            conn.close()
            return True
        
        print(f"\n📊 Found {len(existing_tasks)} tasks to remove:")
        for task_type, status, name in existing_tasks:
            print(f"   • {name} ({task_type}) - {status}")
        
        # حذف logs المرتبطة بهذه المهام
        cursor.execute("""
            DELETE FROM scheduled_task_logs
            WHERE scheduled_task_id IN (
                SELECT id FROM scheduled_tasks
                WHERE task_type = ANY(%s)
            )
        """, (tasks_to_remove,))
        
        deleted_logs = cursor.rowcount
        print(f"\n🗑️ Deleted {deleted_logs} related logs")
        
        # حذف المهام نفسها
        cursor.execute("""
            DELETE FROM scheduled_tasks
            WHERE task_type = ANY(%s)
        """, (tasks_to_remove,))
        
        deleted_tasks = cursor.rowcount
        print(f"🗑️ Deleted {deleted_tasks} tasks")
        
        conn.commit()
        
        # عرض المهام المتبقية
        cursor.execute("""
            SELECT task_type, status, name
            FROM scheduled_tasks
            WHERE status = 'active'
            ORDER BY task_type
        """)
        
        remaining_tasks = cursor.fetchall()
        
        print(f"\n✅ Remaining active tasks ({len(remaining_tasks)}):")
        for task_type, status, name in remaining_tasks:
            print(f"   • {name} ({task_type})")
        
        cursor.close()
        conn.close()
        
        print(f"\n🎯 Content Generation + Social Media Jobs:")
        content_jobs = [
            "📥 News Scraping",
            "🎙️ Audio Transcription (STT)",
            "🔄 News Clustering", 
            "📝 Report Generation",
            "📱 Social Media Content Generation",
            "🖼️ Image Generation",
            "🎵 Audio Generation",
            "📻 Broadcast Generation (Newsletter & Digest)"
        ]
        
        for job in content_jobs:
            print(f"   {job}")
        
        print(f"\n✅ Reel generation tasks successfully removed!")
        print(f"💡 System now focuses on content generation + social media content")
        
        return True
        
    except Exception as e:
        print(f"❌ Error removing reel tasks: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


def remove_social_media_tasks():
    """حذف مهام وسائل التواصل الاجتماعي"""
    print("🗑️ Removing social media and reel generation tasks...")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # قائمة المهام المراد حذفها (بدون social_media_generation)
        tasks_to_remove = [
            'social_media_image_generation',
            'reel_generation',
            'telegram_publishing',
            'facebook_publishing',
            'instagram_publishing'
        ]
        
        print("\n📋 Tasks to be removed:")
        for task in tasks_to_remove:
            print(f"   • {task}")
        
        print(f"\n✅ Keeping: social_media_generation (توليد محتوى السوشال ميديا)")
        
        # التحقق من المهام الموجودة
        cursor.execute("""
            SELECT task_type, status, name
            FROM scheduled_tasks
            WHERE task_type = ANY(%s)
        """, (tasks_to_remove,))
        
        existing_tasks = cursor.fetchall()
        
        if not existing_tasks:
            print("\n✅ No social media tasks found in database")
            cursor.close()
            conn.close()
            return True
        
        print(f"\n📊 Found {len(existing_tasks)} tasks to remove:")
        for task_type, status, name in existing_tasks:
            print(f"   • {name} ({task_type}) - {status}")
        
        # حذف logs المرتبطة بهذه المهام
        cursor.execute("""
            DELETE FROM scheduled_task_logs
            WHERE scheduled_task_id IN (
                SELECT id FROM scheduled_tasks
                WHERE task_type = ANY(%s)
            )
        """, (tasks_to_remove,))
        
        deleted_logs = cursor.rowcount
        print(f"\n🗑️ Deleted {deleted_logs} related logs")
        
        # حذف المهام نفسها
        cursor.execute("""
            DELETE FROM scheduled_tasks
            WHERE task_type = ANY(%s)
        """, (tasks_to_remove,))
        
        deleted_tasks = cursor.rowcount
        print(f"🗑️ Deleted {deleted_tasks} tasks")
        
        conn.commit()
        
        # عرض المهام المتبقية
        cursor.execute("""
            SELECT task_type, status, name, max_concurrent_runs
            FROM scheduled_tasks
            WHERE status = 'active'
            ORDER BY task_type
        """)
        
        remaining_tasks = cursor.fetchall()
        
        print(f"\n✅ Remaining active tasks ({len(remaining_tasks)}):")
        for task_type, status, name, max_concurrent in remaining_tasks:
            print(f"   • {name} ({task_type}) - max concurrent: {max_concurrent}")
        
        cursor.close()
        conn.close()
        
        print(f"\n🎯 Content Generation + Social Media Jobs:")
        content_jobs = [
            "📥 News Scraping",
            "🎙️ Audio Transcription (STT)",
            "🔄 News Clustering", 
            "📝 Report Generation",
            "📱 Social Media Content Generation",
            "🖼️ Image Generation",
            "🎵 Audio Generation",
            "📻 Broadcast Generation (Newsletter & Digest)"
        ]
        
        for job in content_jobs:
            print(f"   {job}")
        
        print(f"\n✅ Publishing and reel tasks successfully removed!")
        print(f"💡 System now focuses on content generation + social media content")
        
        return True
        
    except Exception as e:
        print(f"❌ Error removing social media tasks: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


def show_current_jobs():
    """عرض المهام الحالية"""
    print("\n📋 Current Job Types in System:")
    print("=" * 50)
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # التحقق من وجود العمود max_concurrent_runs
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'scheduled_tasks' AND column_name = 'max_concurrent_runs'
        """)
        
        has_max_concurrent = cursor.fetchone() is not None
        
        if has_max_concurrent:
            cursor.execute("""
                SELECT task_type, status, name, schedule_pattern, max_concurrent_runs
                FROM scheduled_tasks
                ORDER BY 
                    CASE WHEN status = 'active' THEN 0 ELSE 1 END,
                    task_type
            """)
        else:
            cursor.execute("""
                SELECT task_type, status, name, schedule_pattern
                FROM scheduled_tasks
                ORDER BY 
                    CASE WHEN status = 'active' THEN 0 ELSE 1 END,
                    task_type
            """)
        
        active_jobs = []
        inactive_jobs = []
        
        for row in cursor.fetchall():
            task_type, status, name, schedule_pattern = row[:4]
            max_concurrent = row[4] if has_max_concurrent else 1
            
            job_info = {
                'task_type': task_type,
                'name': name,
                'schedule': schedule_pattern,
                'max_concurrent': max_concurrent or 1
            }
            
            if status == 'active':
                active_jobs.append(job_info)
            else:
                inactive_jobs.append(job_info)
        
        print(f"✅ Active Jobs ({len(active_jobs)}):")
        for job in active_jobs:
            print(f"   • {job['name']} ({job['task_type']})")
            print(f"     Schedule: {job['schedule']}")
            print(f"     Max Concurrent: {job['max_concurrent']}")
            print()
        
        if inactive_jobs:
            print(f"⏸️ Inactive Jobs ({len(inactive_jobs)}):")
            for job in inactive_jobs:
                print(f"   • {job['name']} ({job['task_type']})")
        
        cursor.close()
        conn.close()
        
        return active_jobs
        
    except Exception as e:
        print(f"❌ Error showing current jobs: {e}")
        return []


if __name__ == "__main__":
    print("🗑️ Social Media Tasks Removal Tool")
    print("=" * 50)
    
    # عرض المهام الحالية
    current_jobs = show_current_jobs()
    
    # التحقق من وجود مهام social media
    social_media_tasks = [job for job in current_jobs 
                         if 'social_media' in job['task_type'] or 'reel' in job['task_type']]
    
    # social_media_generation مطلوب - لا تحذفه
    reel_tasks = [job for job in current_jobs if 'reel' in job['task_type']]
    
    if not reel_tasks:
        print("\n✅ No reel generation tasks found. System is already clean!")
    else:
        print(f"\n⚠️ Found {len(reel_tasks)} reel generation tasks to remove:")
        for task in reel_tasks:
            print(f"   • {task['name']} ({task['task_type']})")
        
        print(f"\n✅ Keeping: social_media_generation (توليد محتوى السوشال ميديا)")
        
        response = input("Do you want to remove reel generation tasks? (y/n): ")
        
        if response.lower() == 'y':
            success = remove_reel_tasks_only()
            if success:
                print("\n🎉 Reel generation tasks removed successfully!")
                show_current_jobs()
        else:
            print("❌ Operation cancelled")
    
    sys.exit(0)