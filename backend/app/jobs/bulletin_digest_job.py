#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📻 Bulletin & Digest Job + 🎙️ Audio Generation
جدولة النشرة والموجز مع توليد الصوت تلقائياً

المسار: app/jobs/bulletin_digest_job.py

الجدولة:
- النشرة: كل 15 دقيقة
- الموجز: كل 10 دقائق

المنطق:
- إذا في أخبار جديدة → INSERT سجل جديد → توليد صوت
- إذا نفس الأخبار → SKIP (لا شيء)
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================
# 🎙️ توليد الصوت
# ============================================

def generate_audio_for_bulletin(bulletin_id: int) -> bool:
    """
    توليد صوت للنشرة
    
    Args:
        bulletin_id: رقم النشرة
        
    Returns:
        bool: True إذا نجح
    """
    try:
        from app.services.generators.bulletin_audio_generator import BulletinAudioGenerator
        
        logger.info(f"🎙️ توليد صوت للنشرة #{bulletin_id}...")
        
        gen = BulletinAudioGenerator()
        try:
            result = gen.generate_for_bulletin(bulletin_id, force_update=False)
            
            if result.success:
                logger.info(f"✅ تم توليد صوت النشرة: {result.audio_url}")
                return True
            else:
                logger.warning(f"⚠️ فشل توليد صوت النشرة: {result.error_message}")
                return False
                
        finally:
            gen.close()
            
    except Exception as e:
        logger.error(f"❌ خطأ في توليد صوت النشرة: {e}")
        return False


def generate_audio_for_digest(digest_id: int) -> bool:
    """
    توليد صوت للموجز
    
    Args:
        digest_id: رقم الموجز
        
    Returns:
        bool: True إذا نجح
    """
    try:
        from app.services.generators.bulletin_audio_generator import BulletinAudioGenerator
        
        logger.info(f"🎙️ توليد صوت للموجز #{digest_id}...")
        
        gen = BulletinAudioGenerator()
        try:
            result = gen.generate_for_digest(digest_id, force_update=False)
            
            if result.success:
                logger.info(f"✅ تم توليد صوت الموجز: {result.audio_url}")
                return True
            else:
                logger.warning(f"⚠️ فشل توليد صوت الموجز: {result.error_message}")
                return False
                
        finally:
            gen.close()
            
    except Exception as e:
        logger.error(f"❌ خطأ في توليد صوت الموجز: {e}")
        return False


# ============================================
# 📻 النشرة الإخبارية
# ============================================

