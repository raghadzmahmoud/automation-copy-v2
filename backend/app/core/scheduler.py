#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
⏰ Background Task Scheduler
Using APScheduler for automated jobs
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = BackgroundScheduler()


def scraping_job():
    """News scraping job - runs every 10 minutes"""
    try:
        logger.info("🔄 Starting scheduled scraping job...")
        from app.jobs.scraper_job import scrape_news
        scrape_news()
        logger.info("✅ Scraping job completed")
    except Exception as e:
        logger.error(f"❌ Scraping job failed: {e}")


def clustering_job():
    """News clustering job - runs every hour"""
    try:
        logger.info("🔄 Starting scheduled clustering job...")
        from app.jobs.clustering_job import cluster_news
        cluster_news()
        logger.info("✅ Clustering job completed")
    except Exception as e:
        logger.error(f"❌ Clustering job failed: {e}")


def reports_job():
    """Report generation job - runs every hour"""
    try:
        logger.info("🔄 Starting scheduled reports job...")
        from app.jobs.reports_job import generate_reports
        generate_reports()
        logger.info("✅ Reports job completed")
    except Exception as e:
        logger.error(f"❌ Reports job failed: {e}")


def start_scheduler():
    """Start the background scheduler"""
    try:
        # Add jobs
        
        # Scraping - every 10 minutes
        scheduler.add_job(
            scraping_job,
            trigger=CronTrigger(minute='*/10'),
            id='news_scraping',
            name='News Scraping',
            replace_existing=True
        )
        
        # Clustering - every hour
        scheduler.add_job(
            clustering_job,
            trigger=CronTrigger(hour='*'),
            id='news_clustering',
            name='News Clustering',
            replace_existing=True
        )
        
        # Reports - every hour
        scheduler.add_job(
            reports_job,
            trigger=CronTrigger(hour='*'),
            id='report_generation',
            name='Report Generation',
            replace_existing=True
        )
        
        # Start scheduler
        scheduler.start()
        
        logger.info("⏰ Scheduler started successfully")
        logger.info("📅 Next runs:")
        for job in scheduler.get_jobs():
            logger.info(f"   • {job.name}: {job.next_run_time}")
            
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")


def stop_scheduler():
    """Stop the background scheduler"""
    try:
        if scheduler.running:
            scheduler.shutdown()
            logger.info("⏰ Scheduler stopped")
    except Exception as e:
        logger.error(f"❌ Error stopping scheduler: {e}")


def get_scheduler_status():
    """Get scheduler status and jobs info"""
    if not scheduler.running:
        return {
            "status": "stopped",
            "jobs": []
        }
    
    jobs_info = []
    for job in scheduler.get_jobs():
        jobs_info.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })
    
    return {
        "status": "running",
        "jobs": jobs_info
    }