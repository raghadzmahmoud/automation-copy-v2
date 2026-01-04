#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔄 Continuous Pipeline Scheduler
═══════════════════════════════════════════════════════════════
بسيط ومباشر:
- كل task تخلص → اللي بعدها تبدأ
- لما يخلص الكل → نعيد من البداية
- لا اعتماد على مواعيد cron
═══════════════════════════════════════════════════════════════
"""
import certifi
import os
os.environ["SSL_CERT_FILE"] = certifi.where()

import psycopg2
import logging
import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable

from settings import DB_CONFIG

logger = logging.getLogger(__name__)

# ============================================
# 📋 Pipeline Configuration
# ============================================

# ترتيب المهام في الـ Pipeline
PIPELINE_ORDER = [
    'scraping',           # 1. سحب الأخبار
    'clustering',         # 2. تجميع الأخبار
    'report_generation',  # 3. توليد التقارير
    'image_generation',   # 4. توليد الصور
    'audio_generation',   # 5. توليد الصوت
    'bulletin_generation', # 6. النشرة
    'digest_generation',  # 7. الموجز
    'social_media_generation',  # 8. سوشيال ميديا (اختياري)
]

# الفترة بين كل دورة pipeline كاملة (بالثواني)
PIPELINE_COOLDOWN = 60  # دقيقة واحدة بعد ما يخلص الكل

# Task functions mapping
TASK_FUNCTIONS: Dict[str, Callable] = {}

# Pipeline state
pipeline_running = False
pipeline_thread = None
stop_flag = threading.Event()


# ============================================
# 📝 Task Registration
# ============================================

def register_task(task_type: str, func: Callable):
    """Register a task function"""
    TASK_FUNCTIONS[task_type] = func
    logger.info(f"📝 Registered: {task_type}")


def register_all_tasks():
    """Register all task functions"""
    
    def scraping_task():
        from app.jobs.scraper_job import scrape_news
        return scrape_news()
    
    def clustering_task():
        from app.jobs.clustering_job import cluster_news
        return cluster_news()
    
    def report_generation_task():
        from app.jobs.reports_job import generate_reports
        return generate_reports()
    
    def image_generation_task():
        from app.jobs.image_generation_job import generate_images
        return generate_images()
    
    def audio_generation_task():
        from app.jobs.audio_generation_job import generate_audio
        return generate_audio()
    
    def bulletin_task():
        from app.jobs.bulletin_digest_job import generate_bulletin_job
        return generate_bulletin_job()
    
    def digest_task():
        from app.jobs.bulletin_digest_job import generate_digest_job
        return generate_digest_job()
    
    def social_media_task():
        from app.jobs.social_media_job import generate_social_media_content
        return generate_social_media_content()
    
    register_task('scraping', scraping_task)
    register_task('clustering', clustering_task)
    register_task('report_generation', report_generation_task)
    register_task('image_generation', image_generation_task)
    register_task('audio_generation', audio_generation_task)
    register_task('bulletin_generation', bulletin_task)
    register_task('digest_generation', digest_task)
    register_task('social_media_generation', social_media_task)


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


def get_active_tasks_from_db() -> List[str]:
    """
    Get ordered list of active tasks from database
    Returns tasks in execution order
    """
    conn = get_db_connection()
    if not conn:
        return PIPELINE_ORDER  # fallback to default
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT task_type 
            FROM scheduled_tasks
            WHERE status = 'active'
            ORDER BY COALESCE(execution_order, 99), id
        """)
        
        active_tasks = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        
        # Filter to only tasks we have functions for
        return [t for t in active_tasks if t in TASK_FUNCTIONS]
        
    except Exception as e:
        logger.error(f"❌ Error fetching tasks: {e}")
        if conn:
            conn.close()
        return PIPELINE_ORDER


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
    """Log task execution"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id FROM scheduled_tasks WHERE task_type = %s",
            (task_type,)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return
        
        cursor.execute("""
            INSERT INTO scheduled_task_logs 
            (scheduled_task_id, status, execution_time_seconds, error_message, executed_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (row[0], status, duration, error, datetime.now(timezone.utc)))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error logging: {e}")
        if conn:
            conn.close()