def generate_bulletin_job():
    """
    توليد النشرة الإخبارية + الصوت
    
    - صباحية: من 6 صباحاً حتى 2 ظهراً
    - مسائية: من 2 ظهراً حتى 12 ليلاً
    
    يتم التحديث كل 15 دقيقة بأحدث الأخبار
    إذا لم تتغير الأخبار → SKIP
    """
    from app.services.generators.bulletin_generator import BulletinGenerator
    
    current_hour = datetime.now().hour
    
    # تحديد نوع النشرة حسب الوقت
    if 6 <= current_hour < 14:
        bulletin_type = "صباحية"
    else:
        bulletin_type = "مسائية"
    
    logger.info(f"📻 بدء توليد النشرة {bulletin_type}...")
    
    gen = None
    try:
        gen = BulletinGenerator()
        result = gen.generate_bulletin(
            bulletin_type=bulletin_type,
            report_count=12,
            hours_back=48
        )
        
        if result.success:
            if result.skipped:
                logger.info(f"⏭️ النشرة {bulletin_type}: SKIP (نفس الأخبار)")
            else:
                logger.info(f"✅ تم توليد النشرة {bulletin_type} (ID: {result.bulletin_id})")
                logger.info(f"   📊 {result.news_count} خبر، {result.word_count} كلمة، {result.duration_seconds//60} دقيقة")
                
                # ════════════════════════════════════════════════════════
                # 🎙️ NEW: توليد الصوت للنشرة الجديدة
                # ════════════════════════════════════════════════════════
                if result.bulletin_id:
                    generate_audio_for_bulletin(result.bulletin_id)
                # ════════════════════════════════════════════════════════
                
        else:
            logger.warning(f"⚠️ فشل توليد النشرة: {result.message}")
            
        return result
        
    except Exception as e:
        logger.error(f"❌ خطأ في توليد النشرة: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        if gen:
            gen.close()


# ============================================
# 📰 الموجز الإخباري
# ============================================

def generate_digest_job():
    """
    توليد الموجز الإخباري + الصوت
    
    يتم التحديث كل 10 دقائق بأحدث الأخبار
    إذا لم تتغير الأخبار → SKIP
    
    الساعة = الساعة الحالية (مثل النشرة بالضبط)
    """
    from app.services.generators.digest_generator import DigestGenerator
    
    # ═══════════════════════════════════════════════════════════
    # 🕐 استخدام الساعة الحالية (مثل النشرة بالضبط)
    # ═══════════════════════════════════════════════════════════
    current_hour = datetime.now().hour
    
    logger.info(f"📰 بدء توليد موجز الساعة {current_hour}:00...")
    
    gen = None
    try:
        gen = DigestGenerator()
        result = gen.generate_digest(
            broadcast_hour=current_hour,  # الساعة الحالية
            report_count=10,
            hours_back=48
        )
        
        if result.success:
            if result.skipped:
                logger.info(f"⏭️ الموجز: SKIP (نفس الأخبار)")
            else:
                logger.info(f"✅ تم توليد الموجز (ID: {result.digest_id})")
                logger.info(f"   📊 {result.news_count} خبر، {result.duration_seconds} ثانية")
                
                # ════════════════════════════════════════════════════════
                # 🎙️ NEW: توليد الصوت للموجز الجديد
                # ════════════════════════════════════════════════════════
                if result.digest_id:
                    generate_audio_for_digest(result.digest_id)
                # ════════════════════════════════════════════════════════
                
        else:
            logger.warning(f"⚠️ فشل توليد الموجز: {result.message}")
            
        return result
        
    except Exception as e:
        logger.error(f"❌ خطأ في توليد الموجز: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        if gen:
            gen.close()


# ============================================
# 🔄 توليد الاثنين معاً
# ============================================

def generate_all():
    """توليد النشرة والموجز معاً (مع الصوت)"""
    logger.info("="*60)
    logger.info("🔄 بدء توليد النشرة والموجز...")
    logger.info("="*60)
    
    # توليد النشرة (+ صوت)
    bulletin_result = generate_bulletin_job()
    
    # توليد الموجز (+ صوت)
    digest_result = generate_digest_job()
    
    logger.info("="*60)
    logger.info("✅ انتهى التوليد")
    logger.info("="*60)
    
    return {
        'bulletin': bulletin_result,
        'digest': digest_result
    }


# ============================================
# 🧪 اختبار
# ============================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*60)
    print("🧪 اختبار Bulletin & Digest Job + Audio")
    print("="*60)
    print(f"🕐 الوقت الحالي: {datetime.now().strftime('%H:%M:%S')}")
    
    current_hour = datetime.now().hour
    bulletin_type = "صباحية" if 6 <= current_hour < 14 else "مسائية"
    print(f"📻 نوع النشرة: {bulletin_type}")
    print(f"📰 ساعة الموجز: {current_hour}:00")
    print("="*60)
    
    # اختبار النشرة (+ صوت)
    print("\n📻 اختبار النشرة + الصوت...")
    bulletin_result = generate_bulletin_job()
    
    # اختبار الموجز (+ صوت)
    print("\n📰 اختبار الموجز + الصوت...")
    digest_result = generate_digest_job()
    
    # ملخص
    print("\n" + "="*60)
    print("📊 الملخص:")
    print("="*60)
    
    if bulletin_result:
        if bulletin_result.skipped:
            print(f"📻 النشرة: ⏭️ SKIP")
        else:
            print(f"📻 النشرة: ✅ ID={bulletin_result.bulletin_id} + 🎙️ صوت")
    
    if digest_result:
        if digest_result.skipped:
            print(f"📰 الموجز: ⏭️ SKIP")
        else:
            print(f"📰 الموجز: ✅ ID={digest_result.digest_id} + 🎙️ صوت")
    
    print("\n✅ انتهى الاختبار!")