#!/usr/bin/env python3
"""
✅ UPDATED: News Scraper Cron Job
Runs every 10 minutes to fetch news from all active sources
Usage: python cron/scraper_job.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
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
        logging.FileHandler(os.path.join(log_dir, 'scraper_job.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_active_sources():
    """
    ✅ UPDATED: Get all active sources that need scraping
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # ✅ استخدام الـ query المُحدَّث
        cursor.execute("""
            SELECT 
                s.id, 
                s.name, 
                s.source_type_id, 
                s.url, 
                COALESCE(s.last_fetched, '1970-01-01'::timestamp) as last_fetched,
                EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - COALESCE(s.last_fetched, '1970-01-01'::timestamp)))/60 as minutes_since_fetch,
                st.name as source_type_name
            FROM sources s
            LEFT JOIN source_types st ON s.source_type_id = st.id
            WHERE s.is_active = true
            ORDER BY COALESCE(s.last_fetched, '1970-01-01'::timestamp) ASC
        """)
        
        sources = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Filter sources based on fetch interval
        DEFAULT_INTERVAL = getattr(user_config, 'default_fetch_interval_minutes', 60)
        sources_to_fetch = [
            s for s in sources
            if s[5] >= DEFAULT_INTERVAL  # minutes_since_fetch >= interval
        ]
        
        return sources_to_fetch
        
    except Exception as e:
        logger.error(f"Error getting active sources: {e}")
        return []


def update_source_last_fetched(source_id: int):
    """
    ✅ UPDATED: Update last_fetched + updated_at
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE sources
            SET last_fetched = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (source_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error updating last_fetched for source {source_id}: {e}")


def log_task_execution(status: str, items_count: int = 0, error_message: str = None):
    """
    ✅ UPDATED: Log cron job execution
    تم تغيير: task_name → name
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # ✅ استخدام `name` بدلاً من `task_name`
        cursor.execute("""
            SELECT id FROM scheduled_tasks 
            WHERE task_type = 'scraping'
        """)
        
        task_id = cursor.fetchone()
        if not task_id:
            logger.warning("Task 'news_scraping' not found in scheduled_tasks")
            return
        
        task_id = task_id[0]
        
        # Insert log
        cursor.execute("""
            INSERT INTO scheduled_task_logs (
                scheduled_task_id, 
                status, 
                execution_time_seconds, 
                result, 
                error_message, 
                executed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (task_id, status, 0.0, str(items_count), error_message, datetime.now()))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error logging task execution: {e}")


def scrape_news():
    """Main scraping function"""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info(f"Starting news scraping job at {start_time}")
    
    # Check if scraping is enabled
    if not user_config.scraping_enabled:
        logger.info("Scraping is disabled in configuration")
        return
    
    try:
        # Get sources to scrape
        sources = get_active_sources()
        logger.info(f"Found {len(sources)} sources to scrape")
        
        if not sources:
            logger.info("No sources need scraping at this time")
            log_task_execution('completed', 0)
            return
        
        total_news = 0
        
        # Import scraper
        from app.services.ingestion.scraper import NewsScraper
        scraper = NewsScraper()
        
        # Scrape each source
        for source in sources:
            # ✅ التوافق مع Structure الجديد
            # SELECT id, name, source_type_id, url, last_fetched, minutes_since_fetch, source_type_name
            source_id = source[0]
            name = source[1]
            source_type_id = source[2]
            url = source[3]
            source_type_name = source[6]  
            language_id = 1  # default Arabic
            
            try:
                logger.info(f"Scraping source: {name} ({source_type_name})")
                
                # Normalize source type name to be case-insensitive
                normalized_source_type = source_type_name.lower().strip()
                
                if normalized_source_type == 'rss':
                    news_items = scraper.scrape_rss(url, source_id, language_id)
                else:
                    logger.warning(f"Unknown source type: {source_type_name}")
                    continue
                
                # Save news items
                saved_count = scraper.save_news_items(news_items)
                total_news += saved_count
                
                logger.info(f"✓ Saved {saved_count} news items from {name}")
                
                # Update last_fetched
                update_source_last_fetched(source_id)
                
            except Exception as e:
                logger.error(f"✗ Error scraping {name}: {e}")
                continue
        
        # Log completion
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Scraping completed in {duration:.2f}s")
        logger.info(f"Total news items saved: {total_news}")
        
        log_task_execution('completed', total_news)
        
    except Exception as e:
        logger.error(f"Fatal error in scraping job: {e}")
        log_task_execution('failed', 0, str(e))
    
    finally:
        logger.info("=" * 60)


if __name__ == "__main__":
    scrape_news()