def log_pipeline_cycle(cycle_number: int, total_duration: float, results: Dict):
    """Log complete pipeline cycle"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        # Get or create pipeline task
        cursor.execute(
            "SELECT id FROM scheduled_tasks WHERE task_type = 'processing_pipeline'"
        )
        row = cursor.fetchone()
        if row:
            cursor.execute("""
                INSERT INTO scheduled_task_logs 
                (scheduled_task_id, status, execution_time_seconds, result, executed_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (row[0], 'completed', total_duration, 
                  f"Cycle #{cycle_number}: {len(results)} tasks", 
                  datetime.now(timezone.utc)))
            
            conn.commit()
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error logging cycle: {e}")
        if conn:
            conn.close()


# ============================================
# ⚙️ Task Execution
# ============================================

def execute_task(task_type: str) -> Dict:
    """
    Execute a single task
    Returns: {'success': bool, 'duration': float, 'error': str|None}
    """
    if task_type not in TASK_FUNCTIONS:
        logger.error(f"❌ Unknown task: {task_type}")
        return {'success': False, 'duration': 0, 'error': 'Unknown task'}
    
    logger.info(f"▶️ Starting: {task_type}")
    start_time = datetime.now()
    
    try:
        # Execute the task
        result = TASK_FUNCTIONS[task_type]()
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ {task_type} completed in {duration:.2f}s")
        
        # Update database
        update_task_last_run(task_type)
        log_task_execution(task_type, 'completed', duration)
        
        return {
            'success': True,
            'duration': duration,
            'error': None,
            'result': result
        }
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        error_msg = str(e)
        logger.error(f"❌ {task_type} failed: {error_msg}")
        
        import traceback
        traceback.print_exc()
        
        log_task_execution(task_type, 'failed', duration, error_msg)
        
        return {
            'success': False,
            'duration': duration,
            'error': error_msg
        }


# ============================================
# 🔄 Pipeline Execution
# ============================================

def run_pipeline_cycle(cycle_number: int) -> Dict:
    """
    Run one complete pipeline cycle
    All tasks execute in sequence
    """
    logger.info("=" * 70)
    logger.info(f"🔄 Pipeline Cycle #{cycle_number} starting...")
    logger.info("=" * 70)
    
    cycle_start = datetime.now()
    results = {}
    
    # Get active tasks in order
    tasks = get_active_tasks_from_db()
    
    # Filter out processing_pipeline (we don't want to run the old one)
    tasks = [t for t in tasks if t != 'processing_pipeline']
    
    logger.info(f"📋 Tasks to execute: {' → '.join(tasks)}")
    logger.info("-" * 70)
    
    for i, task_type in enumerate(tasks, 1):
        # Check if we should stop
        if stop_flag.is_set():
            logger.info("⏹️ Pipeline stopped by user")
            break
        
        logger.info(f"[{i}/{len(tasks)}] {task_type}")
        
        # Execute task
        result = execute_task(task_type)
        results[task_type] = result
        
        # Small delay between tasks to prevent overwhelming
        if result['success'] and i < len(tasks):
            time.sleep(2)
    
    # Calculate total duration
    total_duration = (datetime.now() - cycle_start).total_seconds()
    
    # Log cycle completion
    log_pipeline_cycle(cycle_number, total_duration, results)
    
    # Print summary
    logger.info("=" * 70)
    logger.info(f"🏁 Pipeline Cycle #{cycle_number} completed in {total_duration:.2f}s")
    logger.info("-" * 70)
    
    successful = sum(1 for r in results.values() if r['success'])
    failed = len(results) - successful
    
    for task, result in results.items():
        status = "✅" if result['success'] else "❌"
        logger.info(f"   {status} {task}: {result['duration']:.2f}s")
    
    logger.info("-" * 70)
    logger.info(f"   Total: {successful} succeeded, {failed} failed")
    logger.info("=" * 70)
    
    return {
        'cycle': cycle_number,
        'duration': total_duration,
        'results': results,
        'successful': successful,
        'failed': failed
    }


