#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 Test Production Scheduler Locally
اختبار نظام الـ Scheduler محلياً قبل الـ deployment
"""

import os
import sys
import time
import threading
import psycopg2
from datetime import datetime, timezone

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settings import DB_CONFIG


def test_database_connection():
    """اختبار الاتصال بقاعدة البيانات"""
    print("🔌 Testing database connection...")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"   ✅ Connected to: {version}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return False


def test_scheduled_tasks_table():
    """اختبار جدول scheduled_tasks"""
    print("\n📋 Testing scheduled_tasks table...")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Check if new columns exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'scheduled_tasks'
            AND column_name IN ('next_run_at', 'locked_at', 'locked_by', 'fail_count', 'last_status', 'max_concurrent_runs')
        """)
        
        existing_columns = [row[0] for row in cursor.fetchall()]
        required_columns = ['next_run_at', 'locked_at', 'locked_by', 'fail_count', 'last_status', 'max_concurrent_runs']
        
        missing_columns = [col for col in required_columns if col not in existing_columns]
        
        if missing_columns:
            print(f"   ⚠️  Missing columns: {missing_columns}")
            print("   💡 Run: python apply_scheduler_migration.py")
            return False
        else:
            print("   ✅ All required columns exist")
        
        # Check active tasks
        cursor.execute("""
            SELECT COUNT(*) FROM scheduled_tasks WHERE status = 'active'
        """)
        active_count = cursor.fetchone()[0]
        print(f"   📊 Active tasks: {active_count}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Table check failed: {e}")
        return False


def test_croniter_import():
    """اختبار croniter library"""
    print("\n⏰ Testing croniter import...")
    
    try:
        from croniter import croniter
        from datetime import datetime, timezone
        
        # Test cron calculation
        now = datetime.now(timezone.utc)
        cron = croniter('*/10 * * * *', now)  # Every 10 minutes
        next_run = cron.get_next(datetime)
        
        print(f"   ✅ croniter working")
        print(f"   📅 Next run for '*/10 * * * *': {next_run.strftime('%H:%M:%S')}")
        return True
        
    except ImportError:
        print("   ❌ croniter not installed")
        print("   💡 Run: pip install croniter==1.4.1")
        return False
    except Exception as e:
        print(f"   ❌ croniter test failed: {e}")
        return False


def test_job_imports():
    """اختبار استيراد الـ jobs"""
    print("\n📦 Testing job imports...")
    
    jobs_to_test = [
        ('scraper_job', 'scrape_news'),
        ('clustering_job', 'cluster_news'),
        ('reports_job', 'generate_reports'),
        ('social_media_job', 'generate_social_media_content'),
        ('image_generation_job', 'generate_images'),
        ('audio_generation_job', 'generate_audio'),
        ('broadcast_job', 'generate_all_broadcasts'),
        ('audio_transcription_job', 'run_audio_transcription_job'),
    ]
    
    success_count = 0
    
    for module_name, function_name in jobs_to_test:
        try:
            module = __import__(f'app.jobs.{module_name}', fromlist=[function_name])
            func = getattr(module, function_name)
            print(f"   ✅ {module_name}.{function_name}")
            success_count += 1
        except Exception as e:
            print(f"   ❌ {module_name}.{function_name}: {e}")
    
    print(f"   📊 Successfully imported: {success_count}/{len(jobs_to_test)} jobs")
    return success_count == len(jobs_to_test)


def run_scheduler_test(duration=30):
    """تشغيل scheduler لفترة قصيرة للاختبار"""
    print(f"\n🕐 Running scheduler test for {duration} seconds...")
    
    try:
        # Import scheduler functions
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from scheduler import update_task_schedules, cleanup_expired_locks, get_scheduler_stats
        
        start_time = time.time()
        tick_count = 0
        
        while time.time() - start_time < duration:
            tick_count += 1
            print(f"   🔄 Tick #{tick_count}")
            
            # Update schedules
            update_success = update_task_schedules()
            print(f"      Schedule update: {'✅' if update_success else '❌'}")
            
            # Cleanup locks
            cleanup_success = cleanup_expired_locks()
            print(f"      Lock cleanup: {'✅' if cleanup_success else '❌'}")
            
            # Get stats every 10 ticks
            if tick_count % 10 == 0:
                stats = get_scheduler_stats()
                if stats:
                    print(f"      📊 Stats: {stats['active_tasks']} active, {stats['due_tasks']} due, {stats['locked_tasks']} locked")
            
            time.sleep(5)  # 5 second tick
        
        print(f"   ✅ Scheduler test completed ({tick_count} ticks)")
        return True
        
    except Exception as e:
        print(f"   ❌ Scheduler test failed: {e}")
        return False


def run_worker_test():
    """اختبار worker (بدون تنفيذ jobs حقيقية)"""
    print("\n⚙️ Testing worker functions...")
    
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from worker import get_due_task, import_job_functions
        
        # Test job registry
        job_registry = import_job_functions()
        print(f"   📋 Job registry: {len(job_registry)} jobs loaded")
        
        # Test getting due task (should return None if no due tasks)
        task = get_due_task()
        if task:
            print(f"   📋 Found due task: {task['task_type']}")
            
            # Unlock it immediately (don't actually run)
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scheduled_tasks
                SET locked_at = NULL, locked_by = NULL, last_status = 'test'
                WHERE id = %s
            """, (task['id'],))
            conn.commit()
            cursor.close()
            conn.close()
            print("   🔓 Task unlocked (test mode)")
        else:
            print("   📋 No due tasks found (normal)")
        
        print("   ✅ Worker test completed")
        return True
        
    except Exception as e:
        print(f"   ❌ Worker test failed: {e}")
        return False


def main():
    """تشغيل كل الاختبارات"""
    print("🧪 Production Scheduler Local Test")
    print("=" * 50)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Scheduled Tasks Table", test_scheduled_tasks_table),
        ("Croniter Import", test_croniter_import),
        ("Job Imports", test_job_imports),
        ("Worker Functions", run_worker_test),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed")
    
    print(f"\n{'='*50}")
    print(f"📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("✅ All tests passed! Ready for deployment.")
        
        # Ask if user wants to run scheduler test
        response = input("\n🕐 Run scheduler test for 30 seconds? (y/n): ")
        if response.lower() == 'y':
            run_scheduler_test(30)
    else:
        print("❌ Some tests failed. Fix issues before deployment.")
        
        if passed < total - 1:
            print("\n💡 Common fixes:")
            print("   1. Run: python apply_scheduler_migration.py")
            print("   2. Install: pip install croniter==1.4.1")
            print("   3. Check database connection settings")


if __name__ == "__main__":
    main()