#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 Test Scheduler - النشرة والموجز فقط
للمراقبة والاختبار بدون تشغيل باقي الـ pipeline

الجدولة:
- النشرة: كل 15 دقيقة
- الموجز: كل 10 دقائق

التشغيل:
    cd backend
    python test_bulletin_audio_scheduler.py
"""

import time
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# إحصائيات
stats = {
    'bulletins_created': 0,
    'bulletins_skipped': 0,
    'bulletins_audio': 0,
    'digests_created': 0,
    'digests_skipped': 0,
    'digests_audio': 0,
    'start_time': None
}


def run_bulletin_job():
    """توليد النشرة + الصوت"""
    logger.info("="*60)
    logger.info("📻 بدء توليد النشرة...")
    
    try:
        from app.jobs.bulletin_digest_job import generate_bulletin_job
        result = generate_bulletin_job()
        
        if result:
            if result.skipped:
                stats['bulletins_skipped'] += 1
                logger.info("📻 النشرة: ⏭️ SKIP (نفس الأخبار)")
            else:
                stats['bulletins_created'] += 1
                stats['bulletins_audio'] += 1
                logger.info(f"📻 النشرة: ✅ ID={result.bulletin_id} + 🎙️ صوت")
        
    except Exception as e:
        logger.error(f"❌ خطأ في النشرة: {e}")
    
    print_stats()


def run_digest_job():
    """توليد الموجز + الصوت"""
    logger.info("="*60)
    logger.info("📰 بدء توليد الموجز...")
    
    try:
        from app.jobs.bulletin_digest_job import generate_digest_job
        result = generate_digest_job()
        
        if result:
            if result.skipped:
                stats['digests_skipped'] += 1
                logger.info("📰 الموجز: ⏭️ SKIP (نفس الأخبار)")
            else:
                stats['digests_created'] += 1
                stats['digests_audio'] += 1
                logger.info(f"📰 الموجز: ✅ ID={result.digest_id} + 🎙️ صوت")
        
    except Exception as e:
        logger.error(f"❌ خطأ في الموجز: {e}")
    
    print_stats()


def print_stats():
    """طباعة الإحصائيات"""
    elapsed = datetime.now() - stats['start_time']
    minutes = int(elapsed.total_seconds() // 60)
    
    print("\n" + "="*60)
    print("📊 الإحصائيات:")
    print("="*60)
    print(f"⏱️  الوقت المنقضي: {minutes} دقيقة")
    print(f"📻 النشرات: {stats['bulletins_created']} جديدة، {stats['bulletins_skipped']} متخطاة، {stats['bulletins_audio']} صوت")
    print(f"📰 الموجزات: {stats['digests_created']} جديدة، {stats['digests_skipped']} متخطاة، {stats['digests_audio']} صوت")
    print("="*60 + "\n")


def main():
    """التشغيل الرئيسي"""
    print("\n" + "="*60)
    print("🧪 Test Scheduler - النشرة والموجز فقط")
    print("="*60)
    print(f"🕐 وقت البدء: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📻 النشرة: كل 15 دقيقة")
    print("📰 الموجز: كل 10 دقائق")
    print("="*60)
    print("⏹️  للإيقاف: Ctrl+C")
    print("="*60 + "\n")
    
    stats['start_time'] = datetime.now()
    
    # إنشاء الـ scheduler
    scheduler = BackgroundScheduler()
    
    # جدولة النشرة: كل 15 دقيقة
    scheduler.add_job(
        run_bulletin_job,
        trigger=CronTrigger(minute='*/15'),
        id='bulletin_job',
        name='📻 Bulletin (Every 15 min)'
    )
    
    # جدولة الموجز: كل 10 دقائق
    scheduler.add_job(
        run_digest_job,
        trigger=CronTrigger(minute='*/10'),
        id='digest_job',
        name='📰 Digest (Every 10 min)'
    )
    
    # بدء الـ scheduler
    scheduler.start()
    
    # تشغيل أولي فوري
    print("🚀 تشغيل أولي...")
    run_bulletin_job()
    run_digest_job()
    
    # عرض الـ jobs المجدولة
    print("\n📅 الـ Jobs المجدولة:")
    for job in scheduler.get_jobs():
        next_run = job.next_run_time.strftime('%H:%M:%S') if job.next_run_time else 'N/A'
        print(f"   • {job.name} → التالي: {next_run}")
    print()
    
    # الانتظار
    try:
        while True:
            time.sleep(60)
            # طباعة heartbeat كل دقيقة
            elapsed = datetime.now() - stats['start_time']
            minutes = int(elapsed.total_seconds() // 60)
            print(f"💓 [{datetime.now().strftime('%H:%M:%S')}] شغال منذ {minutes} دقيقة...")
            
    except KeyboardInterrupt:
        print("\n\n⏹️ إيقاف...")
        scheduler.shutdown()
        
        # طباعة الإحصائيات النهائية
        print("\n" + "="*60)
        print("📊 الإحصائيات النهائية:")
        print("="*60)
        elapsed = datetime.now() - stats['start_time']
        print(f"⏱️  إجمالي الوقت: {int(elapsed.total_seconds() // 60)} دقيقة")
        print(f"📻 النشرات: {stats['bulletins_created']} جديدة، {stats['bulletins_skipped']} متخطاة")
        print(f"📰 الموجزات: {stats['digests_created']} جديدة، {stats['digests_skipped']} متخطاة")
        print(f"🎙️ ملفات الصوت: {stats['bulletins_audio'] + stats['digests_audio']}")
        print("="*60)
        print("✅ تم الإيقاف بنجاح!")


if __name__ == "__main__":
    main()