#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
⏰ Database-Driven Background Task Scheduler
يقرأ الـ jobs من جدول scheduled_tasks في الداتابيس
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import psycopg2
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable

from settings import DB_CONFIG

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = BackgroundScheduler()

# Lock for core jobs only (scraping → clustering → reports)
core_job_lock = threading.Lock()

# Jobs that need sequential execution (use lock)
CORE_JOBS = {'scraping', 'clustering', 'report_generation'}

# Mapping task_type to actual function
TASK_FUNCTIONS: Dict[str, Callable] = {}


def register_task(task_type: str, func: Callable):
    """Register a task function"""
    TASK_FUNCTIONS[task_type] = func
    logger.info(f"📝 Registered task: {task_type}")


def get_db_connection():
    """Create database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return None


def get_scheduled_tasks() -> List[Dict]:
    """
    جلب كل الـ tasks النشطة من الداتابيس
    
    Returns:
        List[Dict]: قائمة الـ scheduled tasks
    """
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                id, name, task_type, schedule_pattern, 
                status, last_run_at, next_run_at
            FROM scheduled_tasks
            WHERE status = 'active'
            ORDER BY id
        """)
        
        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                'id': row[0],
                'name': row[1],
                'task_type': row[2],
                'schedule_pattern': row[3],
                'status': row[4],
                'last_run_at': row[5],
                'next_run_at': row[6]
            })
        
        cursor.close()
        conn.close()
        return tasks
        
    except Exception as e:
        logger.error(f"❌ Error fetching scheduled tasks: {e}")
        if conn:
            conn.close()
        return []


