#!/usr/bin/env python3
"""
🔄 Worker Switcher Script
═══════════════════════════════════════════════════════════════
Script للتبديل بين الـ worker العادي والمحسن

Usage:
    python switch_worker.py --mode improved    # للـ worker المحسن
    python switch_worker.py --mode original    # للـ worker الأصلي
    python switch_worker.py --status           # لمعرفة الحالة الحالية
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import argparse
import shutil
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_current_worker() -> str:
    """تحديد الـ worker الحالي"""
    dockerfile_path = Path("Dockerfile.worker")
    
    if not dockerfile_path.exists():
        return "unknown"
    
    content = dockerfile_path.read_text()
    
    if "start_worker_improved.py" in content:
        return "improved"
    elif "start_worker.py" in content:
        return "original"
    else:
        return "unknown"


def switch_to_improved():
    """التبديل للـ worker المحسن"""
    logger.info("🔄 Switching to improved worker...")
    
    dockerfile_path = Path("Dockerfile.worker")
    
    if not dockerfile_path.exists():
        logger.error("❌ Dockerfile.worker not found!")
        return False
    
    # Read current content
    content = dockerfile_path.read_text()
    
    # Replace the CMD line
    if "start_worker.py" in content:
        new_content = content.replace(
            'CMD ["python", "start_worker.py"]',
            'CMD ["python", "start_worker_improved.py"]'
        )
        
        # Also update the comment if exists
        new_content = new_content.replace(
            "# Run the worker",
            "# Run the improved worker"
        )
        
        dockerfile_path.write_text(new_content)
        logger.info("✅ Switched to improved worker")
        return True
    else:
        logger.info("ℹ️  Already using improved worker")
        return True


def switch_to_original():
    """التبديل للـ worker الأصلي"""
    logger.info("🔄 Switching to original worker...")
    
    dockerfile_path = Path("Dockerfile.worker")
    
    if not dockerfile_path.exists():
        logger.error("❌ Dockerfile.worker not found!")
        return False
    
    # Read current content
    content = dockerfile_path.read_text()
    
    # Replace the CMD line
    if "start_worker_improved.py" in content:
        new_content = content.replace(
            'CMD ["python", "start_worker_improved.py"]',
            'CMD ["python", "start_worker.py"]'
        )
        
        # Also update the comment if exists
        new_content = new_content.replace(
            "# Run the improved worker",
            "# Run the worker"
        )
        
        dockerfile_path.write_text(new_content)
        logger.info("✅ Switched to original worker")
        return True
    else:
        logger.info("ℹ️  Already using original worker")
        return True


def show_status():
    """عرض حالة الـ worker الحالي"""
    current = get_current_worker()
    
    logger.info("=" * 50)
    logger.info("🔍 Current Worker Status")
    logger.info("=" * 50)
    
    if current == "improved":
        logger.info("✅ Currently using: IMPROVED WORKER")
        logger.info("   Features:")
        logger.info("   - ✅ Parallel job execution")
        logger.info("   - ✅ Individual job timeouts")
        logger.info("   - ✅ Error isolation")
        logger.info("   - ✅ Better monitoring")
    elif current == "original":
        logger.info("📝 Currently using: ORIGINAL WORKER")
        logger.info("   Features:")
        logger.info("   - ✅ Sequential execution")
        logger.info("   - ❌ No timeouts")
        logger.info("   - ❌ No parallel processing")
    else:
        logger.warning("⚠️  Unknown worker configuration")
    
    logger.info("=" * 50)
    
    # Check if files exist
    files_status = {
        "start_worker.py": Path("start_worker.py").exists(),
        "start_worker_improved.py": Path("start_worker_improved.py").exists(),
        "app/utils/job_timeout.py": Path("app/utils/job_timeout.py").exists(),
        "app/utils/parallel_executor.py": Path("app/utils/parallel_executor.py").exists(),
    }
    
    logger.info("📁 File Status:")
    for file, exists in files_status.items():
        status = "✅" if exists else "❌"
        logger.info(f"   {status} {file}")
    
    # Check job files
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
    ]
    
    logger.info("\n📋 Job Files:")
    for job_file in job_files:
        exists = Path(job_file).exists()
        status = "✅" if exists else "❌"
        logger.info(f"   {status} {job_file}")
    
    logger.info("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Switch between worker modes")
    parser.add_argument(
        "--mode", 
        choices=["improved", "original"],
        help="Worker mode to switch to"
    )
    parser.add_argument(
        "--status", 
        action="store_true",
        help="Show current worker status"
    )
    
    args = parser.parse_args()
    
    if args.status:
        show_status()
        return
    
    if not args.mode:
        logger.error("❌ Please specify --mode or --status")
        parser.print_help()
        return
    
    # Change to backend directory if we're in root
    if Path("backend").exists() and not Path("start_worker.py").exists():
        os.chdir("backend")
        logger.info("📁 Changed to backend directory")
    
    if args.mode == "improved":
        success = switch_to_improved()
    elif args.mode == "original":
        success = switch_to_original()
    
    if success:
        logger.info("🎉 Switch completed successfully!")
        logger.info("💡 Don't forget to redeploy on Render to apply changes")
    else:
        logger.error("❌ Switch failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()