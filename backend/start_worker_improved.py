#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔄 Sequential Pipeline Scheduler with Cycle Pattern
═══════════════════════════════════════════════════════════════
نظام دورات متتالية:
- دورتين أساسيتين (Main Cycle) 
- دورة واحدة للنشرة (Broadcast Cycle)
- ثم يعيد النمط

Main Cycle (Sequential):
┌─────────────────────────────────────────────────────────────┐
│  1. 📥 Scraping (جمع الأخبار)                               │
│  2. 🔄 Clustering (تجميع الأخبار)                          │
│  3. 📝 Social Media Generation (توليد محتوى السوشال ميديا)   │
│  4. 🖼️ Image Generation (توليد الصور)                      │
│  5. 🎵 Audio Generation (توليد الصوت)                      │
│  6. 📱 Social Media Image Generation (صور السوشال ميديا)    │
│  7. 🎬 Reel Generation (توليد الريلز)                       │
│  8. 📤 Publishing (النشر)                                   │
└─────────────────────────────────────────────────────────────┘

Broadcast Cycle:
┌─────────────────────────────────────────────────────────────┐
│  📻 Broadcast Generation (توليد النشرة والموجز)            │
└─────────────────────────────────────────────────────────────┘

Pattern: Main → Main → Broadcast → Main → Main → Broadcast...
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
    global generate_all_broadcasts, run_audio_transcription_job
    
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
    from app.jobs.audio_transcription_job import run_audio_transcription_job as _run_audio_transcription_job
    
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
    run_audio_transcription_job = timeout_job_by_type('audio')(_run_audio_transcription_job)
    
    logger.info("✅ All jobs imported with timeout protection")
    logger.info("📋 Main Cycle Jobs:")
    logger.info("   📥 scrape_news")
    logger.info("   🎙️ audio_transcription (STT)")
    logger.info("   🔄 cluster_news")
    logger.info("   📝 generate_reports")
    logger.info("   📱 generate_social_media_content")
    logger.info("   🖼️ generate_images")
    logger.info("   🎵 generate_audio")
    logger.info("   📱 generate_social_media_images")
    logger.info("   🎬 generate_reels")
    logger.info("   📤 publish_to_social_media")
    logger.info("📋 Broadcast Cycle Jobs:")
    logger.info("   📻 generate_all_broadcasts")


# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

# الفترة الأساسية بين الدورات (بالثواني)
BASE_CYCLE_INTERVAL = int(os.getenv('CYCLE_INTERVAL', 120))  # 2 دقيقة default  

# نمط الدورات: نشرة أولاً ثم دورتين أساسيتين
CYCLE_PATTERN = ['broadcast', 'main', 'main']  # Broadcast → Main → Main → repeat


# ═══════════════════════════════════════════════════════════════
# Job Execution
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# Job Execution
# ═══════════════════════════════════════════════════════════════

def run_job_sequential(job_name: str, job_func) -> Dict:
    """
    تشغيل job واحد مع timeout protection
    """
    job_start = datetime.now()
    logger.info(f"▶️  Starting: {job_name}")
    
    try:
        result = job_func()
        duration = (datetime.now() - job_start).total_seconds()
        
        if result.get('skipped'):
            logger.info(f"⏭️  {job_name}: Skipped ({result.get('reason', 'no reason')})")
            return {'success': True, 'skipped': True, 'duration': duration}
        elif result.get('error'):
            logger.error(f"❌ {job_name}: Error - {result.get('error')}")
            return {'success': False, 'error': result.get('error'), 'duration': duration}
        else:
            logger.info(f"✅ {job_name}: Completed in {duration:.1f}s")
            return {'success': True, 'duration': duration}
    
    except Exception as e:
        duration = (datetime.now() - job_start).total_seconds()
        logger.error(f"❌ {job_name}: Exception - {e}")
        return {'success': False, 'error': str(e), 'duration': duration}


