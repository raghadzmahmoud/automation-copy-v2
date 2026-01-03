#!/usr/bin/env python3
"""
📱 Social Media Generation Job (Condition-Based)

⚠️ لا يوجد تحقق من الوقت!
   الـ start_worker.py هو المتحكم بالوقت

Condition: يشتغل فقط إذا في تقارير بدون محتوى social media
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

# Logging setup
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'social_media_job.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONDITION CHECK
# =============================================================================

def has_reports_without_social_media(hours: int = 48) -> tuple:
    """
    ✅ Condition: هل في تقارير جديدة بدون محتوى social media؟
    Returns: (bool, count)
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM reports r
            WHERE r.created_at >= NOW() - INTERVAL '%s hours'
            AND NOT EXISTS (
                SELECT 1 FROM social_media_content smc
                WHERE smc.report_id = r.id
            )
        """, (hours,))
        
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return count > 0, count
        
    except Exception as e:
        logger.error(f"Error checking reports without social media: {e}")
        return False, 0


# =============================================================================
# MAIN
# =============================================================================

def generate_social_media_content() -> dict:
    """Main social media generation function"""
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info(f"📱 Social Media Job started at {start_time}")

    # ✅ Condition Check
    has_work, reports_count = has_reports_without_social_media(hours=48)
    
    if not has_work:
        logger.info("⏭️ No reports without social media content, skipping")
        logger.info("=" * 60)
        return {'skipped': True, 'reason': 'no_new_data'}
    
    logger.info(f"📊 Found {reports_count} reports needing social media content")

    generator = None
    try:
        from app.services.generators.social_media_generator import SocialMediaGenerator
        
        generator = SocialMediaGenerator()
        platforms = ['facebook', 'twitter', 'instagram']
        
        logger.info(f"⚙️ Platforms: {', '.join(platforms)}")
        logger.info(f"⚙️ Limit: 10 reports per run")
        
        stats = generator.generate_for_all_reports(
            platforms=platforms,
            force_update=False,
            limit=10
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"✅ Social media generation completed in {duration:.2f}s")
        logger.info(f"📊 Reports processed: {stats.get('total_reports', 0)}")
        logger.info(f"📊 Content created: {stats.get('success', 0)}")
        logger.info(f"📊 Failed: {stats.get('failed', 0)}")
        logger.info("=" * 60)
        
        return {
            'skipped': False,
            'duration': duration,
            'stats': stats
        }
        
    except Exception as e:
        logger.error(f"❌ Social media generation failed: {e}")
        import traceback
        traceback.print_exc()
        logger.info("=" * 60)
        return {'skipped': False, 'error': str(e)}
    
    finally:
        if generator:
            try:
                generator.close()
            except:
                pass


if __name__ == "__main__":
    generate_social_media_content()