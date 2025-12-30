#!/usr/bin/env python3
"""
Report Generation Cron Job
Runs every 2 hours to generate automated reports
Usage: python cron/reports_job.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timedelta
import psycopg2
from settings import DB_CONFIG
from app.config.user_config import user_config

# Ensure logs directory exists at project root
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # Use absolute path for log file
        logging.FileHandler(os.path.join(log_dir, 'reports_job.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def log_task_execution(status: str, items_count: int = 0, error_message: str = None):
    """Log cron job execution"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Get task_id for report_generation
        cursor.execute("""
            SELECT id FROM scheduled_tasks 
            WHERE task_type = 'report_generation'
        """)
        
        task_id = cursor.fetchone()
        if not task_id:
            logger.warning("Task with task_type='report_generation' not found in scheduled_tasks")
            return
        
        task_id = task_id[0]
        
        # Insert log (adapted to schema: scheduled_task_logs has
        # scheduled_task_id, status, execution_time_seconds, result, error_message, executed_at)
        cursor.execute("""
            INSERT INTO scheduled_task_logs (scheduled_task_id, status, execution_time_seconds, result, error_message, executed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (task_id, status, 0.0, str(items_count), error_message, datetime.now()))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error logging task execution: {e}")


def generate_reports():
    """Main report generation function"""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info(f"Starting report generation job at {start_time}")

    # Check if report generation is enabled
    if not user_config.auto_generate_reports:
        logger.info("Automatic report generation is disabled in configuration")
        return

    try:
        _extracted_from_generate_reports_13(start_time)
    except Exception as e:
        logger.error(f"Fatal error in report generation job: {e}")
        log_task_execution('failed', 0, str(e))

    finally:
        logger.info("=" * 60)


# TODO Rename this here and in `generate_reports`
def _extracted_from_generate_reports_13(start_time):
    from app.services.generators.reporter import ReportGenerator
    reporter = ReportGenerator()

    # ✅ إضافة check_updates_hours
    stats = reporter.generate_reports_for_clusters(
        skip_existing=True,
        check_updates_hours=user_config.report_generation_interval_hours  # ← ساعة واحدة
    )


    total_processed = stats.get('total', 0)
    total_reports_generated = stats.get('success', 0)

    # Log completion
    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"Report generation completed in {duration:.2f}s")
    logger.info(f"Total reports generated: {total_reports_generated}")
    logger.info(f"Total clusters processed: {total_processed}")

    if total_processed == 0:
        logger.info("No new clusters to generate reports for.")

    log_task_execution('completed', total_processed)


if __name__ == "__main__":
    generate_reports()