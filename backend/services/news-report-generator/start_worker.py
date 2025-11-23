#!/usr/bin/env python3
import schedule
import time
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_scraper():
    logger.info("Starting scraper job...")
    try:
        from cron.scraper_job import scrape_news
        scrape_news()
    except Exception as e:
        logger.error(f"Scraper error: {e}")

def run_clustering():
    logger.info("Starting clustering job...")
    try:
        from cron.clustering_job import cluster_news
        cluster_news()
    except Exception as e:
        logger.error(f"Clustering error: {e}")

def run_reports():
    logger.info("Starting reports job...")
    try:
        from cron.reports_job import generate_reports
        generate_reports()
    except Exception as e:
        logger.error(f"Reports error: {e}")

def main():
    logger.info("=" * 60)
    logger.info("Background Worker Started")
    logger.info("=" * 60)
    
    schedule.every(10).minutes.do(run_scraper)
    schedule.every(1).hours.do(run_clustering)
    schedule.every(1).hours.do(run_reports)
    
    logger.info("Running initial scraper...")
    run_scraper()
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()