#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔄 Sequential Task Scheduler
═══════════════════════════════════════════════════════════════
يشغل الـ jobs بالترتيب بدل parallel
أفضل للموارد المحدودة ويضمن الترتيب الصحيح

Flow:
┌─────────────────────────────────────────────────────────────┐
│  Loop كل 2 دقيقة:                                           │
│                                                             │
│  1. 📥 Scraping (كل cycle)                                  │
│  2. 🔄 Processing: cluster → report → social (كل cycle)     │
│  3. 🎨 Media: image → audio (كل cycle ثاني)                 │
│  4. 📤 Publishing: social_img → reel → publish (كل 3 cycles)│
│  5. 📻 Broadcast (كل 3 cycles)                              │
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
        logging.FileHandler(f'{log_dir}/worker.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Job Imports (Lazy Loading)
# ═══════════════════════════════════════════════════════════════

def import_jobs():
    """Import all job functions"""
    global scrape_news, cluster_news, generate_reports
    global generate_social_media_content, generate_images, generate_audio
    global generate_social_media_images, generate_reels, publish_to_social_media
    global generate_all_broadcasts
    
    from app.jobs.scraper_job import scrape_news
    from app.jobs.clustering_job import cluster_news
    from app.jobs.reports_job import generate_reports
    from app.jobs.social_media_job import generate_social_media_content
    from app.jobs.image_generation_job import generate_images
    from app.jobs.audio_generation_job import generate_audio
    from app.jobs.social_media_image_job import generate_social_media_images
    from app.jobs.reel_generation_job import generate_reels
    from app.jobs.publishers_job import publish_to_social_media
    from app.jobs.broadcast_job import generate_all_broadcasts
    
    logger.info("✅ All jobs imported successfully")


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


# ═══════════════════════════════════════════════════════════════
# Job Execution
# ═══════════════════════════════════════════════════════════════

def run_job(name: str, func, skip_on_error: bool = True) -> Dict:
    """
    تشغيل job واحد مع logging
    
    Args:
        name: اسم الـ job للـ logging
        func: الدالة اللي تشغلها
        skip_on_error: تكمل حتى لو فشل؟
    
    Returns:
        dict: نتيجة التشغيل
    """
    logger.info(f"▶️  Starting: {name}")
    start_time = datetime.now()
    
    try:
        result = func()
        duration = (datetime.now() - start_time).total_seconds()
        
        if result.get('skipped'):
            logger.info(f"⏭️  {name}: Skipped ({result.get('reason', 'no reason')})")
        elif result.get('error'):
            logger.error(f"❌ {name}: Error - {result.get('error')}")
        else:
            logger.info(f"✅ {name}: Completed in {duration:.1f}s")
        
        return {
            'success': not result.get('error'),
            'skipped': result.get('skipped', False),
            'duration': duration,
            'result': result
        }
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ {name}: Exception - {e}")
        
        if not skip_on_error:
            raise
        
        return {
            'success': False,
            'skipped': False,
            'duration': duration,
            'error': str(e)
        }


def run_group(group_name: str, jobs: list) -> Dict:
    """
    تشغيل مجموعة jobs بالترتيب
    
    Args:
        group_name: اسم المجموعة
        jobs: قائمة (name, func) للـ jobs
    
    Returns:
        dict: نتائج كل الـ jobs
    """
    logger.info(f"\n{'─'*60}")
    logger.info(f"🔷 GROUP: {group_name}")
    logger.info(f"{'─'*60}")
    
    group_start = datetime.now()
    results = {}
    
    for job_name, job_func in jobs:
        results[job_name] = run_job(job_name, job_func)
        
        # فترة راحة قصيرة بين الـ jobs
        time.sleep(2)
    
    group_duration = (datetime.now() - group_start).total_seconds()
    logger.info(f"🔷 GROUP {group_name} completed in {group_duration:.1f}s")
    
    return results


# ═══════════════════════════════════════════════════════════════
# Main Cycle
# ═══════════════════════════════════════════════════════════════

def run_cycle(cycle_number: int) -> Dict:
    """
    تشغيل دورة كاملة
    
    Args:
        cycle_number: رقم الدورة (يبدأ من 1)
    
    Returns:
        dict: نتائج الدورة
    """
    cycle_start = datetime.now()
    
    logger.info("\n" + "═"*70)
    logger.info(f"🔄 CYCLE #{cycle_number} started at {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("═"*70)
    
    results = {}
    
    # ───────────────────────────────────────────────────────────
    # Group 1: Data Ingestion (Scraping)
    # يشتغل كل دورة
    # ───────────────────────────────────────────────────────────
    if cycle_number % CYCLE_CONFIG['scraping'] == 0:
        results['scraping'] = run_group('DATA INGESTION', [
            ('scraping', scrape_news),
        ])
    
    # ───────────────────────────────────────────────────────────
    # Group 2: Processing (Cluster → Report → Social Text)
    # يشتغل كل دورة
    # ───────────────────────────────────────────────────────────
    if cycle_number % CYCLE_CONFIG['processing'] == 0:
        results['processing'] = run_group('PROCESSING', [
            ('clustering', cluster_news),
            ('reports', generate_reports),
            ('social_media_text', generate_social_media_content),
        ])
    
    # ───────────────────────────────────────────────────────────
    # Group 3: Media Generation (Image + Audio)
    # يشتغل كل دورتين
    # ───────────────────────────────────────────────────────────
    if cycle_number % CYCLE_CONFIG['media_generation'] == 0:
        results['media'] = run_group('MEDIA GENERATION', [
            ('images', generate_images),
            ('audio', generate_audio),
        ])
    
    # ───────────────────────────────────────────────────────────
    # Group 4: Publishing (Social Image → Reel → Publish)
    # يشتغل كل 3 دورات
    # ───────────────────────────────────────────────────────────
    if cycle_number % CYCLE_CONFIG['publishing'] == 0:
        results['publishing'] = run_group('PUBLISHING', [
            ('social_media_images', generate_social_media_images),
            ('reels', generate_reels),
            ('publishers', publish_to_social_media),
        ])
    
    # ───────────────────────────────────────────────────────────
    # Group 5: Broadcast (Bulletin + Digest)
    # يشتغل كل 3 دورات
    # ───────────────────────────────────────────────────────────
    if cycle_number % CYCLE_CONFIG['broadcast'] == 0:
        results['broadcast'] = run_group('BROADCAST', [
            ('broadcast', generate_all_broadcasts),
        ])
    
    # ───────────────────────────────────────────────────────────
    # Summary
    # ───────────────────────────────────────────────────────────
    cycle_duration = (datetime.now() - cycle_start).total_seconds()
    
    logger.info("\n" + "═"*70)
    logger.info(f"📊 CYCLE #{cycle_number} Summary")
    logger.info("═"*70)
    logger.info(f"Duration: {cycle_duration:.1f}s ({cycle_duration/60:.1f} min)")
    
    for group_name, group_results in results.items():
        logger.info(f"\n  {group_name}:")
        for job_name, job_result in group_results.items():
            if job_result.get('skipped'):
                status = "⏭️"
            elif job_result.get('success'):
                status = "✅"
            else:
                status = "❌"
            logger.info(f"    {status} {job_name}: {job_result.get('duration', 0):.1f}s")
    
    logger.info("═"*70 + "\n")
    
    return {
        'cycle': cycle_number,
        'duration': cycle_duration,
        'results': results
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
    logger.info("🚀 Sequential Task Scheduler Starting")
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
    logger.info("Schedule:")
    logger.info(f"  📥 Scraping:    every {CYCLE_CONFIG['scraping']} cycle(s)")
    logger.info(f"  🔄 Processing:  every {CYCLE_CONFIG['processing']} cycle(s)")
    logger.info(f"  🎨 Media:       every {CYCLE_CONFIG['media_generation']} cycle(s)")
    logger.info(f"  📤 Publishing:  every {CYCLE_CONFIG['publishing']} cycle(s)")
    logger.info(f"  📻 Broadcast:   every {CYCLE_CONFIG['broadcast']} cycle(s)")
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
            run_cycle(cycle_number)
            
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
    logger.info("🛑 Scheduler stopped gracefully")
    logger.info("═"*70)


if __name__ == "__main__":
    main()