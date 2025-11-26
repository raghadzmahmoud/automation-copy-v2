#!/usr/bin/env python3
"""
📱 Social Media Content Generation Cron Job
Runs every hour to generate social media content for new reports
Usage: python cron/social_media_job.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

# Ensure logs directory exists
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'social_media_job.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def log_task_execution(status: str, items_count: int = 0, error_message: str = None):
    """Log cron job execution"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Get task_id for social_media_generation
        cursor.execute("""
            SELECT id FROM scheduled_tasks 
            WHERE task_type = 'social_media_generation'
        """)
        
        task_id = cursor.fetchone()
        if not task_id:
            logger.warning("Task 'social_media_generation' not found in scheduled_tasks")
            return
        
        task_id = task_id[0]
        
        # Insert log
        cursor.execute("""
            INSERT INTO scheduled_task_logs (
                scheduled_task_id, status, execution_time_seconds,
                result, error_message, executed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (task_id, status, 0.0, str(items_count), error_message, datetime.now()))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error logging task execution: {e}")


def generate_social_media_content():
    """Main social media generation function"""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info(f"Starting social media content generation at {start_time}")
    
    try:
        from app.services.social_media_generator import SocialMediaGenerator
        
        generator = SocialMediaGenerator()
        
        # المنصات المدعومة
        platforms = ['facebook', 'twitter', 'instagram']
        
        logger.info(f"Platforms: {', '.join(platforms)}")
        logger.info(f"Processing limit: 10 reports")
        
        # توليد المحتوى
        stats = generator.generate_for_all_reports(
            platforms=platforms,
            force_update=False,
            limit=10
        )
        
        # Log completion
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Generation completed in {duration:.2f}s")
        logger.info(f"Reports processed: {stats.get('total_reports', 0)}")
        logger.info(f"Content created: {stats.get('success', 0)}")
        logger.info(f"Content updated: {stats.get('updated', 0)}")
        logger.info(f"Skipped: {stats.get('skipped', 0)}")
        logger.info(f"Failed: {stats.get('failed', 0)}")
        
        total_processed = stats.get('total_reports', 0)
        
        if total_processed == 0:
            logger.info("No new reports need social media content")
        
        log_task_execution('completed', total_processed)
        
        generator.close()
        
    except Exception as e:
        logger.error(f"Fatal error in social media generation: {e}")
        import traceback
        traceback.print_exc()
        log_task_execution('failed', 0, str(e))
    
    finally:
        logger.info("=" * 60)


if __name__ == "__main__":
    generate_social_media_content()