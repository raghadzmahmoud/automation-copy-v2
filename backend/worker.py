#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
⚙️ Cron Worker - Scheduled Tasks Executor
═══════════════════════════════════════════════════════════════
🏗️  Hybrid Architecture:

  هذا الـ worker مسؤول فقط عن:
    ✅ scraping          - جلب الأخبار (cron)
    ✅ broadcast_generation - توليد البث (cron)

  الـ real-time pipeline (clustering → report → image)
  تشتغل في pipeline_queue_workers.py (queue-based)

وظيفة الـ Worker:
- يجلب المهام المستحقة من scheduled_tasks (cron-based)
- يقفل المهمة بـ FOR UPDATE SKIP LOCKED
- ينفذ الـ job
- يسجل النتائج في scheduled_task_logs
- يحدث next_run_at و يزيل الـ lock
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import signal
import logging
import traceback
import socket
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Callable
import psycopg2
from croniter import croniter
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settings import DB_CONFIG

# ═══════════════════════════════════════════════════════════════
# Logging Setup
# ═══════════════════════════════════════════════════════════════

log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)

# Worker ID (hostname + PID)
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"

# ═══════════════════════════════════════════════════════════════
# Threading Configuration
# ═══════════════════════════════════════════════════════════════

MAX_WORKERS = int(os.getenv('MAX_WORKERS', 3))  # Number of parallel workers

logging.basicConfig(
    level=logging.INFO,
    format=f'%(asctime)s - [{WORKER_ID}] - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'{log_dir}/worker_{WORKER_ID}.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

WORKER_POLL_INTERVAL = int(os.getenv('WORKER_POLL_INTERVAL', 3))  # 3 seconds (faster for more workers)
MAX_RETRY_COUNT = int(os.getenv('MAX_RETRY_COUNT', 5))

# Retry backoff (minutes)
RETRY_BACKOFF = {
    1: 1,    # 1st fail → 1 minute
    2: 5,    # 2nd fail → 5 minutes  
    3: 15,   # 3rd fail → 15 minutes
    4: 30,   # 4th fail → 30 minutes
    5: 60,   # 5th fail → 1 hour
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


def calculate_next_run(cron_pattern: str, last_run: Optional[datetime] = None) -> datetime:
    """
    حساب next_run_at حسب cron pattern
    """
    try:
        now = datetime.now(timezone.utc)
        base_time = last_run if last_run else now
        
        # تأكد من أن base_time له timezone
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=timezone.utc)
        
        cron = croniter(cron_pattern, base_time)
        next_run = cron.get_next(datetime)
        
        # تأكد من أن next_run له timezone
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=timezone.utc)
        
        if next_run <= now:
            cron = croniter(cron_pattern, now)
            next_run = cron.get_next(datetime)
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=timezone.utc)
        
        return next_run
        
    except Exception as e:
        logger.error(f"❌ Error calculating next run for pattern '{cron_pattern}': {e}")
        return datetime.now(timezone.utc) + timedelta(minutes=10)


