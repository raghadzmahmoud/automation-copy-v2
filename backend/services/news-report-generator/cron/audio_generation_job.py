#!/usr/bin/env python3
"""
🎙️ Audio Generation Cron Job
Runs every hour to generate audio for new reports
Usage: python cron/audio_generation_job.py
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
        logging.FileHandler(os.path.join(log_dir, 'audio_generation_job.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def log_task_execution(status: str, items_count: int = 0, error_message: str = None):
    """Log cron job execution"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Get task_id for audio_generation
        cursor.execute("""
            SELECT id FROM scheduled_tasks 
            WHERE task_type = 'audio_generation'
        """)
        
        task_id = cursor.fetchone()
        if not task_id:
            logger.warning("Task 'audio_generation' not found in scheduled_tasks")
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


def generate_audio():
    """Main audio generation function"""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info(f"Starting audio generation at {start_time}")
    
    generator = None
    
    try:
        from app.services.audio_generator import AudioGenerator
        
        generator = AudioGenerator()
        
        logger.info(f"Processing limit: 10 reports per run")
        
        # توليد الصوتيات (10 ملفات صوتية كل ساعة)
        # Free tier: 4 million chars/month
        # Our usage with 10/hour: ~9.36 million chars/month
        # ⚠️ This exceeds free tier - will cost ~$85/month
        stats = generator.generate_for_all_reports(
            force_update=False,
            limit=4  # ← 10 تقارير كل ساعة
        )
        
        # Log completion
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Audio generation completed in {duration:.2f}s")
        logger.info(f"Reports processed: {stats.get('total_reports', 0)}")
        logger.info(f"Audio files created: {stats.get('success', 0)}")
        logger.info(f"Audio files updated: {stats.get('updated', 0)}")
        logger.info(f"Failed: {stats.get('failed', 0)}")
        
        total_processed = stats.get('total_reports', 0)
        
        if total_processed == 0:
            logger.info("No new reports need audio generation")
        
        log_task_execution('completed', total_processed)
        
    except Exception as e:
        logger.error(f"Fatal error in audio generation: {e}")
        import traceback
        traceback.print_exc()
        log_task_execution('failed', 0, str(e))
    
    finally:
        if generator:
            try:
                generator.close()
            except:
                pass
        logger.info("=" * 60)


if __name__ == "__main__":
    generate_audio()