def run_main_cycle() -> Dict:
    """
    تشغيل الدورة الأساسية (Sequential Pipeline)
    """
    logger.info(f"\n{'═'*70}")
    logger.info(f"🔄 MAIN CYCLE - Sequential Pipeline")
    logger.info(f"{'═'*70}")
    
    cycle_start = datetime.now()
    results = {}
    
    # تسلسل الـ jobs في الدورة الأساسية
    main_jobs = [
        ('scraping', scrape_news),
        ('audio_transcription', run_audio_transcription_job),
        ('clustering', cluster_news),
        ('reports', generate_reports),
        ('social_media_content', generate_social_media_content),
        ('images', generate_images),
        ('audio', generate_audio),
        ('social_media_images', generate_social_media_images),
        ('reels', generate_reels),
        ('publishing', publish_to_social_media),
    ]
    
    # تشغيل كل job بالترتيب
    for job_name, job_func in main_jobs:
        # تشغيل الـ job
        job_result = run_job_sequential(job_name, job_func)
        results[job_name] = job_result
        
        # إذا فشل job مهم، توقف
        if not job_result['success'] and not job_result.get('skipped'):
            # Jobs مهمة لا يمكن تخطيها
            critical_jobs = ['scraping', 'clustering', 'reports']
            if job_name in critical_jobs:
                logger.error(f"💥 Critical job {job_name} failed - stopping main cycle")
                break
        
        # فترة راحة قصيرة بين الـ jobs (5 ثواني)
        if job_name != main_jobs[-1][0]:  # ما عدا آخر job
            logger.info(f"⏳ Waiting 5s before next job...")
            time.sleep(5)
    
    cycle_duration = (datetime.now() - cycle_start).total_seconds()
    
    # إحصائيات الدورة الأساسية
    successful_jobs = sum(1 for r in results.values() if r['success'])
    total_jobs = len(results)
    
    logger.info(f"\n📊 Main Cycle Summary:")
    logger.info(f"   Duration: {cycle_duration:.1f}s ({cycle_duration/60:.1f} min)")
    logger.info(f"   Success: {successful_jobs}/{total_jobs} jobs")
    
    for job_name, job_result in results.items():
        if job_result.get('skipped'):
            status = "⏭️ SKIPPED"
        elif job_result.get('success'):
            status = "✅ SUCCESS"
        else:
            status = "❌ FAILED"
        
        duration = job_result.get('duration', 0)
        logger.info(f"   {status} {job_name}: {duration:.1f}s")
    
    logger.info(f"{'═'*70}")
    
    return {
        'type': 'main',
        'duration': cycle_duration,
        'results': results,
        'stats': {
            'total': total_jobs,
            'successful': successful_jobs,
            'failed': total_jobs - successful_jobs
        }
    }


def run_broadcast_cycle() -> Dict:
    """
    تشغيل دورة النشرة (Broadcast Only)
    """
    logger.info(f"\n{'═'*70}")
    logger.info(f"📻 BROADCAST CYCLE - Newsletter & Digest")
    logger.info(f"{'═'*70}")
    
    cycle_start = datetime.now()
    results = {}
    
    # تشغيل النشرة والموجز
    broadcast_result = run_job_sequential('broadcast', generate_all_broadcasts)
    results['broadcast'] = broadcast_result
    
    cycle_duration = (datetime.now() - cycle_start).total_seconds()
    
    # إحصائيات دورة النشرة
    logger.info(f"\n📊 Broadcast Cycle Summary:")
    logger.info(f"   Duration: {cycle_duration:.1f}s ({cycle_duration/60:.1f} min)")
    
    if broadcast_result.get('skipped'):
        status = "⏭️ SKIPPED"
    elif broadcast_result.get('success'):
        status = "✅ SUCCESS"
    else:
        status = "❌ FAILED"
    
    duration = broadcast_result.get('duration', 0)
    logger.info(f"   {status} broadcast: {duration:.1f}s")
    logger.info(f"{'═'*70}")
    
    return {
        'type': 'broadcast',
        'duration': cycle_duration,
        'results': results,
        'stats': {
            'total': 1,
            'successful': 1 if broadcast_result['success'] else 0,
            'failed': 0 if broadcast_result['success'] else 1
        }
    }


# ═══════════════════════════════════════════════════════════════
# Main Cycle
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# Main Cycle Logic
# ═══════════════════════════════════════════════════════════════

def run_cycle(cycle_number: int) -> Dict:
    """
    تشغيل دورة حسب النمط المحدد
    """
    cycle_start = datetime.now()
    
    # تحديد نوع الدورة حسب النمط
    pattern_index = (cycle_number - 1) % len(CYCLE_PATTERN)
    cycle_type = CYCLE_PATTERN[pattern_index]
    
    logger.info("\n" + "═"*70)
    logger.info(f"🔄 CYCLE #{cycle_number} ({cycle_type.upper()}) started at {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Pattern: {' → '.join(CYCLE_PATTERN)} (position {pattern_index + 1})")
    logger.info("═"*70)
    
    # تشغيل الدورة المناسبة
    if cycle_type == 'main':
        result = run_main_cycle()
    elif cycle_type == 'broadcast':
        result = run_broadcast_cycle()
    else:
        logger.error(f"❌ Unknown cycle type: {cycle_type}")
        return {
            'cycle': cycle_number,
            'type': cycle_type,
            'duration': 0,
            'error': f'Unknown cycle type: {cycle_type}'
        }
    
    # إضافة معلومات الدورة
    result['cycle'] = cycle_number
    result['cycle_type'] = cycle_type
    result['pattern_position'] = pattern_index + 1
    
    total_duration = (datetime.now() - cycle_start).total_seconds()
    
    logger.info("\n" + "═"*70)
    logger.info(f"📊 CYCLE #{cycle_number} ({cycle_type.upper()}) Summary")
    logger.info("═"*70)
    logger.info(f"Total Duration: {total_duration:.1f}s ({total_duration/60:.1f} min)")
    logger.info(f"Pattern Position: {pattern_index + 1}/{len(CYCLE_PATTERN)} ({cycle_type})")
    
    stats = result.get('stats', {})
    successful = stats.get('successful', 0)
    total = stats.get('total', 0)
    failed = stats.get('failed', 0)
    
    logger.info(f"Jobs: {successful}✅ {failed}❌ / {total} total")
    
    # عرض الـ job التالي
    next_pattern_index = cycle_number % len(CYCLE_PATTERN)
    next_cycle_type = CYCLE_PATTERN[next_pattern_index]
    logger.info(f"Next Cycle: #{cycle_number + 1} ({next_cycle_type.upper()})")
    logger.info("═"*70 + "\n")
    
    return result


