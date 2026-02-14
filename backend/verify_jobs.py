#!/usr/bin/env python3
"""
🔍 Job Verification Script
═══════════════════════════════════════════════════════════════
يتحقق من وجود كل الـ jobs ويختبر الـ imports

Usage:
    python verify_jobs.py
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import logging
from pathlib import Path

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_job_files():
    """تحقق من وجود ملفات الـ jobs"""
    logger.info("🔍 Checking job files...")
    
    job_files = [
        "app/jobs/scraper_job.py",
        "app/jobs/clustering_job.py", 
        "app/jobs/reports_job.py",
        "app/jobs/social_media_job.py",
        "app/jobs/image_generation_job.py",
        "app/jobs/audio_generation_job.py",
        "app/jobs/social_media_image_job.py",
        "app/jobs/reel_generation_job.py",
        "app/jobs/publishers_job.py",
        "app/jobs/broadcast_job.py",
        "app/jobs/bulletin_digest_job.py",
        "app/jobs/processing_pipeline_job.py",
    ]
    
    missing_files = []
    for job_file in job_files:
        if Path(job_file).exists():
            logger.info(f"✅ {job_file}")
        else:
            logger.error(f"❌ {job_file}")
            missing_files.append(job_file)
    
    return len(missing_files) == 0


def check_job_imports():
    """تحقق من إمكانية import الـ jobs"""
    logger.info("\n🔍 Checking job imports...")
    
    jobs_to_test = [
        ("app.jobs.scraper_job", "scrape_news"),
        ("app.jobs.clustering_job", "cluster_news"),
        ("app.jobs.reports_job", "generate_reports"),
        ("app.jobs.social_media_job", "generate_social_media_content"),
        ("app.jobs.image_generation_job", "generate_images"),
        ("app.jobs.audio_generation_job", "generate_audio"),
        ("app.jobs.social_media_image_job", "generate_social_media_images"),
        ("app.jobs.reel_generation_job", "generate_reels"),
        ("app.jobs.publishers_job", "publish_to_social_media"),
        ("app.jobs.broadcast_job", "generate_all_broadcasts"),
        ("app.jobs.broadcast_job", "generate_bulletin_job"),
        ("app.jobs.broadcast_job", "generate_digest_job"),
    ]
    
    failed_imports = []
    
    for module_name, function_name in jobs_to_test:
        try:
            module = __import__(module_name, fromlist=[function_name])
            func = getattr(module, function_name)
            logger.info(f"✅ {module_name}.{function_name}")
        except ImportError as e:
            logger.error(f"❌ {module_name}.{function_name} - Import Error: {e}")
            failed_imports.append((module_name, function_name))
        except AttributeError as e:
            logger.error(f"❌ {module_name}.{function_name} - Function not found: {e}")
            failed_imports.append((module_name, function_name))
        except Exception as e:
            logger.error(f"❌ {module_name}.{function_name} - Error: {e}")
            failed_imports.append((module_name, function_name))
    
    return len(failed_imports) == 0


def check_worker_imports():
    """تحقق من إمكانية import الـ worker utilities"""
    logger.info("\n🔍 Checking worker utilities...")
    
    utilities = [
        ("app.utils.job_timeout", ["timeout_job", "timeout_job_by_type", "get_job_timeout"]),
        ("app.utils.parallel_executor", ["ParallelJobExecutor", "run_jobs_parallel"]),
    ]
    
    failed_imports = []
    
    for module_name, functions in utilities:
        try:
            module = __import__(module_name, fromlist=functions)
            for func_name in functions:
                func = getattr(module, func_name)
                logger.info(f"✅ {module_name}.{func_name}")
        except ImportError as e:
            logger.error(f"❌ {module_name} - Import Error: {e}")
            failed_imports.append(module_name)
        except AttributeError as e:
            logger.error(f"❌ {module_name} - Function not found: {e}")
            failed_imports.append(module_name)
        except Exception as e:
            logger.error(f"❌ {module_name} - Error: {e}")
            failed_imports.append(module_name)
    
    return len(failed_imports) == 0


def test_timeout_functionality():
    """اختبار وظائف الـ timeout"""
    logger.info("\n🔍 Testing timeout functionality...")
    
    try:
        from app.utils.job_timeout import get_job_timeout, is_timeout_enabled
        
        # Test timeout values
        timeouts = {
            'scraping': get_job_timeout('scraping'),
            'clustering': get_job_timeout('clustering'),
            'images': get_job_timeout('images'),
            'video': get_job_timeout('video'),
            'default': get_job_timeout('unknown_job_type'),
        }
        
        logger.info("⏰ Timeout values:")
        for job_type, timeout in timeouts.items():
            logger.info(f"   {job_type}: {timeout}s")
        
        # Test timeout enabled status
        enabled = is_timeout_enabled()
        logger.info(f"⚙️  Timeouts enabled: {enabled}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Timeout functionality test failed: {e}")
        return False


def check_environment_variables():
    """تحقق من الـ environment variables"""
    logger.info("\n🔍 Checking environment variables...")
    
    env_vars = [
        'WORKER_TYPE',
        'MAX_PARALLEL_JOBS', 
        'ENABLE_JOB_TIMEOUTS',
        'ENABLE_PARALLEL_EXECUTION',
        'BROADCAST_MODE',
        'SCRAPING_TIMEOUT',
        'IMAGES_TIMEOUT',
        'VIDEO_TIMEOUT',
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"✅ {var}={value}")
        else:
            logger.info(f"ℹ️  {var}=<not set> (will use default)")
    
    return True


def main():
    """Main verification function"""
    logger.info("=" * 70)
    logger.info("🔍 Job Verification Started")
    logger.info("=" * 70)
    
    all_passed = True
    
    # Check job files
    if not check_job_files():
        all_passed = False
    
    # Check job imports
    if not check_job_imports():
        all_passed = False
    
    # Check worker utilities
    if not check_worker_imports():
        all_passed = False
    
    # Test timeout functionality
    if not test_timeout_functionality():
        all_passed = False
    
    # Check environment variables
    check_environment_variables()
    
    # Summary
    logger.info("\n" + "=" * 70)
    if all_passed:
        logger.info("🎉 All verifications PASSED!")
        logger.info("✅ The improved worker should work correctly")
    else:
        logger.error("❌ Some verifications FAILED!")
        logger.error("⚠️  Please fix the issues before using the improved worker")
    logger.info("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)