def pipeline_loop():
    """
    Main pipeline loop - runs continuously
    """
    global pipeline_running
    
    cycle_number = 0
    
    while not stop_flag.is_set():
        cycle_number += 1
        
        try:
            # Run one cycle
            run_pipeline_cycle(cycle_number)
            
            # Cooldown before next cycle
            if not stop_flag.is_set():
                logger.info(f"😴 Cooling down for {PIPELINE_COOLDOWN}s before next cycle...")
                
                # Sleep in small chunks to allow quick stop
                for _ in range(PIPELINE_COOLDOWN):
                    if stop_flag.is_set():
                        break
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"❌ Pipeline cycle error: {e}")
            import traceback
            traceback.print_exc()
            
            # Wait before retrying
            time.sleep(30)
    
    pipeline_running = False
    logger.info("⏹️ Pipeline loop ended")


# ============================================
# 🚀 Pipeline Control
# ============================================

def start_pipeline():
    """Start the continuous pipeline"""
    global pipeline_running, pipeline_thread, stop_flag
    
    if pipeline_running:
        logger.warning("⚠️ Pipeline already running!")
        return False
    
    logger.info("🚀 Starting Continuous Pipeline...")
    
    # Register tasks
    register_all_tasks()
    
    # Show registered tasks
    logger.info(f"📋 Registered tasks: {list(TASK_FUNCTIONS.keys())}")
    
    # Reset stop flag
    stop_flag.clear()
    
    # Start pipeline thread
    pipeline_running = True
    pipeline_thread = threading.Thread(target=pipeline_loop, daemon=True)
    pipeline_thread.start()
    
    logger.info("✅ Pipeline started!")
    return True


def stop_pipeline():
    """Stop the pipeline gracefully"""
    global pipeline_running, stop_flag
    
    if not pipeline_running:
        logger.warning("⚠️ Pipeline not running!")
        return False
    
    logger.info("⏹️ Stopping pipeline...")
    stop_flag.set()
    
    # Wait for thread to finish
    if pipeline_thread:
        pipeline_thread.join(timeout=30)
    
    pipeline_running = False
    logger.info("✅ Pipeline stopped!")
    return True


def get_pipeline_status() -> Dict:
    """Get current pipeline status"""
    return {
        'running': pipeline_running,
        'tasks': list(TASK_FUNCTIONS.keys()),
        'order': PIPELINE_ORDER,
        'cooldown': PIPELINE_COOLDOWN
    }


# ============================================
# 🔧 Manual Controls
# ============================================

def run_single_task(task_type: str) -> Dict:
    """Manually run a single task"""
    if task_type not in TASK_FUNCTIONS:
        # Try to register if not registered
        register_all_tasks()
    
    return execute_task(task_type)


def run_single_cycle() -> Dict:
    """Manually run a single pipeline cycle"""
    register_all_tasks()
    return run_pipeline_cycle(0)


# ============================================
# 🚀 Main
# ============================================

if __name__ == "__main__":
    import signal
    import sys
    import os
    
    # Setup logging for production
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),  # Log to stdout for Render
            logging.FileHandler('app/logs/worker.log', encoding='utf-8')
        ]
    )
    
    logger.info("=" * 70)
    logger.info("🔄 Continuous Pipeline Scheduler (Production)")
    logger.info("=" * 70)
    logger.info(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"📋 Pipeline order: {' → '.join(PIPELINE_ORDER)}")
    logger.info(f"⏱️ Cooldown between cycles: {PIPELINE_COOLDOWN}s")
    logger.info("=" * 70)
    
    # Graceful shutdown handler
    def signal_handler(signum, frame):
        logger.info("⏹️ Received shutdown signal, stopping pipeline...")
        stop_pipeline()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        start_pipeline()
        
        # Keep main thread alive
        logger.info("✅ Worker is running. Press Ctrl+C to stop.")
        while pipeline_running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("\n⏹️ Keyboard interrupt received")
        stop_pipeline()
    except Exception as e:
        logger.error(f"❌ Worker crashed: {e}")
        import traceback
        traceback.print_exc()
        stop_pipeline()
        sys.exit(1)