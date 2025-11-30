#!/usr/bin/env python3
"""
⏰ Background Worker with Job Locking
Runs scheduled jobs: scraping, clustering, reports, social media, images
"""
import schedule
import time
import logging
from datetime import datetime
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lock to prevent overlapping jobs
job_lock = threading.Lock()

def safe_run(job_func, job_name):
    """Run a job safely: wait if another job is running"""
    logger.info(f"{job_name} waiting for lock if needed...")
    with job_lock:  # ينتظر تلقائياً إذا lock مشغول
        logger.info(f"Starting {job_name}...")
        try:
            job_func()
        except Exception as e:
            logger.error(f"{job_name} error: {e}")
            import traceback
            traceback.print_exc()
        logger.info(f"{job_name} finished.")

def run_scraper():
    """News scraper job - every 10 minutes"""
    from cron.scraper_job import scrape_news
    safe_run(scrape_news, "Scraper Job")

def run_clustering():
    """News clustering job - every hour"""
    from cron.clustering_job import cluster_news
    safe_run(cluster_news, "Clustering Job")

def run_reports():
    """Report generation job - every hour"""
    from cron.reports_job import generate_reports
    safe_run(generate_reports, "Reports Job")

def run_social_media():
    """Social media generation job - every hour"""
    from cron.social_media_job import generate_social_media_content
    safe_run(generate_social_media_content, "Social Media Job")

def run_image_generation():
    """Image generation job - every hour"""
    from cron.image_generation_job import generate_images
    safe_run(generate_images, "Image Generation Job")

def main():
    logger.info("=" * 60)
    logger.info("⏰ Background Worker Started")
    logger.info("=" * 60)
    logger.info("Jobs Schedule:")
    logger.info("  • Scraper:         Every 10 minutes")
    logger.info("  • Clustering:      Every 1 hour")
    logger.info("  • Reports:         Every 1 hour")
    logger.info("  • Social Media:    Every 1 hour")
    logger.info("  • Image Generation: Every 1 hour")
    logger.info("=" * 60)
    
    # Schedule jobs
    schedule.every(10).minutes.do(run_scraper)
    schedule.every(1).hours.do(run_clustering)
    schedule.every(1).hours.do(run_reports)
    schedule.every(1).hours.do(run_social_media)
    schedule.every(1).minutes.do(run_image_generation)
    
    # Run initial scraper
    logger.info("Running initial scraper...")
    run_scraper()
    
    # Main loop
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()