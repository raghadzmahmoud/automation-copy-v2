#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 Test Scheduler - Bulletin & Digest Only
تشغيل جدولة النشرة والموجز فقط للاختبار

الاستخدام:
    cd backend
    python test_bulletin_scheduler.py
"""
import certifi, os
os.environ["SSL_CERT_FILE"] = certifi.where()

import logging
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    # Import jobs
    from app.jobs.bulletin_digest_job import generate_bulletin_job, generate_digest_job
    
    scheduler = BackgroundScheduler()
    
    # ════════════════════════════════════════════════════════════
    # 📻 النشرة: كل 15 دقيقة
    # ════════════════════════════════════════════════════════════
    scheduler.add_job(
        generate_bulletin_job,
        trigger=CronTrigger(minute='*/15'),
        id='bulletin_trigger',
        name='📻 Bulletin Generator (Every 15 min)',
        replace_existing=True
    )
    
    # ════════════════════════════════════════════════════════════
    # 📰 الموجز: كل 10 دقائق
    # ════════════════════════════════════════════════════════════
    scheduler.add_job(
        generate_digest_job,
        trigger=CronTrigger(minute='*/10'),
        id='digest_trigger',
        name='📰 Digest Generator (Every 10 min)',
        replace_existing=True
    )
    
    # Start scheduler
    scheduler.start()
    
    current_hour = datetime.now().hour
    bulletin_type = "صباحية" if 6 <= current_hour < 14 else "مسائية"
    
    print("\n" + "="*60)
    print("⏰ Scheduler Started - Bulletin & Digest Only")
    print("="*60)
    print(f"🕐 Current time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"📻 Bulletin type: {bulletin_type}")
    print(f"📰 Digest hour: {current_hour}:00")
    print("="*60)
    print("📻 Bulletin: Every 15 minutes (at :00, :15, :30, :45)")
    print("📰 Digest: Every 10 minutes (at :00, :10, :20, :30, :40, :50)")
    print("="*60)
    
    # Show next run times
    print("\n📅 Next scheduled runs:")
    for job in scheduler.get_jobs():
        print(f"   • {job.name}: {job.next_run_time.strftime('%H:%M:%S')}")
    
    # ════════════════════════════════════════════════════════════
    # 🚀 تشغيل أولي
    # ════════════════════════════════════════════════════════════
    print("\n" + "="*60)
    print("🚀 Running initial generation...")
    print("="*60)
    
    print("\n📻 Generating bulletin...")
    bulletin_result = generate_bulletin_job()
    
    print("\n📰 Generating digest...")
    digest_result = generate_digest_job()
    
    # Summary
    print("\n" + "="*60)
    print("📊 Initial Run Summary:")
    print("="*60)
    if bulletin_result:
        if bulletin_result.skipped:
            print(f"📻 Bulletin: ⏭️ SKIPPED (same news)")
        else:
            print(f"📻 Bulletin: ✅ Created (ID: {bulletin_result.bulletin_id})")
    
    if digest_result:
        if digest_result.skipped:
            print(f"📰 Digest: ⏭️ SKIPPED (same news)")
        else:
            print(f"📰 Digest: ✅ Created (ID: {digest_result.digest_id})")
    
    # ════════════════════════════════════════════════════════════
    # ⏳ انتظار التشغيل المجدول
    # ════════════════════════════════════════════════════════════
    print("\n" + "="*60)
    print("⏳ Waiting for scheduled runs...")
    print("   Press Ctrl+C to stop")
    print("="*60)
    
    try:
        while True:
            time.sleep(60)
            # Show current time every minute
            now = datetime.now()
            print(f"\n🕐 {now.strftime('%H:%M:%S')} - Scheduler running...")
            
            # Show next runs
            for job in scheduler.get_jobs():
                next_run = job.next_run_time
                if next_run:
                    diff = (next_run - now.astimezone()).total_seconds()
                    if diff > 0:
                        mins = int(diff // 60)
                        secs = int(diff % 60)
                        print(f"   • {job.name}: in {mins}m {secs}s")
                        
    except KeyboardInterrupt:
        print("\n\n⏹️ Shutting down scheduler...")
        scheduler.shutdown()
        print("✅ Scheduler stopped")


if __name__ == "__main__":
    main()