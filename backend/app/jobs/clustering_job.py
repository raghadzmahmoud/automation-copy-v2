#!/usr/bin/env python3
"""
🎯 News Clustering Job (Condition-Based)

⚠️ لا يوجد تحقق من الوقت!
   الـ start_worker.py هو المتحكم بالوقت

Condition: يشتغل فقط إذا في أخبار جديدة غير مجمعة
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
import psycopg2
from settings import DB_CONFIG
from app.config.user_config import user_config

# Logging setup
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'clustering_job.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONDITION CHECK
# =============================================================================

def has_unclustered_news(hours: int = 48) -> tuple:
    """
    ✅ Condition: هل في أخبار جديدة غير مجمعة؟
    Returns: (bool, count)
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM raw_news rn
            WHERE rn.collected_at >= NOW() - INTERVAL '%s hours'
            AND NOT EXISTS (
                SELECT 1 FROM news_cluster_members ncm
                WHERE ncm.news_id = rn.id
            )
        """, (hours,))
        
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return count > 0, count
        
    except Exception as e:
        logger.error(f"Error checking unclustered news: {e}")
        return False, 0


# =============================================================================
# MAIN
# =============================================================================

def cluster_news() -> dict:
    """Main clustering function"""
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info(f"🎯 Clustering Job started at {start_time}")

    # Check if enabled
    if not user_config.clustering_enabled:
        logger.info("⏭️ Clustering is disabled in configuration")
        return {'skipped': True, 'reason': 'disabled'}

    # ✅ Condition Check
    has_work, unclustered_count = has_unclustered_news(hours=48)
    
    if not has_work:
        logger.info("⏭️ No unclustered news found, skipping")
        logger.info("=" * 60)
        return {'skipped': True, 'reason': 'no_new_data'}
    
    logger.info(f"📊 Found {unclustered_count} unclustered news items")

    try:
        from app.services.processing.clustering import NewsClusterer
        
        time_window_days = user_config.clustering_time_window_hours / 24.0
        
        logger.info(f"⚙️ Time window: {user_config.clustering_time_window_hours} hours")
        logger.info(f"⚙️ Min similarity: {user_config.clustering_min_similarity}")
        
        clusterer = NewsClusterer()
        stats = clusterer.cluster_all_news(
            time_limit_days=time_window_days,
            mode='incremental'
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"✅ Clustering completed in {duration:.2f}s")
        logger.info(f"📊 News processed: {stats.get('total_news', 0)}")
        logger.info(f"📊 Clusters created: {stats.get('clusters_created', 0)}")
        logger.info("=" * 60)
        
        return {
            'skipped': False,
            'duration': duration,
            'stats': stats
        }
        
    except Exception as e:
        logger.error(f"❌ Clustering failed: {e}")
        import traceback
        traceback.print_exc()
        logger.info("=" * 60)
        return {'skipped': False, 'error': str(e)}


if __name__ == "__main__":
    cluster_news()