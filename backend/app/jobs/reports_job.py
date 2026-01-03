#!/usr/bin/env python3
"""
📝 Report Generation Job (Condition-Based)

⚠️ لا يوجد تحقق من الوقت!
   الـ start_worker.py هو المتحكم بالوقت

Condition: يشتغل فقط إذا في clusters بدون تقارير
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
        logging.FileHandler(os.path.join(log_dir, 'reports_job.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONDITION CHECK
# =============================================================================

def has_clusters_without_reports(hours: int = 48) -> tuple:
    """
    ✅ Condition: هل في clusters جديدة بدون تقارير؟
    Returns: (bool, count)
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM news_clusters nc
            WHERE nc.created_at >= NOW() - INTERVAL '%s hours'
            AND NOT EXISTS (
                SELECT 1 FROM reports r
                WHERE r.cluster_id = nc.id
            )
        """, (hours,))
        
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return count > 0, count
        
    except Exception as e:
        logger.error(f"Error checking clusters without reports: {e}")
        return False, 0


# =============================================================================
# MAIN
# =============================================================================

def generate_reports() -> dict:
    """Main report generation function"""
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info(f"📝 Report Generation Job started at {start_time}")

    # Check if enabled
    if not user_config.auto_generate_reports:
        logger.info("⏭️ Report generation is disabled in configuration")
        return {'skipped': True, 'reason': 'disabled'}

    # ✅ Condition Check
    has_work, clusters_count = has_clusters_without_reports(hours=48)
    
    if not has_work:
        logger.info("⏭️ No clusters without reports found, skipping")
        logger.info("=" * 60)
        return {'skipped': True, 'reason': 'no_new_data'}
    
    logger.info(f"📊 Found {clusters_count} clusters needing reports")

    try:
        from app.services.generators.reporter import ReportGenerator
        
        reporter = ReportGenerator()
        
        stats = reporter.generate_reports_for_clusters(
            skip_existing=True,
            check_updates_hours=user_config.report_generation_interval_hours
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"✅ Report generation completed in {duration:.2f}s")
        logger.info(f"📊 Clusters processed: {stats.get('total', 0)}")
        logger.info(f"📊 Reports generated: {stats.get('success', 0)}")
        logger.info(f"📊 Failed: {stats.get('failed', 0)}")
        logger.info("=" * 60)
        
        return {
            'skipped': False,
            'duration': duration,
            'stats': stats
        }
        
    except Exception as e:
        logger.error(f"❌ Report generation failed: {e}")
        import traceback
        traceback.print_exc()
        logger.info("=" * 60)
        return {'skipped': False, 'error': str(e)}


if __name__ == "__main__":
    generate_reports()