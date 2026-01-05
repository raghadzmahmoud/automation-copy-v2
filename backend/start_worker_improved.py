#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔄 Improved Task Scheduler with Parallel Execution & Timeouts
═══════════════════════════════════════════════════════════════
يشغل الـ jobs بشكل parallel مع timeout protection
يضمن إن job واحد ما يعطل كامل الـ pipeline

Improvements:
✅ Parallel execution داخل كل group
✅ Individual timeouts لكل job
✅ Error isolation
✅ Better monitoring
✅ Graceful degradation

Flow:
┌─────────────────────────────────────────────────────────────┐
│  Loop كل 2 دقيقة:                                           │
│                                                             │
│  1. 📥 Scraping (parallel if multiple sources)             │
│  2. 🔄 Processing: cluster → report → social (sequential)   │
│  3. 🎨 Media: image + audio (parallel)                     │
│  4. 📤 Publishing: social_img + reel + publish (parallel)   │
│  5. 📻 Broadcast (single job)                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import signal
import logging
import traceback
from datetime import datetime, timezone
from typing import Dict, Optional

import certifi
import psycopg2

# Set SSL certificate
os.environ["SSL_CERT_FILE"] = certifi.where()

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from settings import DB_CONFIG
from app.utils.parallel_executor import ParallelJobExecutor, JobConfig, run_jobs_parallel
from app.utils.job_timeout import timeout_job_by_type, get_job_timeout

# ═══════════════════════════════════════════════════════════════
# Logging Setup
# ═══════════════════════════════════════════════════════════════

log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'{log_dir}/worker_improved.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Job Imports (Lazy Loading)
# ═══════════════════════════════════════════════════════════════

def import_jobs():
    """Import all job functions with timeout decorators"""
    global scrape_news, cluster_news, generate_reports
    global generate_social_media_content, generate_images, generate_audio
    global generate_social_media_images, generate_reels, publish_to_social_media
    global generate_all_broadcasts, generate_bulletin_job, generate_digest_job
    
    # Import original functions
    from app.jobs.scraper_job import scrape_news as _scrape_news
    from app.jobs.clustering_job import cluster_news as _cluster_news
    from app.jobs.reports_job import generate_reports as _generate_reports
    from app.jobs.social_media_job import generate_social_media_content as _generate_social_media_content
    from app.jobs.image_generation_job import generate_images as _generate_images
    from app.jobs.audio_generation_job import generate_audio as _generate_audio
    from app.jobs.social_media_image_job import generate_social_media_images as _generate_social_media_images
    from app.jobs.reel_generation_job import generate_reels as _generate_reels
    from app.jobs.publishers_job import publish_to_social_media as _publish_to_social_media
    from app.jobs.broadcast_job import generate_all_broadcasts as _generate_all_broadcasts
    
    # Import bulletin/digest jobs (they exist in both files, use broadcast_job version)
    from app.jobs.broadcast_job import generate_bulletin_job as _generate_bulletin_job
    from app.jobs.broadcast_job import generate_digest_job as _generate_digest_job
    
    # Wrap with timeout decorators
    scrape_news = timeout_job_by_type('scraping')(_scrape_news)
    cluster_news = timeout_job_by_type('clustering')(_cluster_news)
    generate_reports = timeout_job_by_type('reports')(_generate_reports)
    generate_social_media_content = timeout_job_by_type('social_media')(_generate_social_media_content)
    generate_images = timeout_job_by_type('images')(_generate_images)
    generate_audio = timeout_job_by_type('audio')(_generate_audio)
    generate_social_media_images = timeout_job_by_type('images')(_generate_social_media_images)
    generate_reels = timeout_job_by_type('video')(_generate_reels)
    publish_to_social_media = timeout_job_by_type('publishing')(_publish_to_social_media)
    generate_all_broadcasts = timeout_job_by_type('broadcast')(_generate_all_broadcasts)
    
    # Individual broadcast jobs (for flexibility)
    generate_bulletin_job = timeout_job_by_type('broadcast')(_generate_bulletin_job)
    generate_digest_job = timeout_job_by_type('broadcast')(_generate_digest_job)
    
    logger.info("✅ All jobs imported with timeout protection")
    logger.info("📋 Available jobs:")
    logger.info("   📥 scrape_news")
    logger.info("   🔄 cluster_news, generate_reports, generate_social_media_content")
    logger.info("   🎨 generate_images, generate_audio")
    logger.info("   📤 generate_social_media_images, generate_reels, publish_to_social_media")
    logger.info("   📻 generate_all_broadcasts, generate_bulletin_job, generate_digest_job")


# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

# الفترة الأساسية بين الدورات (بالثواني)
BASE_CYCLE_INTERVAL = int(os.getenv('CYCLE_INTERVAL', 120))  # 2 دقيقة default  

# كل كم دورة يشتغل كل group
CYCLE_CONFIG = {
    'scraping': 1,           # كل دورة (كل 2 دق)
    'processing': 1,         # كل دورة (كل 2 دق)
    'media_generation': 2,   # كل دورتين (كل 4 دق)
    'publishing': 3,         # كل 3 دورات (كل 6 دق)
    'broadcast': 3,          # كل 3 دورات (كل 6 دق)
}

# عدد الـ workers لكل group
WORKER_CONFIG = {
    'scraping': 1,           # عادة source واحد
    'processing': 1,         # sequential (dependencies)
    'media_generation': 2,   # image + audio parallel
    'publishing': 3,         # social_img + reel + publish parallel
    'broadcast': 1,          # job واحد
}


# ═══════════════════════════════════════════════════════════════
# Job Execution
# ═══════════════════════════════════════════════════════════════

def run_job_group_sequential(group_name: str, jobs: list) -> Dict:
    """
    تشغيل مجموعة jobs بالترتيب (للـ dependencies)
    """
    logger.info(f"\n{'─'*60}")
    logger.info(f"🔷 GROUP: {group_name} (Sequential)")
    logger.info(f"{'─'*60}")
    
    group_start = datetime.now()
    results = {}
    
    for job_name, job_func in jobs:
        job_start = datetime.now()
        logger.info(f"▶️  Starting: {job_name}")
        
        try:
            result = job_func()
            duration = (datetime.now() - job_start).total_seconds()
            
            if result.get('skipped'):
                logger.info(f"⏭️  {job_name}: Skipped ({result.get('reason', 'no reason')})")
                results[job_name] = {'success': True, 'skipped': True, 'duration': duration}
            elif result.get('error'):
                logger.error(f"❌ {job_name}: Error - {result.get('error')}")
                results[job_name] = {'success': False, 'error': result.get('error'), 'duration': duration}
            else:
                logger.info(f"✅ {job_name}: Completed in {duration:.1f}s")
                results[job_name] = {'success': True, 'duration': duration}
        
        except Exception as e:
            duration = (datetime.now() - job_start).total_seconds()
            logger.error(f"❌ {job_name}: Exception - {e}")
            results[job_name] = {'success': False, 'error': str(e), 'duration': duration}
        
        # فترة راحة قصيرة بين الـ jobs
        time.sleep(2)
    
    group_duration = (datetime.now() - group_start).total_seconds()
    logger.info(f"🔷 GROUP {group_name} completed in {group_duration:.1f}s")
    
    return results


def run_job_group_parallel(group_name: str, jobs: list, max_workers: int = 2) -> Dict:
    """
    تشغيل مجموعة jobs بشكل parallel
    """
    logger.info(f"\n{'─'*60}")
    logger.info(f"🔷 GROUP: {group_name} (Parallel - {max_workers} workers)")
    logger.info(f"{'─'*60}")
    
    # تحضير الـ jobs للـ parallel executor
    job_configs = []
    for job_name, job_func in jobs:
        # احصل على الـ timeout المناسب
        timeout = get_job_timeout(job_name.split('_')[0])  # أول كلمة من اسم الـ job
        job_configs.append((job_name, job_func, timeout))
    
    # تشغيل parallel
    parallel_results = run_jobs_parallel(job_configs, max_workers)
    
    # تحويل النتائج للـ format المطلوب
    results = {}
    for job_name, job_result in parallel_results.items():
        results[job_name] = {
            'success': job_result.success,
            'duration': job_result.duration,
            'error': job_result.error,
            'timeout': job_result.timeout
        }
    
    return results


# ═══════════════════════════════════════════════════════════════
# Main Cycle
# ═══════════════════════════════════════════════════════════════