# ═══════════════════════════════════════════════════════════════
# Manual Job Execution (for API)
# ═══════════════════════════════════════════════════════════════

def run_job_now(task_type: str) -> bool:
    """
    تشغيل job يدوياً من الـ API
    
    Args:
        task_type: نوع الـ task (مثل: audio_transcription, clustering, etc.)
    
    Returns:
        bool: نجح أو لا
    """
    try:
        # Import the specific job
        if task_type == 'audio_transcription':
            from app.jobs.audio_transcription_job import run_audio_transcription_job
            result = run_audio_transcription_job()
            return result.get('success', 0) > 0 or result.get('processed', 0) == 0
            
        elif task_type == 'scraping':
            from app.jobs.scraper_job import scrape_news
            result = scrape_news()
            return not result.get('error')
            
        elif task_type == 'clustering':
            from app.jobs.clustering_job import cluster_news
            result = cluster_news()
            return not result.get('error')
            
        elif task_type == 'report_generation':
            from app.jobs.reports_job import generate_reports
            result = generate_reports()
            return not result.get('error')
            
        elif task_type == 'social_media_generation':
            from app.jobs.social_media_job import generate_social_media_content
            result = generate_social_media_content()
            return not result.get('error')
            
        elif task_type == 'image_generation':
            from app.jobs.image_generation_job import generate_images
            result = generate_images()
            return not result.get('error')
            
        elif task_type == 'audio_generation':
            from app.jobs.audio_generation_job import generate_audio
            result = generate_audio()
            return not result.get('error')
            
        elif task_type == 'bulletin_generation' or task_type == 'digest_generation':
            from app.jobs.broadcast_job import generate_all_broadcasts
            result = generate_all_broadcasts()
            return not result.get('error')
            
        else:
            logger.error(f"Unknown task type: {task_type}")
            return False
            
    except Exception as e:
        logger.error(f"Error running job {task_type}: {e}")
        traceback.print_exc()
        return False


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
    logger.info("🚀 Sequential Pipeline Scheduler Starting")
    logger.info("   ✅ Sequential job execution")
    logger.info("   ✅ Individual job timeouts")
    logger.info("   ✅ Cycle pattern system")
    logger.info("   ✅ Error isolation")
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
    logger.info("Cycle Pattern:")
    for i, cycle_type in enumerate(CYCLE_PATTERN, 1):
        logger.info(f"  {i}. {cycle_type.upper()} Cycle")
    logger.info(f"  Pattern repeats every {len(CYCLE_PATTERN)} cycles")
    logger.info("")
    logger.info("Main Cycle Jobs (Sequential):")
    logger.info("  1. 📥 Scraping")
    logger.info("  2. 🎙️ Audio Transcription (STT)")
    logger.info("  3. 🔄 Clustering") 
    logger.info("  4. 📝 Reports Generation")
    logger.info("  5. 📱 Social Media Content")
    logger.info("  6. 🖼️ Image Generation")
    logger.info("  7. 🎵 Audio Generation")
    logger.info("  8. 📱 Social Media Images")
    logger.info("  9. 🎬 Reel Generation")
    logger.info("  10. 📤 Publishing")
    logger.info("")
    logger.info("Broadcast Cycle Jobs:")
    logger.info("  1. 📻 Newsletter & Digest Generation")
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
            if 'error' in cycle_result:
                logger.error(f"❌ Cycle #{cycle_number} failed: {cycle_result['error']}")
            else:
                stats = cycle_result.get('stats', {})
                cycle_type = cycle_result.get('cycle_type', 'unknown')
                
                if stats.get('failed', 0) > 0:
                    logger.warning(f"⚠️  {stats['failed']} jobs failed in {cycle_type} cycle #{cycle_number}")
                else:
                    logger.info(f"✅ {cycle_type.title()} cycle #{cycle_number} completed successfully")
            
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
    logger.info("🛑 Sequential Pipeline Scheduler stopped gracefully")
    logger.info("═"*70)


if __name__ == "__main__":
    main()