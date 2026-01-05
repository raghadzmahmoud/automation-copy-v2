#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Multi-Threaded Task Scheduler
═══════════════════════════════════════════════════════════════
Each task runs independently in its own thread with fixed intervals
When a task finishes, it starts a timer to run again after its interval
No database dependency for task configuration
═══════════════════════════════════════════════════════════════
"""

import certifi
import os
import psycopg2
import logging
import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable
from settings import DB_CONFIG
import sys
import signal
import traceback

# Job imports
from app.jobs.scraper_job import scrape_news
from app.jobs.clustering_job import cluster_news
from app.jobs.reports_job import generate_reports
from app.jobs.image_generation_job import generate_images
from app.jobs.audio_generation_job import generate_audio
from app.jobs.bulletin_digest_job import generate_bulletin_job, generate_digest_job
from app.jobs.social_media_job import generate_social_media_content
from app.jobs.social_media_image_job import generate_social_media_images
from app.jobs.reel_generation_job import generate_reels

# Set SSL certificate environment variable
os.environ["SSL_CERT_FILE"] = certifi.where()

logger = logging.getLogger(__name__)


# ============================================
# Configuration
# ============================================

# Task configuration: function and interval in one place
TASKS = {
    'scraping': {
        'func': scrape_news,
        'interval': 600,              # 10 minutes
    },
    'clustering': {
        'func': cluster_news,
        'interval': 1000,              
    },
    'report_generation': {
        'func': generate_reports,
        'interval': 1300,             
    },
    'image_generation': {
        'func': generate_images,
        'interval': 1800,             
    },
    'audio_generation': {
        'func': generate_audio,
        'interval': 1800,             
    },
    'bulletin_generation': {
        'func': generate_bulletin_job,
        'interval': 7200,            
    },
    'digest_generation': {
        'func': generate_digest_job,
        'interval': 7200,             
    },
    'social_media_generation': {
        'func': generate_social_media_content,
        'interval': 1800,             
    },
    'social_media_image_generation': {
        'func': generate_social_media_images,
        'interval': 2000,             
    },
    'reel_generation': {
        'func': generate_reels,
        'interval': 2000,             
    }
 
}

# Task functions mapping (populated from TASKS)
TASK_FUNCTIONS: Dict[str, Callable] = {}

# Scheduler state
scheduler_running = False
task_threads: Dict[str, threading.Thread] = {}
task_stop_flags: Dict[str, threading.Event] = {}
task_last_run: Dict[str, datetime] = {}
scheduler_lock = threading.Lock()


def register_all_tasks():
    """Register all task functions from TASKS configuration"""
    for task_type, task_config in TASKS.items():
        TASK_FUNCTIONS[task_type] = task_config['func']
        logger.info(f"Registered: {task_type}")


# ============================================
# Database Functions (for logging only)
# ============================================

def get_db_connection():
    """Create database connection"""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None


def update_task_last_run(task_type: str):
    """Update last_run_at for a task (optional, for logging)"""
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
        # Silently fail if table doesn't exist or task not in DB
        if conn:
            conn.rollback()
            conn.close()


def log_task_execution(task_type: str, status: str, duration: float = 0, error: str = None):
    """Log task execution (optional, for logging)"""
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
        # Silently fail if table doesn't exist
        if conn:
            conn.close()


# ============================================
# Task Execution
# ============================================

def execute_task(task_type: str) -> Dict:
    """
    Execute a single task
    Returns: {'success': bool, 'duration': float, 'error': str|None}
    """
    if task_type not in TASK_FUNCTIONS:
        logger.error(f"Unknown task: {task_type}")
        return {'success': False, 'duration': 0, 'error': 'Unknown task'}
    
    logger.info(f"[{task_type}] Starting execution...")
    start_time = datetime.now()
    
    try:
        # Execute the task
        result = TASK_FUNCTIONS[task_type]()
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"[{task_type}] Completed in {duration:.2f}s")
        
        # Update database (optional, for logging)
        update_task_last_run(task_type)
        log_task_execution(task_type, 'completed', duration)
        
        # Update last run time in memory
        with scheduler_lock:
            task_last_run[task_type] = datetime.now(timezone.utc)
        
        return {
            'success': True,
            'duration': duration,
            'error': None,
            'result': result
        }
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        error_msg = str(e)
        logger.error(f"[{task_type}] Failed: {error_msg}")
        
        traceback.print_exc()
        
        log_task_execution(task_type, 'failed', duration, error_msg)
        
        return {
            'success': False,
            'duration': duration,
            'error': error_msg
        }


# ============================================
# Task Thread Functions
# ============================================

def task_thread_loop(task_type: str, interval_seconds: int):
    """
    Main loop for a single task thread
    Pattern: Run task -> Wait interval -> Repeat
    When task finishes, timer starts immediately for next run
    """
    logger.info(f"[{task_type}] Thread started with interval: {interval_seconds}s ({interval_seconds//60}min)")
    
    stop_flag = task_stop_flags.get(task_type)
    if not stop_flag:
        logger.error(f"[{task_type}] No stop flag found!")
        return
    
    while not stop_flag.is_set():
        try:
            # Execute the task
            execute_task(task_type)
            
            # After task finishes, wait for interval before next run
            # Timer starts immediately after task completion
            logger.info(f"[{task_type}] Waiting {interval_seconds}s ({interval_seconds//60}min) until next run...")
            
            # Wait for interval (checking stop flag every second)
            for _ in range(interval_seconds):
                if stop_flag.is_set():
                    logger.info(f"[{task_type}] Thread stopped")
                    return
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"[{task_type}] Thread error: {e}")
            traceback.print_exc()
            
            # Wait 30 seconds before retrying on error
            logger.info(f"[{task_type}] Retrying in 30 seconds...")
            for _ in range(30):
                if stop_flag.is_set():
                    return
                time.sleep(1)
    
    logger.info(f"[{task_type}] Thread ended")


# ============================================
# Scheduler Control
# ============================================

def start_scheduler():
    """Start the multi-threaded scheduler"""
    global scheduler_running, task_threads, task_stop_flags
    
    if scheduler_running:
        logger.warning("Scheduler already running!")
        return False
    
    logger.info("=" * 70)
    logger.info("Starting Multi-Threaded Task Scheduler...")
    logger.info("=" * 70)
    
    # Register all tasks
    register_all_tasks()
    
    if not TASK_FUNCTIONS:
        logger.warning("No tasks registered!")
        return False
    
    # Initialize task threads for all registered tasks
    scheduler_running = True
    
    for task_type, task_config in TASKS.items():
        # Get interval and function from TASKS configuration
        interval = task_config['interval']
        task_func = task_config['func']
        
        # Create stop flag for this task
        task_stop_flags[task_type] = threading.Event()
        
        # Start thread for this task
        thread = threading.Thread(
            target=task_thread_loop,
            args=(task_type, interval),
            daemon=True,
            name=f"Task-{task_type}"
        )
        thread.start()
        task_threads[task_type] = thread
        
        logger.info(f"[{task_type}] Started (interval: {interval}s = {interval//60}min)")
    
    logger.info("=" * 70)
    logger.info(f"Scheduler started with {len(task_threads)} task threads")
    logger.info("=" * 70)
    
    return True


def stop_scheduler():
    """Stop the scheduler gracefully"""
    global scheduler_running, task_threads, task_stop_flags
    
    if not scheduler_running:
        logger.warning("Scheduler not running!")
        return False
    
    logger.info("Stopping scheduler...")
    
    # Set all stop flags
    for task_type, stop_flag in task_stop_flags.items():
        logger.info(f"[{task_type}] Stopping...")
        stop_flag.set()
    
    # Wait for threads to finish (with timeout)
    for task_type, thread in task_threads.items():
        thread.join(timeout=30)
        if thread.is_alive():
            logger.warning(f"[{task_type}] Thread did not stop within timeout")
        else:
            logger.info(f"[{task_type}] Thread stopped")
    
    scheduler_running = False
    task_threads.clear()
    task_stop_flags.clear()
    task_last_run.clear()
    
    logger.info("Scheduler stopped!")
    return True


def get_scheduler_status() -> Dict:
    """Get current scheduler status"""
    with scheduler_lock:
        task_statuses = {}
        for task_type in task_threads.keys():
            thread = task_threads.get(task_type)
            stop_flag = task_stop_flags.get(task_type)
            interval = TASKS.get(task_type, {}).get('interval', 3600)
            
            task_statuses[task_type] = {
                'running': thread.is_alive() if thread else False,
                'interval_seconds': interval,
                'interval_minutes': interval // 60,
                'last_run': task_last_run.get(task_type),
                'stopped': stop_flag.is_set() if stop_flag else True
            }
    
    return {
        'scheduler_running': scheduler_running,
        'active_tasks': len(task_threads),
        'tasks': task_statuses
    }


# ============================================
# Manual Controls
# ============================================

def run_single_task(task_type: str) -> Dict:
    """Manually run a single task"""
    if task_type not in TASK_FUNCTIONS:
        register_all_tasks()
    
    if task_type not in TASK_FUNCTIONS:
        return {'success': False, 'duration': 0, 'error': 'Task not registered'}
    
    return execute_task(task_type)


# ============================================
# Main
# ============================================

if __name__ == "__main__":
    # Setup logging for production
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f'{log_dir}/worker.log', encoding='utf-8')
        ]
    )
    
    logger.info("=" * 70)
    logger.info("Multi-Threaded Task Scheduler")
    logger.info("=" * 70)
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info("=" * 70)
    
    # Graceful shutdown handler
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal, stopping scheduler...")
        stop_scheduler()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        start_scheduler()
        
        # Keep main thread alive
        logger.info("Scheduler is running. Press Ctrl+C to stop.")
        while scheduler_running:
            time.sleep(1)
            
            # Check if any task thread has unexpectedly stopped
            with scheduler_lock:
                dead_threads = []
                for task_type, thread in task_threads.items():
                    stop_flag = task_stop_flags.get(task_type, threading.Event())
                    if not thread.is_alive() and not stop_flag.is_set():
                        dead_threads.append(task_type)
            
            if dead_threads:
                logger.warning(f"Dead threads detected: {dead_threads}")
                # Could implement auto-restart here if needed
            
    except KeyboardInterrupt:
        logger.info("\nKeyboard interrupt received")
        stop_scheduler()
    except Exception as e:
        logger.error(f"Scheduler crashed: {e}")
        traceback.print_exc()
        stop_scheduler()
        sys.exit(1)
