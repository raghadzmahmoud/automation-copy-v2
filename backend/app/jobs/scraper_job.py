#!/usr/bin/env python3
"""
📥 News Scraper Job (Condition-Based)

⚠️ لا يوجد تحقق من الوقت هنا!
   الـ Scheduler (start_worker.py) هو المتحكم بالوقت

Behavior:
- يسحب من كل المصادر النشطة
- يتحقق فقط من: هل المصدر جاهز للسحب؟ (minutes_since_fetch)
- 8 أخبار من كل مصدر

Usage: Called by start_worker.py scheduler
"""

import sys
import os

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
    )
)

import logging
from datetime import datetime
import psycopg2
from settings import DB_CONFIG
from app.config.user_config import user_config

# =============================================================================
# LOGGING
# =============================================================================

log_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'logs'
)
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'scraper_job.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE
# =============================================================================

def is_processing_pipeline_running() -> bool:
    """
    تحقق إذا في processing pipeline شغال حاليًا
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # تحقق إذا في processing_pipeline شغال من آخر 30 دقيقة
        cursor.execute("""
            SELECT COUNT(*) FROM scheduled_task_logs stl
            JOIN scheduled_tasks st ON stl.scheduled_task_id = st.id
            WHERE st.task_type = 'processing_pipeline'
            AND stl.executed_at >= NOW() - INTERVAL '30 minutes'
            AND stl.status = 'running'
        """)
        
        running_count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return running_count > 0
        
    except Exception as e:
        logger.error(f"Error checking pipeline status: {e}")
        return False


def get_active_sources():
    """
    Get all active sources ready for scraping
    Condition: minutes_since_fetch >= DEFAULT_INTERVAL
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                s.id,
                s.name,
                s.source_type_id,
                s.url,
                COALESCE(s.last_fetched, '1970-01-01'::timestamp),
                EXTRACT(EPOCH FROM (
                    CURRENT_TIMESTAMP - COALESCE(s.last_fetched, '1970-01-01')
                )) / 60 AS minutes_since_fetch,
                st.name AS source_type_name
            FROM sources s
            LEFT JOIN source_types st ON s.source_type_id = st.id
            WHERE s.is_active = true
            ORDER BY COALESCE(s.last_fetched, '1970-01-01') ASC
        """)

        sources = cursor.fetchall()
        cursor.close()
        conn.close()

        # Filter by interval (condition-based)
        DEFAULT_INTERVAL = getattr(
            user_config,
            'default_fetch_interval_minutes',
            30  # default: 30 minutes between fetches per source
        )

        return [s for s in sources if s[5] >= DEFAULT_INTERVAL]

    except Exception as e:
        logger.error(f"Error getting active sources: {e}")
        return []


# =============================================================================
# MAIN
# =============================================================================

def scrape_news() -> dict:
    """
    Main scraping function
    
    Returns:
        dict with stats: {total, success, failed, news_saved}
    """
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info(f"📥 Scraper Job started at {start_time}")
    logger.info("=" * 60)

    # Check if enabled
    if not user_config.scraping_enabled:
        logger.info("⏭️ Scraping is disabled in configuration")
        return {'total': 0, 'success': 0, 'failed': 0, 'news_saved': 0, 'skipped': True}

    # ✅ Check if processing pipeline is running
    if is_processing_pipeline_running():
        logger.info("⏭️ Processing pipeline is running, skipping scraping to avoid conflicts")
        logger.info("=" * 60)
        return {'total': 0, 'success': 0, 'failed': 0, 'news_saved': 0, 'skipped': True}

    # Get sources ready for scraping
    sources = get_active_sources()
    
    if not sources:
        logger.info("⏭️ No sources ready for scraping (all recently fetched)")
        return {'total': 0, 'success': 0, 'failed': 0, 'news_saved': 0, 'skipped': True}
    
    logger.info(f"📋 Found {len(sources)} sources ready for scraping:")
    for i, s in enumerate(sources, start=1):
        logger.info(f"   {i}. [{s[6]}] {s[1]} - {s[3][:50]}...")

    # Import scraper
    from app.services.ingestion.scraper import scrape_url

    total_news = 0
    success_count = 0
    failed_count = 0

    for source in sources:
        source_id = source[0]
        name = source[1]
        url = source[3]
        source_type = source[6]

        try:
            logger.info(f"📥 Scraping: {name} ({source_type})")

            result = scrape_url(
                url=url,
                save_to_db=True,
                max_articles=8,
                language_id=1,
                use_telegram_api=False
            )

            if result.success:
                total_news += result.saved
                success_count += 1
                logger.info(
                    f"   ✅ Extracted={result.extracted}, "
                    f"Saved={result.saved}, Skipped={result.skipped}"
                )
            else:
                failed_count += 1
                logger.warning(f"   ⚠️ {result.error}")

        except Exception as e:
            failed_count += 1
            logger.error(f"   ❌ Error: {e}")

    # Summary
    duration = (datetime.now() - start_time).total_seconds()
    
    logger.info("=" * 60)
    logger.info(f"📊 Scraping completed in {duration:.2f}s")
    logger.info(f"   ✅ Successful: {success_count}")
    logger.info(f"   ❌ Failed: {failed_count}")
    logger.info(f"   📰 News saved: {total_news}")
    logger.info("=" * 60)

    return {
        'total': len(sources),
        'success': success_count,
        'failed': failed_count,
        'news_saved': total_news,
        'duration': duration,
        'skipped': False
    }


if __name__ == "__main__":
    scrape_news()