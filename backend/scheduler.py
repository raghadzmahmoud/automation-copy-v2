#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🕐 Production Scheduler - Tick-based Task Scheduler
═══════════════════════════════════════════════════════════════
وظيفة الـ Scheduler:
- يحسب next_run_at لكل task حسب cron pattern
- يحدث الـ database كل 5 ثواني
- لا ينفذ jobs، فقط يحدد المهام المستحقة
- يدير lock expiry للـ tasks المعلقة
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import signal
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import psycopg2
from croniter import croniter

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settings import DB_CONFIG

# ═══════════════════════════════════════════════════════════════
# Logging Setup
# ═══════════════════════════════════════════════════════════════

log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'{log_dir}/scheduler.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

TICK_INTERVAL = int(os.getenv('SCHEDULER_TICK_INTERVAL', 5))  # 5 seconds
LOCK_TIMEOUT_MINUTES = {
    'scraping': 20,
    'clustering': 15,
    'report_generation': 10,
    'social_media_generation': 15,
    'image_generation': 30,
    'audio_generation': 45,
    'reel_generation': 60,
    'broadcast_generation': 20,
    'bulletin_generation': 15,
    'digest_generation': 15,
    'audio_transcription': 30,
    'processing_pipeline': 25,
    'default': 30
}

# ═══════════════════════════════════════════════════════════════
# Database Functions
# ═══════════════════════════════════════════════════════════════