def update_task_run_times(task_id: int, last_run: datetime, next_run: Optional[datetime] = None):
    """
    تحديث أوقات التشغيل في الداتابيس
    
    Args:
        task_id: ID الـ task
        last_run: وقت آخر تشغيل
        next_run: وقت التشغيل القادم (اختياري)
    """
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        if next_run:
            cursor.execute("""
                UPDATE scheduled_tasks 
                SET last_run_at = %s, next_run_at = %s
                WHERE id = %s
            """, (last_run, next_run, task_id))
        else:
            cursor.execute("""
                UPDATE scheduled_tasks 
                SET last_run_at = %s
                WHERE id = %s
            """, (last_run, task_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error updating task run times: {e}")
        if conn:
            conn.rollback()
            conn.close()


def _execute_job(job_func: Callable, job_name: str):
    """Execute job with error handling"""
    logger.info(f"▶️ Starting {job_name}...")
    try:
        job_func()
        logger.info(f"✅ {job_name} completed")
    except Exception as e:
        logger.error(f"❌ {job_name} failed: {e}")
        import traceback
        traceback.print_exc()


def safe_run(task_id: int, task_type: str, job_name: str):
    """
    Run a job safely with optional locking
    
    Args:
        task_id: ID من الداتابيس
        task_type: نوع الـ task
        job_name: اسم الـ job للـ logging
    """
    job_func = TASK_FUNCTIONS.get(task_type)
    
    if not job_func:
        logger.error(f"❌ No function registered for task_type: {task_type}")
        return
    
    start_time = datetime.now(timezone.utc)
    
    # Core jobs use lock, others run parallel
    if task_type in CORE_JOBS:
        logger.info(f"🔄 {job_name} waiting for lock if needed...")
        with core_job_lock:
            _execute_job(job_func, job_name)
    else:
        # Run without lock (parallel execution allowed)
        _execute_job(job_func, job_name)
    
    # Update last_run_at in database
    # Get next run time from scheduler
    job = scheduler.get_job(f"task_{task_id}")
    next_run = job.next_run_time if job else None
    
    update_task_run_times(task_id, start_time, next_run)


def create_job_wrapper(task_id: int, task_type: str, job_name: str):
    """Create a wrapper function for the job"""
    def wrapper():
        safe_run(task_id, task_type, job_name)
    return wrapper


def parse_cron_pattern(pattern: str) -> Dict:
    """
    Parse cron pattern to APScheduler CronTrigger args
    
    Pattern format: minute hour day month day_of_week
    Example: */10 * * * * = every 10 minutes
    Example: 0 * * * * = every hour at minute 0
    """
    parts = pattern.strip().split()
    
    if len(parts) != 5:
        logger.warning(f"⚠️ Invalid cron pattern: {pattern}, using defaults")
        return {'minute': '0', 'hour': '*'}
    
    return {
        'minute': parts[0],
        'hour': parts[1],
        'day': parts[2],
        'month': parts[3],
        'day_of_week': parts[4]
    }


def register_default_tasks():
    """Register default task functions"""
    
    def scraping_task():
        from app.jobs.scraper_job import scrape_news
        scrape_news()
    
    def clustering_task():
        from app.jobs.clustering_job import cluster_news
        cluster_news()
    
    def report_generation_task():
        from app.jobs.reports_job import generate_reports
        generate_reports()
    
    def social_media_generation_task():
        from app.jobs.social_media_job import generate_social_media_content
        generate_social_media_content()
    
    def image_generation_task():
        from app.jobs.image_generation_job import generate_images
        generate_images()
    
    def audio_generation_task():
        from app.jobs.audio_generation_job import generate_audio
        generate_audio()
    
    # Register all tasks
    register_task('scraping', scraping_task)
    register_task('clustering', clustering_task)
    register_task('report_generation', report_generation_task)
    register_task('social_media_generation', social_media_generation_task)
    register_task('image_generation', image_generation_task)
    register_task('audio_generation', audio_generation_task)


def load_jobs_from_database():
    """Load and schedule all active jobs from database"""
    tasks = get_scheduled_tasks()
    
    if not tasks:
        logger.warning("⚠️ No active tasks found in database")
        return 0
    
    loaded_count = 0
    
    for task in tasks:
        try:
            task_id = task['id']
            task_type = task['task_type']
            task_name = task['name']
            schedule_pattern = task['schedule_pattern']
            
            # Check if task function exists
            if task_type not in TASK_FUNCTIONS:
                logger.warning(f"⚠️ No function for task_type: {task_type}, skipping...")
                continue
            
            # Parse cron pattern
            cron_args = parse_cron_pattern(schedule_pattern)
            
            # Create job wrapper
            job_wrapper = create_job_wrapper(task_id, task_type, task_name)
            
            # Add job to scheduler
            scheduler.add_job(
                job_wrapper,
                trigger=CronTrigger(**cron_args),
                id=f"task_{task_id}",
                name=task_name,
                replace_existing=True
            )
            
            loaded_count += 1
            logger.info(f"📌 Loaded: {task_name} ({schedule_pattern})")
            
        except Exception as e:
            logger.error(f"❌ Error loading task {task.get('name')}: {e}")
    
    return loaded_count


def start_scheduler(run_initial_scrape: bool = True):
    """Start the background scheduler"""
    try:
        # Register task functions
        register_default_tasks()
        
        # Load jobs from database
        loaded = load_jobs_from_database()
        
        if loaded == 0:
            logger.error("❌ No jobs loaded from database!")
            return
        
        # Start scheduler
        scheduler.start()
        
        logger.info("=" * 60)
        logger.info("⏰ Scheduler started successfully")
        logger.info(f"📊 Loaded {loaded} jobs from database")
        logger.info("📅 Scheduled Jobs:")
        for job in scheduler.get_jobs():
            logger.info(f"   • {job.name}: {job.next_run_time}")
        logger.info("=" * 60)
        
        # Run initial scrape if requested
        if run_initial_scrape:
            logger.info("🚀 Running initial scraper...")
            if 'scraping' in TASK_FUNCTIONS:
                safe_run(1, 'scraping', 'Initial Scraping')
            
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")
        raise


def stop_scheduler():
    """Stop the background scheduler"""
    try:
        if scheduler.running:
            scheduler.shutdown()
            logger.info("⏰ Scheduler stopped")
    except Exception as e:
        logger.error(f"❌ Error stopping scheduler: {e}")


def reload_jobs():
    """Reload jobs from database (useful after config changes)"""
    logger.info("🔄 Reloading jobs from database...")
    
    # Remove all existing jobs
    for job in scheduler.get_jobs():
        scheduler.remove_job(job.id)
    
    # Load fresh from database
    loaded = load_jobs_from_database()
    logger.info(f"✅ Reloaded {loaded} jobs")
    
    return loaded


def get_scheduler_status() -> Dict:
    """Get scheduler status and jobs info"""
    if not scheduler.running:
        return {
            "status": "stopped",
            "jobs": []
        }
    
    jobs_info = []
    for job in scheduler.get_jobs():
        jobs_info.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })
    
    return {
        "status": "running",
        "jobs": jobs_info
    }


def run_job_now(task_type: str) -> bool:
    """Manually trigger a specific job by task_type"""
    if task_type not in TASK_FUNCTIONS:
        logger.error(f"❌ Unknown task_type: {task_type}")
        return False
    
    logger.info(f"🔧 Manually triggering: {task_type}")
    
    # Find task_id from database
    tasks = get_scheduled_tasks()
    task = next((t for t in tasks if t['task_type'] == task_type), None)
    
    if task:
        safe_run(task['id'], task_type, f"Manual: {task['name']}")
    else:
        # Run without database tracking
        TASK_FUNCTIONS[task_type]()
    
    return True


# ============================================
# Standalone execution
# ============================================

if __name__ == "__main__":
    import time
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger.info("🚀 Starting Database-Driven Background Worker")
    start_scheduler(run_initial_scrape=True)
    
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("⏹️ Shutting down...")
        stop_scheduler()