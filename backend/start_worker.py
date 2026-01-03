#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
⏰ Database-Driven Background Task Scheduler with Job Chaining
كل job لما يخلص يشغّل اللي بعده
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import psycopg2
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor

from settings import DB_CONFIG

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = BackgroundScheduler()

# Thread pool for parallel jobs
parallel_executor = ThreadPoolExecutor(max_workers=3)

# Mapping task_type to actual function
TASK_FUNCTIONS: Dict[str, Callable] = {}


# ============================================
# 🔗 Job Chain Definition
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


# ============================================
# 🗄️ Database Functions
# ============================================

def get_db_connection():
    """Create database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return None


def get_task_by_type(task_type: str) -> Optional[Dict]:
    """Get task info from database by task_type"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, task_type, schedule_pattern, status
            FROM scheduled_tasks
            WHERE task_type = %s AND status = 'active'
            LIMIT 1
        """, (task_type,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'task_type': row[2],
                'schedule_pattern': row[3],
                'status': row[4]
            }
        return None
        
    except Exception as e:
        logger.error(f"❌ Error fetching task: {e}")
        if conn:
            conn.close()
        return None


def get_scraping_task() -> Optional[Dict]:
    """Get scraping task (the only scheduled one)"""
    return get_task_by_type('scraping')


def update_task_run_times(task_type: str, last_run: datetime, next_run: Optional[datetime] = None):
    """Update run times in database"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        if next_run:
            cursor.execute("""
                UPDATE scheduled_tasks 
                SET last_run_at = %s, next_run_at = %s
                WHERE task_type = %s
            """, (last_run, next_run, task_type))
        else:
            cursor.execute("""
                UPDATE scheduled_tasks 
                SET last_run_at = %s, next_run_at = NULL
                WHERE task_type = %s
            """, (last_run, task_type))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error updating task run times: {e}")
        if conn:
            conn.rollback()
            conn.close()


# ============================================
# 🔗 Job Chaining Logic
# ============================================

def execute_job(task_type: str) -> bool:
    """
    Execute a single job
    
    Returns:
        bool: True if successful
    """
    job_func = TASK_FUNCTIONS.get(task_type)
    
    if not job_func:
        logger.error(f"❌ No function registered for: {task_type}")
        return False
    
    task = get_task_by_type(task_type)
    job_name = task['name'] if task else task_type
    
    logger.info(f"▶️ Starting {job_name}...")
    start_time = datetime.now(timezone.utc)
    
    try:
        job_func()
        logger.info(f"✅ {job_name} completed")
        update_task_run_times(task_type, start_time)
        return True
        
    except Exception as e:
        logger.error(f"❌ {job_name} failed: {e}")
        import traceback
        traceback.print_exc()
        update_task_run_times(task_type, start_time)
        return False


def run_parallel_jobs():
    """Run generation jobs in parallel"""
    logger.info("🚀 Starting parallel generation jobs...")
    
    futures = []
    for task_type in PARALLEL_JOBS:
        if task_type in TASK_FUNCTIONS:
            future = parallel_executor.submit(execute_job, task_type)
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
        success = execute_job(task_type)
        
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
# 📋 Task Registration
# ============================================

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
    
    def reel_generation_task():
        from app.jobs.reel_generation_job import generate_reels
        generate_reels()
    
    # Register all tasks
    register_task('scraping', scraping_task)
    register_task('clustering', clustering_task)
    register_task('report_generation', report_generation_task)
    register_task('social_media_generation', social_media_generation_task)
    register_task('image_generation', image_generation_task)
    register_task('audio_generation', audio_generation_task)
    register_task('reel_generation', reel_generation_task)


# ============================================
# ⏰ Scheduler Functions
# ============================================

def parse_cron_pattern(pattern: str) -> Dict:
    """Parse cron pattern to APScheduler CronTrigger args"""
    parts = pattern.strip().split()
    
    if len(parts) != 5:
        logger.warning(f"⚠️ Invalid cron pattern: {pattern}, using default */10")
        return {'minute': '*/10'}
    
    return {
        'minute': parts[0],
        'hour': parts[1],
        'day': parts[2],
        'month': parts[3],
        'day_of_week': parts[4]
    }


def start_scheduler(run_initial: bool = True):
    """Start the background scheduler"""
    try:
        # Register task functions
        register_default_tasks()
        
        # Get scraping schedule from database
        scraping_task = get_scraping_task()
        
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
        
        # Schedule reel generation to run every hour independently
        scheduler.add_job(
            execute_job,
            args=['reel_generation'],
            trigger=CronTrigger(minute=0),  # Every hour at minute 0
            id='reel_generation_hourly',
            name='Reel Generation (Hourly)',
            replace_existing=True
        )
        
        # Start scheduler
        scheduler.start()
        
        logger.info("=" * 60)
        logger.info("⏰ Scheduler started with Job Chaining")
        logger.info("=" * 60)
        logger.info("🔗 Pipeline: Scraping → Clustering → Reports → Generation")
        logger.info(f"⏱️ Schedule: {scraping_task['schedule_pattern'] if scraping_task else '*/10 * * * *'}")
        logger.info("🎬 Reel Generation: Every hour (0 * * * *)")
        logger.info("=" * 60)
        
        # Run initial pipeline if requested
        if run_initial:
            logger.info("🚀 Running initial pipeline...")
            run_pipeline()
            
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")
        raise


def stop_scheduler():
    """Stop the background scheduler"""
    try:
        if scheduler.running:
            scheduler.shutdown()
            parallel_executor.shutdown(wait=True)
            logger.info("⏰ Scheduler stopped")
    except Exception as e:
        logger.error(f"❌ Error stopping scheduler: {e}")


def get_scheduler_status() -> Dict:
    """Get scheduler status"""
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
        "pipeline": "Scraping → Clustering → Reports → (Social + Images + Audio + Reels)",
        "jobs": jobs_info
    }


# ============================================
# 🔧 Manual Triggers
# ============================================

def run_job_now(task_type: str) -> bool:
    """Manually trigger a specific job"""
    if task_type not in TASK_FUNCTIONS:
        logger.error(f"❌ Unknown task_type: {task_type}")
        return False
    
    logger.info(f"🔧 Manually triggering: {task_type}")
    return execute_job(task_type)


def run_pipeline_now():
    """Manually trigger the full pipeline"""
    logger.info("🔧 Manually triggering full pipeline...")
    run_pipeline()


def run_only_scraping():
    """Run only scraping (without chaining)"""
    logger.info("🔧 Running only scraping...")
    return execute_job('scraping')


# ============================================
# 🚀 Standalone execution
# ============================================

if __name__ == "__main__":
    import time
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger.info("🚀 Starting Job Chaining Scheduler")
    start_scheduler(run_initial=True)
    
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("⏹️ Shutting down...")
        stop_scheduler()