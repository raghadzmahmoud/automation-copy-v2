#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
⏰ Database-Driven Task Scheduler v2.0
══════════════════════════════════════
كل Job يتحقق من شرطه قبل التنفيذ
الـ Database هي المتحكم الأساسي
"""
import certifi
import os
os.environ["SSL_CERT_FILE"] = certifi.where()

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import psycopg2
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Callable
from concurrent.futures import ThreadPoolExecutor

from settings import DB_CONFIG

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = BackgroundScheduler()

# Thread pool for parallel execution
executor = ThreadPoolExecutor(max_workers=5)

# Mapping task_type to actual function
TASK_FUNCTIONS: Dict[str, Callable] = {}


# ============================================
# 📝 Task Registration
# ============================================

# Core pipeline: Scraping → Clustering → Reports → Parallel Generation
PIPELINE_CHAIN = [
    'scraping',
    'clustering', 
    'report_generation',
]

# These run in parallel after the pipeline
PARALLEL_JOBS = [
    'social_media_generation',
    'image_generation',
    'audio_generation',
    'reel_generation',
]


def register_task(task_type: str, func: Callable):
    """Register a task function"""
    TASK_FUNCTIONS[task_type] = func
    logger.info(f"📝 Registered task: {task_type}")


def register_default_tasks():
    """Register all task functions"""
    
    def scraping_task():
        from app.jobs.scraper_job import scrape_news
        scrape_news()
    
    def clustering_task():
        from app.jobs.clustering_job import cluster_news
        cluster_news()
    
    def report_generation_task():
        from app.jobs.reports_job import generate_reports
        generate_reports()
    
    def social_media_task():
        from app.jobs.social_media_job import generate_social_media_content
        generate_social_media_content()
    
    def image_generation_task():
        from app.jobs.image_generation_job import generate_images
        generate_images()
    
    def audio_generation_task():
        from app.jobs.audio_generation_job import generate_audio
        generate_audio()
    
    def bulletin_task():
        from app.jobs.bulletin_digest_job import generate_bulletin_job
        generate_bulletin_job()
    
    def digest_task():
        from app.jobs.bulletin_digest_job import generate_digest_job
        generate_digest_job()
    
    def reel_generation_task():
        from app.jobs.reel_generation_job import generate_reels
        generate_reels()
    
    # Register all tasks
    register_task('scraping', scraping_task)
    register_task('clustering', clustering_task)
    register_task('report_generation', report_generation_task)
    register_task('social_media_generation', social_media_task)
    register_task('image_generation', image_generation_task)
    register_task('audio_generation', audio_generation_task)
    register_task('bulletin_generation', bulletin_task)
    register_task('digest_generation', digest_task)
    register_task('reel_generation', reel_generation_task)


# ============================================
# 🗄️ Database Functions
# ============================================

def get_db_connection():
    """Create database connection"""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return None


def get_all_active_tasks() -> list:
    """Get all active tasks from database with run_condition and timing info"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                id, 
                name, 
                task_type, 
                schedule_pattern, 
                status, 
                COALESCE(run_condition, 'always') as run_condition,
                COALESCE(min_interval_seconds, 300) as min_interval_seconds,
                COALESCE(is_running, FALSE) as is_running,
                last_run_at
            FROM scheduled_tasks
            WHERE status = 'active'
            ORDER BY COALESCE(execution_order, 99), id
        """)
        
        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                'id': row[0],
                'name': row[1],
                'task_type': row[2],
                'schedule_pattern': row[3],
                'status': row[4],
                'run_condition': row[5],
                'min_interval_seconds': row[6],
                'is_running': row[7],
                'last_run_at': row[8]
            })
        
        cursor.close()
        conn.close()
        return tasks
        
    except Exception as e:
        logger.error(f"❌ Error fetching tasks: {e}")
        if conn:
            conn.close()
        return []


# ============================================
# 🔒 Overlap Protection Functions
# ============================================

def can_run_task(task_type: str) -> tuple:
    """
    تحقق إذا الـ task يقدر يشتغل
    Returns: (can_run: bool, reason: str)
    """
    conn = get_db_connection()
    if not conn:
        return True, "no_db_connection"
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COALESCE(is_running, FALSE) as is_running,
                last_run_at,
                COALESCE(min_interval_seconds, 300) as min_interval
            FROM scheduled_tasks 
            WHERE task_type = %s
        """, (task_type,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            return True, "task_not_found"
        
        is_running, last_run_at, min_interval = row
        
        # 1️⃣ تحقق إذا شغال حالياً
        if is_running:
            return False, "already_running"
        
        # 2️⃣ تحقق من الحد الأدنى للفترة الزمنية
        if last_run_at:
            elapsed = (datetime.now(timezone.utc) - last_run_at.replace(tzinfo=timezone.utc)).total_seconds()
            if elapsed < min_interval:
                return False, f"too_soon (wait {int(min_interval - elapsed)}s)"
        
        return True, "ok"
        
    except Exception as e:
        logger.error(f"❌ Error checking can_run: {e}")
        if conn:
            conn.close()
        return True, "error"


def set_task_running(task_type: str, is_running: bool):
    """Set is_running flag for a task"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        if is_running:
            # بداية التشغيل - حدث is_running و last_run_at
            cursor.execute("""
                UPDATE scheduled_tasks 
                SET is_running = TRUE, last_run_at = %s
                WHERE task_type = %s
            """, (datetime.now(timezone.utc), task_type))
        else:
            # نهاية التشغيل - حدث is_running فقط
            cursor.execute("""
                UPDATE scheduled_tasks 
                SET is_running = FALSE
                WHERE task_type = %s
            """, (task_type,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error setting task running state: {e}")
        if conn:
            conn.rollback()
            conn.close()


def cleanup_stuck_tasks():
    """تنظيف الـ tasks اللي علقت بـ is_running = true"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE scheduled_tasks 
            SET is_running = FALSE 
            WHERE is_running = TRUE 
            AND last_run_at < NOW() - INTERVAL '1 hour'
            RETURNING task_type
        """)
        
        stuck = cursor.fetchall()
        if stuck:
            logger.warning(f"⚠️ Cleaned up {len(stuck)} stuck tasks: {[s[0] for s in stuck]}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error cleaning stuck tasks: {e}")
        if conn:
            conn.close()


# ============================================
# ✅ Run Condition Checker
# ============================================

def check_run_condition(condition: str) -> bool:
    """
    تحقق من شرط التشغيل
    Returns: True إذا الشرط متحقق ولازم يشتغل
    """
    if condition == 'always':
        return True
    
    conn = get_db_connection()
    if not conn:
        logger.warning(f"⚠️ Cannot check condition (no DB), assuming True")
        return True
    
    try:
        cursor = conn.cursor()
        result = False
        
        # ═══════════════════════════════════════════════════════
        # 📰 شروط الأخبار والتجميع
        # ═══════════════════════════════════════════════════════
        
        if condition == 'has_unclustered_news':
            # أخبار جديدة لم تُجمّع بعد (آخر 2 ساعة)
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM raw_news rn
                    WHERE rn.collected_at >= NOW() - INTERVAL '2 hours'
                    AND NOT EXISTS (
                        SELECT 1 FROM news_cluster_members ncm 
                        WHERE ncm.news_id = rn.id
                    )
                    LIMIT 1
                )
            """)
            result = cursor.fetchone()[0]
        
        elif condition == 'has_clusters_without_reports':
            # Clusters بدون تقارير (آخر 3 ساعات)
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM news_clusters nc
                    WHERE nc.created_at >= NOW() - INTERVAL '3 hours'
                    AND NOT EXISTS (
                        SELECT 1 FROM generated_report gr 
                        WHERE gr.cluster_id = nc.id
                    )
                    LIMIT 1
                )
            """)
            result = cursor.fetchone()[0]
        
        # ═══════════════════════════════════════════════════════
        # 📝 شروط التقارير
        # ═══════════════════════════════════════════════════════
        
        elif condition == 'has_reports_without_images':
            # تقارير بدون صور (آخر 6 ساعات)
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM generated_report gr
                    WHERE gr.created_at >= NOW() - INTERVAL '6 hours'
                    AND gr.status = 'ready'
                    AND NOT EXISTS (
                        SELECT 1 FROM generated_content gc 
                        WHERE gc.report_id = gr.id 
                        AND gc.content_type_id = (
                            SELECT id FROM content_types WHERE name = 'image' LIMIT 1
                        )
                    )
                    LIMIT 1
                )
            """)
            result = cursor.fetchone()[0]
        
        elif condition == 'has_reports_without_audio':
            # تقارير بدون صوت (آخر 6 ساعات)
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM generated_report gr
                    WHERE gr.created_at >= NOW() - INTERVAL '6 hours'
                    AND gr.status = 'ready'
                    AND NOT EXISTS (
                        SELECT 1 FROM generated_content gc 
                        WHERE gc.report_id = gr.id 
                        AND gc.content_type_id = (
                            SELECT id FROM content_types WHERE name = 'audio' LIMIT 1
                        )
                    )
                    LIMIT 1
                )
            """)
            result = cursor.fetchone()[0]
        
        elif condition == 'has_reports_without_social':
            # تقارير بدون محتوى سوشيال ميديا
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM generated_report gr
                    WHERE gr.created_at >= NOW() - INTERVAL '6 hours'
                    AND gr.status = 'ready'
                    AND NOT EXISTS (
                        SELECT 1 FROM generated_content gc 
                        WHERE gc.report_id = gr.id 
                        AND gc.content_type_id = (
                            SELECT id FROM content_types WHERE name = 'social_media' LIMIT 1
                        )
                    )
                    LIMIT 1
                )
            """)
            result = cursor.fetchone()[0]
        
        # ═══════════════════════════════════════════════════════
        # 📻 شروط النشرة والموجز
        # ═══════════════════════════════════════════════════════
        
        elif condition == 'has_recent_reports':
            # تقارير جديدة خلال آخر 30 دقيقة
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM generated_report 
                    WHERE created_at >= NOW() - INTERVAL '30 minutes'
                    AND status = 'ready'
                    LIMIT 1
                )
            """)
            result = cursor.fetchone()[0]
        
        elif condition == 'has_recent_reports_10m':
            # تقارير جديدة خلال آخر 10 دقائق (للموجز)
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM generated_report 
                    WHERE created_at >= NOW() - INTERVAL '12 minutes'
                    AND status = 'ready'
                    LIMIT 1
                )
            """)
            result = cursor.fetchone()[0]
        
        elif condition == 'has_recent_reports_15m':
            # تقارير جديدة خلال آخر 15 دقيقة (للنشرة)
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM generated_report 
                    WHERE created_at >= NOW() - INTERVAL '17 minutes'
                    AND status = 'ready'
                    LIMIT 1
                )
            """)
            result = cursor.fetchone()[0]
        
        elif condition == 'has_reports_for_digest':
            # تقارير لم تُضاف لموجز بعد
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM generated_report gr
                    WHERE gr.created_at >= NOW() - INTERVAL '1 hour'
                    AND gr.status = 'ready'
                    AND NOT EXISTS (
                        SELECT 1 FROM digest_reports dr 
                        WHERE dr.report_id = gr.id
                        AND dr.created_at >= NOW() - INTERVAL '1 hour'
                    )
                    LIMIT 1
                )
            """)
            result = cursor.fetchone()[0]
        
        elif condition == 'has_reports_for_bulletin':
            # تقارير لم تُضاف لنشرة بعد
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM generated_report gr
                    WHERE gr.created_at >= NOW() - INTERVAL '2 hours'
                    AND gr.status = 'ready'
                    AND NOT EXISTS (
                        SELECT 1 FROM bulletin_reports br 
                        WHERE br.report_id = gr.id
                        AND br.created_at >= NOW() - INTERVAL '2 hours'
                    )
                    LIMIT 1
                )
            """)
            result = cursor.fetchone()[0]
        
        else:
            # شرط غير معروف - نفترض True
            logger.warning(f"⚠️ Unknown condition: {condition}, assuming True")
            result = True
        
        cursor.close()
        conn.close()
        return result
        
    except Exception as e:
        logger.error(f"❌ Error checking condition '{condition}': {e}")
        if conn:
            conn.close()
        return True  # في حالة الخطأ، نشغل المهمة


def update_task_last_run(task_type: str):
    """Update last_run_at for a task"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE scheduled_tasks 
            SET last_run_at = %s
            WHERE task_type = %s
        """, (datetime.now(timezone.utc), task_type))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error updating last_run: {e}")
        if conn:
            conn.rollback()
            conn.close()


def log_task_execution(task_type: str, status: str, duration: float = 0, 
                       error: str = None, skipped_reason: str = None):
    """Log task execution to scheduled_task_logs"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        # Get task_id
        cursor.execute(
            "SELECT id FROM scheduled_tasks WHERE task_type = %s",
            (task_type,)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return
        
        result_text = skipped_reason if skipped_reason else None
        
        cursor.execute("""
            INSERT INTO scheduled_task_logs 
            (scheduled_task_id, status, execution_time_seconds, result, error_message, executed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (row[0], status, duration, result_text, error, datetime.now(timezone.utc)))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error logging execution: {e}")
        if conn:
            conn.close()


# ============================================
# ⚙️ Job Execution with Condition Check
# ============================================

def execute_task_with_condition(task_type: str, run_condition: str = 'always'):
    """
    Execute a task ONLY if:
    1. It's not already running
    2. Minimum interval has passed
    3. Its condition is met
    """
    # 1️⃣ تحقق من التداخل أولاً
    can_run, reason = can_run_task(task_type)
    if not can_run:
        logger.info(f"⏭️ Skipping {task_type}: {reason}")
        log_task_execution(task_type, 'skipped', 0, skipped_reason=reason)
        return False
    
    # 2️⃣ تحقق من الشرط
    if not check_run_condition(run_condition):
        logger.info(f"⏭️ Skipping {task_type}: condition '{run_condition}' not met")
        log_task_execution(task_type, 'skipped', 0, skipped_reason=f"Condition not met: {run_condition}")
        return False
    
    # 3️⃣ علّم الـ task كـ running
    set_task_running(task_type, True)
    
    # 4️⃣ نفذ المهمة
    job_func = TASK_FUNCTIONS.get(task_type)
    
    if not job_func:
        logger.error(f"❌ No function registered for: {task_type}")
        set_task_running(task_type, False)
        return False
    
    logger.info(f"▶️ Starting: {task_type} (condition: {run_condition} ✓)")
    start_time = datetime.now()
    
    try:
        job_func()
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ {task_type} completed in {duration:.2f}s")
        
        log_task_execution(task_type, 'completed', duration)
        return True
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ {task_type} failed: {e}")
        
        import traceback
        traceback.print_exc()
        
        log_task_execution(task_type, 'failed', duration, str(e))
        return False


def run_parallel_jobs():
    """Run generation jobs in parallel"""
    logger.info("🚀 Starting parallel generation jobs...")
    
    futures = []
    for task_type in PARALLEL_JOBS:
        if task_type in TASK_FUNCTIONS:
            # Get the condition for this task
            condition = get_task_condition(task_type)
            future = executor.submit(execute_task_with_condition, task_type, condition)
            futures.append((task_type, future))
    
    # Wait for all to complete
    for task_type, future in futures:
        try:
            future.result()
        except Exception as e:
            logger.error(f"❌ Parallel job {task_type} error: {e}")
    
    logger.info("✅ All parallel jobs completed")


def run_pipeline():
    """
    🔗 Run the complete pipeline with chaining
    
    Scraping → Clustering → Reports → (Social + Images + Audio + Reels)
    """
    logger.info("=" * 60)
    logger.info("🔗 Starting Pipeline...")
    logger.info("=" * 60)
    
    # Run core pipeline sequentially
    for task_type in PIPELINE_CHAIN:
        condition = get_task_condition(task_type)
        success = execute_task_with_condition(task_type, condition)
        
        if not success:
            logger.warning(f"⚠️ {task_type} failed, but continuing pipeline...")
        
        # Small delay between jobs
        import time
        time.sleep(1)
    
    # Run generation jobs in parallel
    run_parallel_jobs()
    
    logger.info("=" * 60)
    logger.info("✅ Pipeline completed!")
    logger.info("=" * 60)


# ============================================
# ⏰ Scheduler Functions
# ============================================

def parse_cron_pattern(pattern: str) -> Dict:
    """Parse cron pattern to APScheduler CronTrigger args"""
    parts = pattern.strip().split()
    
    if len(parts) != 5:
        logger.warning(f"⚠️ Invalid cron: {pattern}, using */10")
        return {'minute': '*/10'}
    
    return {
        'minute': parts[0],
        'hour': parts[1],
        'day': parts[2],
        'month': parts[3],
        'day_of_week': parts[4]
    }


# ============================================
# 🚀 Scheduler Control
# ============================================

def start_scheduler(run_initial: bool = False):
    """
    Start scheduler - reads ALL tasks from DB including conditions
    """
    try:
        # Register task functions
        register_default_tasks()
        
        # تنظيف الـ tasks اللي علقت
        cleanup_stuck_tasks()
        
        # Get all active tasks from database
        tasks = get_all_active_tasks()
        
        # Find scraping task to determine schedule
        scraping_task = None
        for task in tasks:
            if task['task_type'] == 'scraping':
                scraping_task = task
                break
        
        if scraping_task:
            cron_args = parse_cron_pattern(scraping_task['schedule_pattern'])
        else:
            # Default: every 10 minutes
            cron_args = {'minute': '*/10'}
            logger.warning("⚠️ No scraping task in DB, using default: */10 * * * *")
        
        # Schedule ONLY the pipeline trigger (scraping schedule)
        scheduler.add_job(
            run_pipeline,
            trigger=CronTrigger(**cron_args),
            id='pipeline_trigger',
            name='Pipeline Trigger',
            replace_existing=True
        )
        
        # Start scheduler
        scheduler.start()
        
        logger.info("=" * 60)
        logger.info("⏰ Scheduler started with Job Chaining")
        logger.info("=" * 60)
        logger.info("🔗 Pipeline: Scraping → Clustering → Reports → Generation (+ Reels)")
        logger.info(f"⏱️ Schedule: {scraping_task['schedule_pattern'] if scraping_task else '*/10 * * * *'}")
        logger.info("=" * 60)
        
        # Run initial tasks if requested
        if run_initial:
            logger.info("🚀 Running initial scraping...")
            execute_task_with_condition('scraping', 'always')
            
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")
        raise


def stop_scheduler():
    """Stop the scheduler"""
    try:
        if scheduler.running:
            scheduler.shutdown()
            executor.shutdown(wait=True)
            logger.info("⏰ Scheduler stopped")
    except Exception as e:
        logger.error(f"❌ Error stopping scheduler: {e}")


def reload_schedules():
    """Reload schedules from database"""
    logger.info("🔄 Reloading schedules from database...")
    
    # Remove all existing jobs
    for job in scheduler.get_jobs():
        job.remove()
    
    # Get fresh tasks from DB
    tasks = get_all_active_tasks()
    
    # Find scraping task to determine pipeline schedule
    scraping_task = None
    for task in tasks:
        if task['task_type'] == 'scraping':
            scraping_task = task
            break
    
    if scraping_task:
        cron_args = parse_cron_pattern(scraping_task['schedule_pattern'])
        
        # Schedule the pipeline trigger
        scheduler.add_job(
            run_pipeline,
            trigger=CronTrigger(**cron_args),
            id='pipeline_trigger',
            name='Pipeline Trigger',
            replace_existing=True
        )
        
        logger.info(f"   ✅ Reloaded pipeline: {scraping_task['schedule_pattern']}")
    else:
        logger.warning("⚠️ No scraping task found, pipeline not scheduled")
    
    logger.info("🔄 Reload complete!")


def get_scheduler_status() -> Dict:
    """Get current scheduler status with detailed info"""
    if not scheduler.running:
        return {"status": "stopped", "jobs": []}
    
    # Get tasks info from DB
    tasks = get_all_active_tasks()
    tasks_info = {t['task_type']: t for t in tasks}
    
    jobs_info = []
    for job in scheduler.get_jobs():
        task_data = tasks_info.get(job.id, {})
        jobs_info.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
            "condition": task_data.get('run_condition', 'always'),
            "is_running": task_data.get('is_running', False),
            "last_run": task_data.get('last_run_at').isoformat() if task_data.get('last_run_at') else None
        })
    
    return {
        "status": "running",
        "pipeline": "Scraping → Clustering → Reports → (Social + Images + Audio + Reels)",
        "jobs": jobs_info
    }


# ============================================
# 🔧 Manual Triggers
# ============================================

def run_task_now(task_type: str, ignore_condition: bool = False) -> bool:
    """Manually trigger a specific task"""
    if task_type not in TASK_FUNCTIONS:
        logger.error(f"❌ Unknown task_type: {task_type}")
        return False
    
    logger.info(f"🔧 Manually triggering: {task_type}")
    
    condition = 'always' if ignore_condition else get_task_condition(task_type)
    executor.submit(execute_task_with_condition, task_type, condition)
    return True


def get_task_condition(task_type: str) -> str:
    """Get the run_condition for a task from DB"""
    conn = get_db_connection()
    if not conn:
        return 'always'
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COALESCE(run_condition, 'always') FROM scheduled_tasks WHERE task_type = %s",
            (task_type,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row[0] if row else 'always'
    except:
        return 'always'


def run_all_tasks_now():
    """Manually trigger all active tasks"""
    logger.info("🔧 Manually triggering all tasks...")
    tasks = get_all_active_tasks()
    for task in tasks:
        executor.submit(
            execute_task_with_condition, 
            task['task_type'], 
            task.get('run_condition', 'always')
        )


# ============================================
# 📊 Status Check Functions
# ============================================

def check_all_conditions() -> Dict:
    """Check all conditions and return their status"""
    conditions = [
        'has_unclustered_news',
        'has_clusters_without_reports',
        'has_reports_without_images',
        'has_reports_without_audio',
        'has_reports_without_social',
        'has_recent_reports',
        'has_recent_reports_10m',
        'has_recent_reports_15m',
        'has_reports_for_digest',
        'has_reports_for_bulletin'
    ]
    
    results = {}
    for cond in conditions:
        results[cond] = check_run_condition(cond)
    
    return results


def get_running_tasks() -> list:
    """Get list of currently running tasks"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT task_type, last_run_at 
            FROM scheduled_tasks 
            WHERE is_running = TRUE
        """)
        
        running = []
        for row in cursor.fetchall():
            running.append({
                'task_type': row[0],
                'started_at': row[1]
            })
        
        cursor.close()
        conn.close()
        return running
        
    except Exception as e:
        logger.error(f"❌ Error getting running tasks: {e}")
        if conn:
            conn.close()
        return []


# ============================================
# 🚀 Standalone execution
# ============================================

if __name__ == "__main__":
    import time
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger.info("🚀 Starting Database-Driven Scheduler v2.0")
    logger.info("=" * 70)
    
    # Show current conditions
    logger.info("📋 Current conditions status:")
    conditions = check_all_conditions()
    for cond, status in conditions.items():
        emoji = "✅" if status else "❌"
        logger.info(f"   {emoji} {cond}: {status}")
    
    logger.info("=" * 70)
    
    # Show running tasks (if any stuck)
    running = get_running_tasks()
    if running:
        logger.warning(f"⚠️ Found {len(running)} running tasks (will cleanup):")
        for t in running:
            logger.warning(f"   - {t['task_type']} (started: {t['started_at']})")
    
    start_scheduler(run_initial=False)
    
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("⏹️ Shutting down...")
        stop_scheduler()