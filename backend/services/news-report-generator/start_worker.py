"""
Background Worker - Runs all cron jobs on schedule
"""
import schedule
import time
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_scraper():
    """Run news scraper job"""
    logger.info("Starting scraper job...")
    try:
        from cron.scraper_job import scrape_news
        scrape_news()
    except Exception as e:
        logger.error(f"Scraper error: {e}")

def run_clustering():
    """Run clustering job"""
    logger.info("Starting clustering job...")
    try:
        from cron.clustering_job import cluster_news
        cluster_news()
    except Exception as e:
        logger.error(f"Clustering error: {e}")

def run_reports():
    """Run report generation job"""
    logger.info("Starting reports job...")
    try:
        from cron.reports_job import generate_reports
        generate_reports()
    except Exception as e:
        logger.error(f"Reports error: {e}")

def main():
    logger.info("=" * 60)
    logger.info("🚀 Background Worker Started")
    logger.info("=" * 60)
    
    # Schedule jobs
    schedule.every(10).minutes.do(run_scraper)      # كل 10 دقائق
    schedule.every(1).hours.do(run_clustering)       # كل ساعة
    schedule.every(1).hours.do(run_reports)          # كل ساعة
    
    logger.info("📅 Scheduled Jobs:")
    logger.info("   • Scraper: every 10 minutes")
    logger.info("   • Clustering: every 1 hour")
    logger.info("   • Reports: every 1 hour")
    
    # Run scraper immediately on startup
    logger.info("Running initial scraper...")
    run_scraper()
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()