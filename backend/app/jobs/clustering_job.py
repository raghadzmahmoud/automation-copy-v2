#!/usr/bin/env python3
"""
News Clustering Cron Job
Runs every hour to cluster similar news articles
Usage: python cron/clustering_job.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timedelta, timezone
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
        logging.FileHandler(os.path.join(log_dir, 'clustering_job.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def log_task_execution(status: str, items_count: int = 0, error_message: str = None):
    """Log cron job execution"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Get task_id for news_clustering
        cursor.execute("""
            SELECT id FROM scheduled_tasks 
            WHERE task_type = 'clustering'
        """)
        
        task_id = cursor.fetchone()
        if not task_id:
            logger.warning("Task with task_type='clustering' not found in scheduled_tasks")
            return
        
        task_id = task_id[0]
        
        # Insert log (adapt to schema)
        cursor.execute("""
            INSERT INTO scheduled_task_logs (scheduled_task_id, status, execution_time_seconds, result, error_message, executed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (task_id, status, 0.0, str(items_count), error_message, datetime.now()))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error logging task execution: {e}")


def cluster_news():
    """Main clustering function"""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info(f"Starting news clustering job at {start_time}")
    
    # Check if clustering is enabled
    if not user_config.clustering_enabled:
        logger.info("Clustering is disabled in configuration")
        return
    
    try:
        # Get configuration
        time_window_days = user_config.clustering_time_window_hours / 24.0

        logger.info(f"Time window: {user_config.clustering_time_window_hours} hours")
        logger.info(f"Minimum similarity: {user_config.clustering_min_similarity}")
        
        # Import clustering service (lazy import)
        from app.services.processing.clustering import NewsClusterer
        clusterer = NewsClusterer()
        
        # Perform incremental clustering
        stats = clusterer.cluster_all_news(
            time_limit_days=time_window_days,
            mode='incremental'
        )
        
        # Log completion
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Clustering completed in {duration:.2f}s")
        logger.info(f"Total news items processed: {stats.get('total_news', 0)}")
        
        log_task_execution('completed', stats.get('total_news', 0))
        
    except Exception as e:
        logger.error(f"Fatal error in clustering job: {e}")
        log_task_execution('failed', 0, str(e))
    
    finally:
        logger.info("=" * 60)

if __name__ == "__main__":
    cluster_news()