def get_db_connection():
    """إنشاء اتصال بقاعدة البيانات"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return None


def get_lock_timeout(task_type: str) -> int:
    """الحصول على timeout للـ task type"""
    return LOCK_TIMEOUT_MINUTES.get(task_type, LOCK_TIMEOUT_MINUTES['default'])


def calculate_next_run(cron_pattern: str, last_run: Optional[datetime] = None) -> datetime:
    """
    حساب next_run_at حسب cron pattern
    
    Args:
        cron_pattern: نمط الـ cron (مثل: */10 * * * *)
        last_run: آخر تشغيل (اختياري)
    
    Returns:
        datetime: موعد التشغيل التالي
    """
    try:
        now = datetime.now(timezone.utc)
        
        # إذا لم يكن هناك last_run، استخدم الآن
        base_time = last_run if last_run else now
        
        # تأكد من أن base_time له timezone
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=timezone.utc)
        
        # إنشاء croniter
        cron = croniter(cron_pattern, base_time)
        next_run = cron.get_next(datetime)
        
        # تأكد من أن next_run له timezone
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=timezone.utc)
        
        # تأكد من أن next_run في المستقبل
        if next_run <= now:
            cron = croniter(cron_pattern, now)
            next_run = cron.get_next(datetime)
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=timezone.utc)
        
        return next_run.replace(tzinfo=timezone.utc)
        
    except Exception as e:
        logger.error(f"❌ Error calculating next run for pattern '{cron_pattern}': {e}")
        # fallback: 10 دقائق من الآن
        return datetime.now(timezone.utc) + timedelta(minutes=10)


def update_task_schedules():
    """
    تحديث next_run_at لكل المهام النشطة
    """
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # جلب المهام النشطة التي تحتاج تحديث
        cursor.execute("""
            SELECT id, task_type, schedule_pattern, last_run_at, next_run_at
            FROM scheduled_tasks
            WHERE status = 'active'
            AND schedule_pattern IS NOT NULL
            AND (
                next_run_at IS NULL 
                OR next_run_at <= NOW()
                OR (locked_at IS NULL AND next_run_at <= NOW() + INTERVAL '1 minute')
            )
        """)
        
        tasks = cursor.fetchall()
        updated_count = 0
        
        for task_id, task_type, schedule_pattern, last_run_at, current_next_run in tasks:
            try:
                # تأكد من أن last_run_at له timezone
                if last_run_at and last_run_at.tzinfo is None:
                    last_run_at = last_run_at.replace(tzinfo=timezone.utc)
                
                # حساب next_run_at الجديد
                next_run = calculate_next_run(schedule_pattern, last_run_at)
                
                # تحديث في قاعدة البيانات
                cursor.execute("""
                    UPDATE scheduled_tasks
                    SET next_run_at = %s,
                        last_status = CASE 
                            WHEN last_status IS NULL THEN 'ready'
                            ELSE last_status
                        END
                    WHERE id = %s
                """, (next_run, task_id))
                
                updated_count += 1
                
                if current_next_run != next_run:
                    logger.debug(f"📅 Updated {task_type}: next_run = {next_run.strftime('%H:%M:%S')}")
                
            except Exception as e:
                logger.error(f"❌ Error updating task {task_id} ({task_type}): {e}")
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        
        if updated_count > 0:
            logger.debug(f"📊 Updated {updated_count} task schedules")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error updating task schedules: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def cleanup_expired_locks():
    """
    تنظيف الـ locks المنتهية الصلاحية
    """
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # جلب المهام المقفلة
        cursor.execute("""
            SELECT id, task_type, locked_at, locked_by
            FROM scheduled_tasks
            WHERE locked_at IS NOT NULL
        """)
        
        locked_tasks = cursor.fetchall()
        cleaned_count = 0
        
        now = datetime.now(timezone.utc)
        
        for task_id, task_type, locked_at, locked_by in locked_tasks:
            if locked_at.tzinfo is None:
                locked_at = locked_at.replace(tzinfo=timezone.utc)
            
            # حساب timeout للـ task type
            timeout_minutes = get_lock_timeout(task_type)
            lock_expiry = locked_at + timedelta(minutes=timeout_minutes)
            
            # إذا انتهت صلاحية الـ lock
            if now > lock_expiry:
                cursor.execute("""
                    UPDATE scheduled_tasks
                    SET locked_at = NULL,
                        locked_by = NULL,
                        last_status = 'timeout',
                        fail_count = fail_count + 1
                    WHERE id = %s
                """, (task_id,))
                
                cleaned_count += 1
                logger.warning(f"🔓 Cleaned expired lock: {task_type} (locked by {locked_by} for {timeout_minutes}min)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        if cleaned_count > 0:
            logger.info(f"🧹 Cleaned {cleaned_count} expired locks")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error cleaning expired locks: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def get_scheduler_stats() -> Dict:
    """
    إحصائيات الـ scheduler
    """
    conn = get_db_connection()
    if not conn:
        return {}
    
    try:
        cursor = conn.cursor()
        
        # إحصائيات المهام
        cursor.execute("""
            SELECT 
                COUNT(*) as total_tasks,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_tasks,
                COUNT(CASE WHEN locked_at IS NOT NULL THEN 1 END) as locked_tasks,
                COUNT(CASE WHEN next_run_at <= NOW() AND status = 'active' AND locked_at IS NULL THEN 1 END) as due_tasks
            FROM scheduled_tasks
        """)
        
        stats = cursor.fetchone()
        
        # آخر تشغيل للمهام
        cursor.execute("""
            SELECT task_type, last_run_at, next_run_at, last_status, fail_count
            FROM scheduled_tasks
            WHERE status = 'active'
            ORDER BY next_run_at ASC
            LIMIT 5
        """)
        
        upcoming_tasks = []
        for row in cursor.fetchall():
            upcoming_tasks.append({
                'task_type': row[0],
                'last_run_at': row[1],
                'next_run_at': row[2],
                'last_status': row[3],
                'fail_count': row[4]
            })
        
        cursor.close()
        conn.close()
        
        return {
            'total_tasks': stats[0],
            'active_tasks': stats[1],
            'locked_tasks': stats[2],
            'due_tasks': stats[3],
            'upcoming_tasks': upcoming_tasks
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting scheduler stats: {e}")
        if conn:
            conn.close()
        return {}


# ═══════════════════════════════════════════════════════════════
# Main Scheduler Loop
# ═══════════════════════════════════════════════════════════════

# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global running
    logger.info("\n⚠️  Shutdown signal received, stopping scheduler...")
    running = False


def main():
    """Main scheduler loop"""
    global running
    
    logger.info("═"*70)
    logger.info("🕐 Production Scheduler Starting")
    logger.info("   ✅ Tick-based scheduling")
    logger.info("   ✅ Cron pattern support")
    logger.info("   ✅ Lock expiry management")
    logger.info("   ✅ Task due calculation")
    logger.info("═"*70)
    logger.info(f"Tick interval: {TICK_INTERVAL}s")
    logger.info(f"Lock timeouts: {LOCK_TIMEOUT_MINUTES}")
    logger.info("═"*70)
    
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    tick_count = 0
    last_stats_time = datetime.now()
    
    while running:
        tick_count += 1
        tick_start = datetime.now()
        
        try:
            # 1. تحديث جداول المهام
            update_success = update_task_schedules()
            
            # 2. تنظيف الـ locks المنتهية
            cleanup_success = cleanup_expired_locks()
            
            # 3. عرض إحصائيات كل دقيقة
            if (datetime.now() - last_stats_time).total_seconds() >= 60:
                stats = get_scheduler_stats()
                if stats:
                    logger.info(f"📊 Stats: {stats['active_tasks']} active, {stats['due_tasks']} due, {stats['locked_tasks']} locked")
                    
                    # عرض المهام القادمة
                    if stats['upcoming_tasks']:
                        logger.info("📅 Next tasks:")
                        for task in stats['upcoming_tasks'][:3]:
                            next_run = task['next_run_at']
                            if next_run:
                                time_str = next_run.strftime('%H:%M:%S')
                                status = task['last_status'] or 'ready'
                                fails = task['fail_count'] or 0
                                fail_str = f" ({fails} fails)" if fails > 0 else ""
                                logger.info(f"   {task['task_type']}: {time_str} [{status}]{fail_str}")
                
                last_stats_time = datetime.now()
            
            # 4. حساب وقت الانتظار
            tick_duration = (datetime.now() - tick_start).total_seconds()
            
            if not update_success or not cleanup_success:
                logger.warning(f"⚠️  Tick #{tick_count}: Some operations failed")
            
            # انتظار حتى الـ tick التالي
            sleep_time = max(0, TICK_INTERVAL - tick_duration)
            if sleep_time > 0:
                time.sleep(sleep_time)
            
        except KeyboardInterrupt:
            logger.info("\n⚠️  Keyboard interrupt received")
            break
            
        except Exception as e:
            logger.error(f"❌ Scheduler tick error: {e}")
            traceback.print_exc()
            time.sleep(TICK_INTERVAL)
    
    logger.info("\n" + "═"*70)
    logger.info("🛑 Production Scheduler stopped gracefully")
    logger.info("═"*70)


if __name__ == "__main__":
    main()