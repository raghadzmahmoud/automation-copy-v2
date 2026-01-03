#!/usr/bin/env python3
"""
🎨 Image Generation Job (Condition-Based)

⚠️ لا يوجد تحقق من الوقت!
   الـ start_worker.py هو المتحكم بالوقت

Condition: يشتغل فقط إذا في تقارير بدون صور
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
        logging.FileHandler(os.path.join(log_dir, 'image_generation_job.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONDITION CHECK
# =============================================================================

def has_reports_without_images(hours: int = 48) -> tuple:
    """
    ✅ Condition: هل في تقارير جديدة بدون صور؟
    Returns: (bool, count)
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM reports r
            WHERE r.created_at >= NOW() - INTERVAL '%s hours'
            AND (r.image_url IS NULL OR r.image_url = '')
        """, (hours,))
        
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return count > 0, count
        
    except Exception as e:
        logger.error(f"Error checking reports without images: {e}")
        return False, 0


# =============================================================================
# MAIN
# =============================================================================

def generate_images() -> dict:
    """Main image generation function"""
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info(f"🎨 Image Generation Job started at {start_time}")

    # ✅ Condition Check
    has_work, reports_count = has_reports_without_images(hours=48)
    
    if not has_work:
        logger.info("⏭️ No reports without images found, skipping")
        logger.info("=" * 60)
        return {'skipped': True, 'reason': 'no_new_data'}
    
    logger.info(f"📊 Found {reports_count} reports needing images")

    generator = None
    try:
        from app.services.generators.image_generator import ImageGenerator
        
        generator = ImageGenerator()
        
        logger.info(f"⚙️ Limit: 40 images per run")
        
        stats = generator.generate_for_all_reports(
            force_update=False,
            limit=40
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"✅ Image generation completed in {duration:.2f}s")
        logger.info(f"📊 Reports processed: {stats.get('total_reports', 0)}")
        logger.info(f"📊 Images created: {stats.get('success', 0)}")
        logger.info(f"📊 Failed: {stats.get('failed', 0)}")
        logger.info("=" * 60)
        
        return {
            'skipped': False,
            'duration': duration,
            'stats': stats
        }
        
    except Exception as e:
        logger.error(f"❌ Image generation failed: {e}")
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
    generate_images()