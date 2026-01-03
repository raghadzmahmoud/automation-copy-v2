#!/usr/bin/env python3
"""
🎙️ Audio Generation Job (Condition-Based)

⚠️ لا يوجد تحقق من الوقت!
   الـ start_worker.py هو المتحكم بالوقت

Condition: يشتغل فقط إذا في تقارير بدون صوت
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
        logging.FileHandler(os.path.join(log_dir, 'audio_generation_job.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONDITION CHECK
# =============================================================================

def has_reports_without_audio(hours: int = 48) -> tuple:
    """
    ✅ Condition: هل في تقارير جديدة بدون صوت؟
    Returns: (bool, count)
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM reports r
            WHERE r.created_at >= NOW() - INTERVAL '%s hours'
            AND (r.audio_url IS NULL OR r.audio_url = '')
        """, (hours,))
        
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return count > 0, count
        
    except Exception as e:
        logger.error(f"Error checking reports without audio: {e}")
        return False, 0


# =============================================================================
# MAIN
# =============================================================================

def generate_audio() -> dict:
    """Main audio generation function"""
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info(f"🎙️ Audio Generation Job started at {start_time}")

    # ✅ Condition Check
    has_work, reports_count = has_reports_without_audio(hours=48)
    
    if not has_work:
        logger.info("⏭️ No reports without audio found, skipping")
        logger.info("=" * 60)
        return {'skipped': True, 'reason': 'no_new_data'}
    
    logger.info(f"📊 Found {reports_count} reports needing audio")

    generator = None
    try:
        from app.services.generators.audio_generator import AudioGenerator
        
        generator = AudioGenerator()
        
        logger.info(f"⚙️ Limit: 4 audio files per run")
        
        stats = generator.generate_for_all_reports(
            force_update=False,
            limit=4
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"✅ Audio generation completed in {duration:.2f}s")
        logger.info(f"📊 Reports processed: {stats.get('total_reports', 0)}")
        logger.info(f"📊 Audio created: {stats.get('success', 0)}")
        logger.info(f"📊 Failed: {stats.get('failed', 0)}")
        logger.info("=" * 60)
        
        return {
            'skipped': False,
            'duration': duration,
            'stats': stats
        }
        
    except Exception as e:
        logger.error(f"❌ Audio generation failed: {e}")
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
    generate_audio()