def run_cycle(cycle_number: int) -> Dict:
    """
    تشغيل دورة كاملة مع parallel execution
    """
    cycle_start = datetime.now()
    
    logger.info("\n" + "═"*70)
    logger.info(f"🔄 IMPROVED CYCLE #{cycle_number} started at {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("═"*70)
    
    results = {}
    
    # ───────────────────────────────────────────────────────────
    # Group 1: Data Ingestion (Scraping)
    # Sequential (عادة source واحد)
    # ───────────────────────────────────────────────────────────
    if cycle_number % CYCLE_CONFIG['scraping'] == 0:
        results['scraping'] = run_job_group_sequential('DATA INGESTION', [
            ('scraping', scrape_news),
        ])
    
    # ───────────────────────────────────────────────────────────
    # Group 2: Processing (Cluster → Report → Social Text)
    # Sequential (dependencies بينهم)
    # ───────────────────────────────────────────────────────────
    if cycle_number % CYCLE_CONFIG['processing'] == 0:
        results['processing'] = run_job_group_sequential('PROCESSING', [
            ('clustering', cluster_news),
            ('reports', generate_reports),
            ('social_media_text', generate_social_media_content),
        ])
    
    # ───────────────────────────────────────────────────────────
    # Group 3: Media Generation (Image + Audio)
    # Parallel (مستقلين عن بعض)
    # ───────────────────────────────────────────────────────────
    if cycle_number % CYCLE_CONFIG['media_generation'] == 0:
        results['media'] = run_job_group_parallel('MEDIA GENERATION', [
            ('images', generate_images),
            ('audio', generate_audio),
        ], max_workers=WORKER_CONFIG['media_generation'])
    
    # ───────────────────────────────────────────────────────────
    # Group 4: Publishing (Social Image + Reel + Publish)
    # Parallel (مستقلين نسبياً)
    # ───────────────────────────────────────────────────────────
    if cycle_number % CYCLE_CONFIG['publishing'] == 0:
        results['publishing'] = run_job_group_parallel('PUBLISHING', [
            ('social_media_images', generate_social_media_images),
            ('reels', generate_reels),
            ('publishers', publish_to_social_media),
        ], max_workers=WORKER_CONFIG['publishing'])
    
    # ───────────────────────────────────────────────────────────
    # Group 5: Broadcast (Bulletin + Digest)
    # Sequential (job واحد أو منفصل)
    # ───────────────────────────────────────────────────────────
    if cycle_number % CYCLE_CONFIG['broadcast'] == 0:
        # يمكن تشغيل generate_all_broadcasts (الموصى به)
        # أو تشغيل bulletin و digest منفصلين
        broadcast_mode = os.getenv('BROADCAST_MODE', 'unified')  # unified, separate
        
        if broadcast_mode == 'separate':
            results['broadcast'] = run_job_group_sequential('BROADCAST', [
                ('bulletin', generate_bulletin_job),
                ('digest', generate_digest_job),
            ])
        else:
            # الوضع الموحد (default)
            results['broadcast'] = run_job_group_sequential('BROADCAST', [
                ('broadcast', generate_all_broadcasts),
            ])
    
    # ───────────────────────────────────────────────────────────
    # Summary
    # ───────────────────────────────────────────────────────────
    cycle_duration = (datetime.now() - cycle_start).total_seconds()
    
    logger.info("\n" + "═"*70)
    logger.info(f"📊 IMPROVED CYCLE #{cycle_number} Summary")
    logger.info("═"*70)
    logger.info(f"Duration: {cycle_duration:.1f}s ({cycle_duration/60:.1f} min)")
    
    # إحصائيات مفصلة
    total_jobs = 0
    successful_jobs = 0
    failed_jobs = 0
    timeout_jobs = 0
    
    for group_name, group_results in results.items():
        logger.info(f"\n  {group_name}:")
        for job_name, job_result in group_results.items():
            total_jobs += 1
            
            if job_result.get('skipped'):
                status = "⏭️"
            elif job_result.get('timeout'):
                status = "⏰❌"
                timeout_jobs += 1
            elif job_result.get('success'):
                status = "✅"
                successful_jobs += 1
            else:
                status = "❌"
                failed_jobs += 1
            
            duration = job_result.get('duration', 0)
            logger.info(f"    {status} {job_name}: {duration:.1f}s")
    
    logger.info(f"\n📈 Stats: {successful_jobs}✅ {failed_jobs}❌ {timeout_jobs}⏰ / {total_jobs} total")
    logger.info("═"*70 + "\n")
    
    return {
        'cycle': cycle_number,
        'duration': cycle_duration,
        'results': results,
        'stats': {
            'total': total_jobs,
            'successful': successful_jobs,
            'failed': failed_jobs,
            'timeout': timeout_jobs
        }
    }


# ═══════════════════════════════════════════════════════════════
# Main Loop
# ═══════════════════════════════════════════════════════════════

# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global running
    logger.info("\n⚠️  Shutdown signal received, finishing current cycle...")
    running = False


def main():
    """Main entry point"""
    global running
    
    logger.info("═"*70)
    logger.info("🚀 Improved Task Scheduler Starting")
    logger.info("   ✅ Parallel execution enabled")
    logger.info("   ✅ Individual job timeouts")
    logger.info("   ✅ Error isolation")
    logger.info("   ✅ Better monitoring")
    logger.info("═"*70)
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    
    # Check FFmpeg availability
    try:
        from app.utils.audio_converter import AudioConverter
        audio_converter = AudioConverter()
        
        if audio_converter.is_ffmpeg_available():
            logger.info("✅ FFmpeg available")
        else:
            logger.warning("⚠️  FFmpeg not available - audio features may be limited")
    except Exception as e:
        logger.warning(f"⚠️  Could not check FFmpeg availability: {e}")
    
    logger.info(f"Base cycle interval: {BASE_CYCLE_INTERVAL}s ({BASE_CYCLE_INTERVAL//60} min)")
    logger.info("")
    logger.info("Schedule & Workers:")
    logger.info(f"  📥 Scraping:    every {CYCLE_CONFIG['scraping']} cycle(s) - {WORKER_CONFIG['scraping']} worker(s)")
    logger.info(f"  🔄 Processing:  every {CYCLE_CONFIG['processing']} cycle(s) - {WORKER_CONFIG['processing']} worker(s)")
    logger.info(f"  🎨 Media:       every {CYCLE_CONFIG['media_generation']} cycle(s) - {WORKER_CONFIG['media_generation']} worker(s)")
    logger.info(f"  📤 Publishing:  every {CYCLE_CONFIG['publishing']} cycle(s) - {WORKER_CONFIG['publishing']} worker(s)")
    logger.info(f"  📻 Broadcast:   every {CYCLE_CONFIG['broadcast']} cycle(s) - {WORKER_CONFIG['broadcast']} worker(s)")
    logger.info("═"*70)
    
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Import jobs
    try:
        import_jobs()
    except Exception as e:
        logger.error(f"❌ Failed to import jobs: {e}")
        traceback.print_exc()
        sys.exit(1)
    
    cycle_number = 0
    
    while running:
        cycle_number += 1
        
        try:
            # Run the cycle
            cycle_result = run_cycle(cycle_number)
            
            # Log performance metrics
            stats = cycle_result['stats']
            if stats['timeout'] > 0:
                logger.warning(f"⚠️  {stats['timeout']} jobs timed out in cycle #{cycle_number}")
            
            if not running:
                break
            
            # Wait for next cycle
            logger.info(f"💤 Waiting {BASE_CYCLE_INTERVAL}s ({BASE_CYCLE_INTERVAL//60} min) until next cycle...")
            
            # Sleep in small increments to allow for graceful shutdown
            for _ in range(BASE_CYCLE_INTERVAL):
                if not running:
                    break
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("\n⚠️  Keyboard interrupt received")
            break
            
        except Exception as e:
            logger.error(f"❌ Cycle error: {e}")
            traceback.print_exc()
            
            # Wait a bit before retrying
            logger.info("⏳ Waiting 60s before retry...")
            for _ in range(60):
                if not running:
                    break
                time.sleep(1)
    
    logger.info("\n" + "═"*70)
    logger.info("🛑 Improved Scheduler stopped gracefully")
    logger.info("═"*70)


if __name__ == "__main__":
    main()