def get_due_task() -> Optional[Dict]:
    """
    جلب مهمة مستحقة مع locking
    
    Returns:
        Dict: بيانات المهمة أو None
    """
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        
        # جلب مهمة مستحقة مع قفل
        cursor.execute("""
            SELECT id, name, task_type, schedule_pattern, last_run_at, 
                   fail_count, max_concurrent_runs
            FROM scheduled_tasks
            WHERE status = 'active'
            AND next_run_at <= NOW()
            AND (locked_at IS NULL OR locked_at < NOW() - INTERVAL '30 minutes')
            ORDER BY next_run_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """)
        
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return None
        
        task_id, name, task_type, schedule_pattern, last_run_at, fail_count, max_concurrent_runs = row
        
        # التحقق من concurrent runs limit
        if max_concurrent_runs and max_concurrent_runs > 1:
            cursor.execute("""
                SELECT COUNT(*) FROM scheduled_tasks
                WHERE task_type = %s 
                AND locked_at IS NOT NULL
                AND locked_at > NOW() - INTERVAL '30 minutes'
            """, (task_type,))
            
            current_runs = cursor.fetchone()[0]
            if current_runs >= max_concurrent_runs:
                logger.debug(f"⏭️ Skipping {task_type}: max concurrent runs ({max_concurrent_runs}) reached")
                cursor.close()
                conn.close()
                return None
        
        # قفل المهمة
        now = datetime.now(timezone.utc)
        cursor.execute("""
            UPDATE scheduled_tasks
            SET locked_at = %s,
                locked_by = %s,
                last_status = 'running'
            WHERE id = %s
        """, (now, WORKER_ID, task_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'id': task_id,
            'name': name,
            'task_type': task_type,
            'schedule_pattern': schedule_pattern,
            'last_run_at': last_run_at,
            'fail_count': fail_count or 0,
            'locked_at': now
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting due task: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return None


def log_task_execution(task_id: int, status: str, execution_time: float, 
                      result: str = None, error_message: str = None,
                      started_at: datetime = None, finished_at: datetime = None):
    """
    تسجيل نتيجة تنفيذ المهمة
    """
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO scheduled_task_logs (
                scheduled_task_id, status, execution_time_seconds,
                result, error_message, executed_at, started_at, finished_at, locked_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            task_id, status, execution_time,
            result, error_message, datetime.now(timezone.utc),
            started_at, finished_at, WORKER_ID
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error logging task execution: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def complete_task(task: Dict, success: bool, execution_time: float, 
                 result: str = None, error_message: str = None):
    """
    إكمال المهمة وتحديث next_run_at
    """
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc)
        
        if success:
            # نجحت المهمة
            next_run = calculate_next_run(task['schedule_pattern'], now)
            
            cursor.execute("""
                UPDATE scheduled_tasks
                SET last_run_at = %s,
                    next_run_at = %s,
                    locked_at = NULL,
                    locked_by = NULL,
                    last_status = 'completed',
                    fail_count = 0
                WHERE id = %s
            """, (now, next_run, task['id']))
            
        else:
            # فشلت المهمة
            fail_count = task['fail_count'] + 1
            
            if fail_count >= MAX_RETRY_COUNT:
                # تعطيل المهمة بعد المحاولات المحددة
                cursor.execute("""
                    UPDATE scheduled_tasks
                    SET locked_at = NULL,
                        locked_by = NULL,
                        last_status = 'failed_max_retries',
                        fail_count = %s,
                        status = 'paused'
                    WHERE id = %s
                """, (fail_count, task['id']))
                
                logger.error(f"❌ Task {task['task_type']} paused after {fail_count} failures")
                
            else:
                # إعادة جدولة مع backoff
                backoff_minutes = RETRY_BACKOFF.get(fail_count, 60)
                next_run = now + timedelta(minutes=backoff_minutes)
                
                cursor.execute("""
                    UPDATE scheduled_tasks
                    SET next_run_at = %s,
                        locked_at = NULL,
                        locked_by = NULL,
                        last_status = 'failed',
                        fail_count = %s
                    WHERE id = %s
                """, (next_run, fail_count, task['id']))
                
                logger.warning(f"⚠️ Task {task['task_type']} failed (attempt {fail_count}), retry in {backoff_minutes}min")
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error completing task: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


# ═══════════════════════════════════════════════════════════════
# Job Registry
# ═══════════════════════════════════════════════════════════════

def import_job_functions():
    """
    Import job functions للـ cron-based tasks فقط.

    ⚠️  clustering / report_generation / image_generation
         انتقلت لـ pipeline_queue_workers.py (queue-based)
         ولا تُشغَّل هنا.
    """
    try:
        from app.jobs.scraper_job import scrape_news
        from app.jobs.broadcast_job import generate_all_broadcasts

        job_registry = {
            # ─── Cron-based (يضلوا هنا) ───────────────────────────
            'scraping':             scrape_news,
            'broadcast_generation': generate_all_broadcasts,
            'bulletin_generation':  generate_all_broadcasts,  # alias
            'digest_generation':    generate_all_broadcasts,  # alias
        }

        # ─── Optional jobs (يُضافون إذا كانوا موجودين) ────────────
        try:
            from app.jobs.social_media_job import generate_social_media_content
            job_registry['social_media_generation'] = generate_social_media_content
        except ImportError:
            pass

        try:
            from app.jobs.audio_generation_job import generate_audio
            job_registry['audio_generation'] = generate_audio
        except ImportError:
            pass

        try:
            from app.jobs.audio_transcription_job import run_audio_transcription_job
            job_registry['audio_transcription'] = run_audio_transcription_job
        except ImportError:
            pass

        return job_registry

    except Exception as e:
        logger.error(f"❌ Error importing job functions: {e}")
        return {}


# ═══════════════════════════════════════════════════════════════
# Job Execution
# ═══════════════════════════════════════════════════════════════

def execute_job(task: Dict, job_func: Callable) -> Dict:
    """
    تنفيذ job واحد
    
    Returns:
        Dict: {'success': bool, 'result': str, 'error': str, 'execution_time': float}
    """
    task_type = task['task_type']
    started_at = datetime.now(timezone.utc)
    
    logger.info(f"▶️  Executing: {task_type} (attempt {task['fail_count'] + 1})")
    
    try:
        # تنفيذ الـ job
        result = job_func()
        
        finished_at = datetime.now(timezone.utc)
        execution_time = (finished_at - started_at).total_seconds()
        
        # تحليل النتيجة
        if isinstance(result, dict):
            if result.get('error'):
                return {
                    'success': False,
                    'result': None,
                    'error': result.get('error'),
                    'execution_time': execution_time,
                    'started_at': started_at,
                    'finished_at': finished_at
                }
            elif result.get('skipped'):
                return {
                    'success': True,
                    'result': f"Skipped: {result.get('reason', 'no reason')}",
                    'error': None,
                    'execution_time': execution_time,
                    'started_at': started_at,
                    'finished_at': finished_at
                }
            else:
                # نجح
                result_str = str(result.get('processed', result.get('generated', result.get('count', 'completed'))))
                return {
                    'success': True,
                    'result': result_str,
                    'error': None,
                    'execution_time': execution_time,
                    'started_at': started_at,
                    'finished_at': finished_at
                }
        else:
            # نتيجة غير متوقعة
            return {
                'success': True,
                'result': str(result) if result else 'completed',
                'error': None,
                'execution_time': execution_time,
                'started_at': started_at,
                'finished_at': finished_at
            }
            
    except Exception as e:
        finished_at = datetime.now(timezone.utc)
        execution_time = (finished_at - started_at).total_seconds()
        
        error_msg = str(e)
        logger.error(f"❌ Job {task_type} failed: {error_msg}")
        
        return {
            'success': False,
            'result': None,
            'error': error_msg,
            'execution_time': execution_time,
            'started_at': started_at,
            'finished_at': finished_at
        }


# ═══════════════════════════════════════════════════════════════
# Worker Thread Function
# ═══════════════════════════════════════════════════════════════

def worker_thread(task_queue, job_registry, log_task_execution, complete_task_func):
    """Worker thread that processes tasks from the queue"""
    global jobs_executed
    
    while True:
        task = task_queue.get()
        
        try:
            task_type = task['task_type']
            
            # التحقق من وجود الـ job function
            if task_type not in job_registry:
                logger.error(f"❌ Unknown job type: {task_type}")
                
                log_task_execution(
                    task['id'], 'failed', 0,
                    error_message=f"Unknown job type: {task_type}"
                )
                complete_task_func(task, False, 0, error_message=f"Unknown job type: {task_type}")
                continue
            
            # تنفيذ الـ job
            job_func = job_registry[task_type]
            execution_result = execute_job(task, job_func)
            
            # تسجيل النتيجة
            log_task_execution(
                task['id'],
                'completed' if execution_result['success'] else 'failed',
                execution_result['execution_time'],
                result=execution_result['result'],
                error_message=execution_result['error'],
                started_at=execution_result['started_at'],
                finished_at=execution_result['finished_at']
            )
            
            # إكمال المهمة
            complete_task_func(
                task,
                execution_result['success'],
                execution_result['execution_time'],
                result=execution_result['result'],
                error_message=execution_result['error']
            )
            
            # إحصائيات
            with threading.Lock():
                jobs_executed += 1
            
            if execution_result['success']:
                logger.info(f"✅ {task_type} completed in {execution_result['execution_time']:.1f}s")
            else:
                logger.error(f"❌ {task_type} failed in {execution_result['execution_time']:.1f}s")
                
        except Exception as e:
            logger.error(f"❌ Task processing error: {e}")
            traceback.print_exc()
        finally:
            task_queue.task_done()


# ═══════════════════════════════════════════════════════════════
# Main Worker Loop
# ═══════════════════════════════════════════════════════════════

# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global running
    logger.info("\n⚠️  Shutdown signal received, finishing current job...")
    running = False


def main():
    """Main worker loop"""
    global running
    
    logger.info("═"*70)
    logger.info(f"⚙️  Cron Worker Starting - {WORKER_ID}")
    logger.info("   🏗️  Hybrid Architecture Mode")
    logger.info("   ✅ Handles: scraping + broadcast_generation (cron-based)")
    logger.info("   ℹ️  clustering/report/image → pipeline_queue_workers.py")
    logger.info("   ✅ Database locking (FOR UPDATE SKIP LOCKED)")
    logger.info("   ✅ Retry with exponential backoff")
    logger.info("   ✅ Concurrent run limits")
    logger.info("═"*70)
    logger.info(f"Poll interval: {WORKER_POLL_INTERVAL}s")
    logger.info(f"Max retries: {MAX_RETRY_COUNT}")
    logger.info(f"Retry backoff: {RETRY_BACKOFF}")
    logger.info("═"*70)
    
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Import job functions
    job_registry = import_job_functions()
    if not job_registry:
        logger.error("❌ Failed to import job functions, exiting")
        sys.exit(1)
    
    logger.info(f"📋 Loaded {len(job_registry)} job types:")
    for job_type in sorted(job_registry.keys()):
        logger.info(f"   - {job_type}")
    logger.info("═"*70)
    
    global jobs_executed
    jobs_executed = 0
    last_activity = datetime.now()
    
    # Queue for tasks to process
    task_queue = Queue()
    
    def process_task(task):
        """Process a single task"""
        task_type = task['task_type']
        
        # التحقق من وجود الـ job function
        if task_type not in job_registry:
            logger.error(f"❌ Unknown job type: {task_type}")
            
            log_task_execution(
                task['id'], 'failed', 0,
                error_message=f"Unknown job type: {task_type}"
            )
            complete_task(task, False, 0, error_message=f"Unknown job type: {task_type}")
            return
        
        # تنفيذ الـ job
        job_func = job_registry[task_type]
        execution_result = execute_job(task, job_func)
        
        # تسجيل النتيجة
        log_task_execution(
            task['id'],
            'completed' if execution_result['success'] else 'failed',
            execution_result['execution_time'],
            result=execution_result['result'],
            error_message=execution_result['error'],
            started_at=execution_result['started_at'],
            finished_at=execution_result['finished_at']
        )
        
        # إكمال المهمة
        complete_task(
            task,
            execution_result['success'],
            execution_result['execution_time'],
            result=execution_result['result'],
            error_message=execution_result['error']
        )
        
        # إحصائيات
        with threading.Lock():
            jobs_executed += 1
        
        if execution_result['success']:
            logger.info(f"✅ {task_type} completed in {execution_result['execution_time']:.1f}s")
        else:
            logger.error(f"❌ {task_type} failed in {execution_result['execution_time']:.1f}s")
    
    # Start worker threads
    threads = []
    for i in range(MAX_WORKERS):
        t = threading.Thread(target=worker_thread, args=(task_queue, job_registry, log_task_execution, complete_task), daemon=True)
        t.start()
        threads.append(t)
        logger.info(f"🚀 Started worker thread {i+1}/{MAX_WORKERS}")
    
    while running:
        try:
            # جلب مهمة مستحقة
            task = get_due_task()
            
            if not task:
                # لا توجد مهام مستحقة
                time.sleep(WORKER_POLL_INTERVAL)
                
                # عرض heartbeat كل دقيقة
                if (datetime.now() - last_activity).total_seconds() >= 60:
                    logger.debug(f"💓 Worker {WORKER_ID} alive - {jobs_executed} jobs executed")
                    last_activity = datetime.now()
                
                continue
            
            # إضافة المهمة للـ queue
            task_queue.put(task)
            
        except KeyboardInterrupt:
            logger.info("\n⚠️  Keyboard interrupt received")
            break
            
        except Exception as e:
            logger.error(f"❌ Worker loop error: {e}")
            traceback.print_exc()
            time.sleep(WORKER_POLL_INTERVAL)
    
    # Wait for all threads to finish
    task_queue.join()
    
    logger.info("\n" + "═"*70)
    logger.info(f"🛑 Cron Worker {WORKER_ID} stopped gracefully")
    logger.info(f"📊 Total jobs executed: {jobs_executed}")
    logger.info("═"*70)


if __name__ == "__main__":
    main()