#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
⏰ Database-Driven Task Scheduler
الـ Database هي المتحكم الأساسي - كل job له schedule خاص فيه
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import psycopg2
import logging
from datetime import datetime, timezone
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

def register_task(task_type: str, func: Callable):
    """Register a task function"""
    TASK_FUNCTIONS[task_type] = func
    logger.info(f"📝 Registered task: {task_type}")


def register_default_tasks():
    """Register all task functions"""
    
    def scraping_task():
        from app.jobs.scraper_job import scrape_news
        scrape_news()
    
    def processing_pipeline_task():
        from app.jobs.processing_pipeline_job import run_processing_pipeline
        run_processing_pipeline()
    
    # Individual tasks (for manual triggers only)
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
    
    # Register main tasks
    register_task('scraping', scraping_task)
    register_task('processing_pipeline', processing_pipeline_task)
    
    # Register individual tasks (for manual execution)
    register_task('clustering', clustering_task)
    register_task('report_generation', report_generation_task)
    register_task('social_media_generation', social_media_task)
    register_task('image_generation', image_generation_task)
    register_task('audio_generation', audio_generation_task)


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
    """
    Get all active tasks from database
    Returns: List of task dicts with schedule_pattern
    """
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, task_type, schedule_pattern, status
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
                'status': row[4]
            })
        
        cursor.close()
        conn.close()
        return tasks
        
    except Exception as e:
        logger.error(f"❌ Error fetching tasks: {e}")
        if conn:
            conn.close()
        return []


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


def log_task_execution(task_type: str, status: str, duration: float = 0, error: str = None):
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
            return
        
        cursor.execute("""
            INSERT INTO scheduled_task_logs 
            (scheduled_task_id, status, execution_time_seconds, error_message, executed_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (row[0], status, duration, error, datetime.now()))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error logging execution: {e}")
        if conn:
            conn.close()


# ============================================
# ⚙️ Job Execution
# ============================================

def execute_task(task_type: str):
    """
    Execute a single task
    """
    job_func = TASK_FUNCTIONS.get(task_type)
    
    if not job_func:
        logger.error(f"❌ No function registered for: {task_type}")
        return
    
    logger.info(f"▶️ Starting: {task_type}")
    start_time = datetime.now()
    
    try:
        job_func()
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ {task_type} completed in {duration:.2f}s")
        
        update_task_last_run(task_type)
        log_task_execution(task_type, 'completed', duration)
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ {task_type} failed: {e}")
        
        import traceback
        traceback.print_exc()
        
        log_task_execution(task_type, 'failed', duration, str(e))


def create_job_wrapper(task_type: str):
    """Create a wrapper function for a task"""
    def wrapper():
        execute_task(task_type)
    return wrapper


# ============================================
# ⏰ Cron Pattern Parser
# ============================================

def parse_cron_pattern(pattern: str) -> Dict:
    """
    Parse cron pattern to APScheduler CronTrigger args
    Format: minute hour day month day_of_week
    Examples:
        "0 * * * *"     = every hour at :00
        "*/30 * * * *"  = every 30 minutes
        "0 */2 * * *"   = every 2 hours
    """
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
    Start scheduler - reads ALL tasks from DB and schedules each one
    """
    try:
        # Register task functions
        register_default_tasks()
        
        # Get all active tasks from database
        tasks = get_all_active_tasks()
        
        if not tasks:
            logger.warning("⚠️ No active tasks found in database!")
            return
        
        logger.info("=" * 60)
        logger.info("📋 Loading tasks from database...")
        logger.info("=" * 60)
        
        # Schedule each task with its own cron pattern
        for task in tasks:
            task_type = task['task_type']
            schedule = task['schedule_pattern']
            name = task['name']
            
            if task_type not in TASK_FUNCTIONS:
                logger.warning(f"⚠️ Unknown task_type: {task_type}, skipping")
                continue
            
            cron_args = parse_cron_pattern(schedule)
            
            scheduler.add_job(
                create_job_wrapper(task_type),
                trigger=CronTrigger(**cron_args),
                id=task_type,
                name=name,
                replace_existing=True
            )
            
            logger.info(f"   ✅ {name} ({task_type}): {schedule}")
        
        # Start scheduler
        scheduler.start()
        
        logger.info("=" * 60)
        logger.info("⏰ Scheduler started!")
        logger.info("=" * 60)
        
        # Show next run times
        for job in scheduler.get_jobs():
            next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "N/A"
            logger.info(f"   📅 {job.name}: next run at {next_run}")
        
        logger.info("=" * 60)
        
        # Run initial tasks if requested
        if run_initial:
            logger.info("🚀 Running initial scraping...")
            execute_task('scraping')
            
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
    """
    Reload schedules from database (call this after DB changes)
    """
    logger.info("🔄 Reloading schedules from database...")
    
    # Remove all existing jobs
    for job in scheduler.get_jobs():
        job.remove()
    
    # Get fresh tasks from DB
    tasks = get_all_active_tasks()
    
    for task in tasks:
        task_type = task['task_type']
        schedule = task['schedule_pattern']
        name = task['name']
        
        if task_type not in TASK_FUNCTIONS:
            continue
        
        cron_args = parse_cron_pattern(schedule)
        
        scheduler.add_job(
            create_job_wrapper(task_type),
            trigger=CronTrigger(**cron_args),
            id=task_type,
            name=name,
            replace_existing=True
        )
        
        logger.info(f"   ✅ Reloaded: {name} ({schedule})")
    
    logger.info("🔄 Reload complete!")


def get_scheduler_status() -> Dict:
    """Get current scheduler status"""
    if not scheduler.running:
        return {"status": "stopped", "jobs": []}
    
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


# ============================================
# 🔧 Manual Triggers
# ============================================

def run_task_now(task_type: str) -> bool:
    """Manually trigger a specific task"""
    if task_type not in TASK_FUNCTIONS:
        logger.error(f"❌ Unknown task_type: {task_type}")
        return False
    
    logger.info(f"🔧 Manually triggering: {task_type}")
    executor.submit(execute_task, task_type)
    return True


def run_all_tasks_now():
    """Manually trigger all tasks"""
    logger.info("🔧 Manually triggering all tasks...")
    tasks = get_all_active_tasks()
    for task in tasks:
        executor.submit(execute_task, task['task_type'])


# ============================================
# 🚀 Standalone execution
# ============================================

if __name__ == "__main__":
    import time
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger.info("🚀 Starting Database-Driven Scheduler")
    start_scheduler(run_initial=False)
    
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("⏹️ Shutting down...")
        stop_scheduler()