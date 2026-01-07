#!/usr/bin/env python3
"""
🎬 Reel Generation Cron Job
Runs every hour to generate Instagram Reels for reports with images and audio
Limited to 4 reports per run
Usage: python cron/reel_generation_job.py
"""
import sys
import os

# Add backend directory to Python path (go up 2 levels from app/jobs/ to backend/)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, backend_dir)

import logging
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

# Ensure logs directory exists
log_dir = os.path.join(backend_dir, 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'reel_generation_job.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def log_task_execution(status: str, items_count: int = 0, error_message: str = None):
    """Log cron job execution"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Get task_id for reel_generation
        cursor.execute("""
            SELECT id FROM scheduled_tasks 
            WHERE task_type = 'reel_generation'
        """)
        
        task_id = cursor.fetchone()
        if not task_id:
            logger.warning("Task 'reel_generation' not found in scheduled_tasks")
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


def generate_reels(report_id: int = None, force_update: bool = False):
    """Main reel generation function
    
    Args:
        report_id: Optional report ID to generate reel for a specific report
        force_update: If True, regenerate even if reel already exists
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info(f"Starting reel generation at {start_time}")
    
    generator = None
    
    try:
        from app.services.generators.reel_generator import ReelGenerator
        
        generator = ReelGenerator()
        
        # If report_id is provided, generate for that specific report
        if report_id:
            logger.info(f"Generating reel for specific report ID: {report_id}")
            result = generator.generate_for_report(
                report_id=report_id,
                force_update=force_update
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Reel generation completed in {duration:.2f}s")
            
            if result.success:
                logger.info(f"✅ Success! Reel URL: {result.reel_url}")
                logger.info(f"   Duration: {result.duration_seconds:.2f}s")
                log_task_execution('completed', 1)
            else:
                logger.error(f"❌ Failed: {result.error_message}")
                log_task_execution('failed', 0, result.error_message)
        else:
            # Get batch size from environment variable
            batch_size = int(os.getenv('MAX_REELS_PER_RUN', 1))
            
            # Generate reels for all reports (original behavior)
            logger.info(f"Processing limit: {batch_size} reports per run")
            
            stats = generator.generate_for_all_reports(
                force_update=force_update,
                limit=batch_size
            )
            
            # Log completion
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Reel generation completed in {duration:.2f}s")
            logger.info(f"Reports processed: {stats.get('total_reports', 0)}")
            logger.info(f"Reels created: {stats.get('success', 0)}")
            logger.info(f"Reels updated: {stats.get('updated', 0)}")
            logger.info(f"Failed: {stats.get('failed', 0)}")
            
            total_processed = stats.get('total_reports', 0)
            
            if total_processed == 0:
                logger.info("No new reports need reel generation")
            
            log_task_execution('completed', total_processed)
        
    except Exception as e:
        logger.error(f"Fatal error in reel generation: {e}")
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
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate Instagram Reels for reports',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate reel for a specific report ID
  python reel_generation_job.py --report-id 123
  
  # Generate reel for a specific report ID (force update if exists)
  python reel_generation_job.py --report-id 123 --force
  
  # Generate reels for all reports (default behavior)
  python reel_generation_job.py
        """
    )
    parser.add_argument(
        '--report-id',
        type=int,
        help='Generate reel for a specific report ID'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force regeneration even if reel already exists'
    )
    
    args = parser.parse_args()
    
    generate_reels(report_id=args.report_id, force_update=args.force)


"""
python3 app/jobs/reel_generation_job.py --report-id 5010 
"""