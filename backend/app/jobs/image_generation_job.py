#!/usr/bin/env python3
"""
🎨 Image Generation Job (Enhanced - Condition-Based)

✅ التحسينات:
- فصل Image عن باقي الـ pipeline
- تخطي التقارير الفاشلة كتير
- الاستمرار حتى لو فشل تقرير
- تسجيل أفضل للأخطاء

Condition: يشتغل فقط إذا في تقارير بدون صور
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
import psycopg2
from settings import DB_CONFIG

# Logging setup
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'image_generation_job.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

MAX_FAILURE_ATTEMPTS = 3  # تخطي التقارير اللي فشلت أكثر من هذا العدد
REPORTS_PER_RUN = 20      # عدد التقارير لكل تشغيل (زيادة من 10 إلى 20)
CHECK_HOURS = 48          # فحص التقارير من آخر X ساعة


# =============================================================================
# CONDITION CHECK
# =============================================================================

def has_reports_without_images(hours: int = CHECK_HOURS) -> tuple:
    """
    ✅ Condition: هل في تقارير جديدة بدون صور؟
    - يستثني التقارير اللي فشلت كتير
    - يستثني التقارير اللي الـ raw_news تبعها فيها صورة
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # ✅ Query محسن: يستثني التقارير اللي فشلت كتير
        # ويستثني التقارير اللي الأخبار الأصلية فيها صور
        cursor.execute("""
            SELECT COUNT(*) FROM generated_report gr
            WHERE gr.created_at >= NOW() - INTERVAL '%s hours'
            AND gr.status = 'draft'
            -- التقرير ما عنده صورة مولدة
            AND NOT EXISTS (
                SELECT 1 FROM generated_content gc
                WHERE gc.report_id = gr.id
                AND gc.content_type_id = 6
            )
            -- التقرير ما فشل كتير
            AND NOT EXISTS (
                SELECT 1 FROM image_generation_failures igf
                WHERE igf.report_id = gr.id
                AND igf.attempt_count >= %s
            )
            -- الأخبار الأصلية ما فيها صور
            AND NOT EXISTS (
                SELECT 1 FROM news_cluster_members ncm
                JOIN raw_news rn ON ncm.news_id = rn.id
                WHERE ncm.cluster_id = gr.cluster_id
                AND (
                    rn.image_url IS NOT NULL 
                    AND rn.image_url != ''
                    AND rn.image_url != 'null'
                )
            )
        """, (hours, MAX_FAILURE_ATTEMPTS))
        
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return count > 0, count
        
    except psycopg2.errors.UndefinedTable:
        # الجدول مش موجود، نرجع للـ query الأصلي
        logger.warning("image_generation_failures table not found, using simple query")
        return has_reports_without_images_simple(hours)
        
    except Exception as e:
        logger.error(f"Error checking reports without images: {e}")
        return has_reports_without_images_simple(hours)


def has_reports_without_images_simple(hours: int = CHECK_HOURS) -> tuple:
    """Fallback query بدون فلتر الفشل، لكن مع فلتر الصور الأصلية"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM generated_report gr
            WHERE gr.created_at >= NOW() - INTERVAL '%s hours'
            AND gr.status = 'draft'
            -- التقرير ما عنده صورة مولدة
            AND NOT EXISTS (
                SELECT 1 FROM generated_content gc
                WHERE gc.report_id = gr.id
                AND gc.content_type_id = 6
            )
            -- الأخبار الأصلية ما فيها صور
            AND NOT EXISTS (
                SELECT 1 FROM news_cluster_members ncm
                JOIN raw_news rn ON ncm.news_id = rn.id
                WHERE ncm.cluster_id = gr.cluster_id
                AND (
                    rn.image_url IS NOT NULL 
                    AND rn.image_url != ''
                    AND rn.image_url != 'null'
                )
            )
        """, (hours,))
        
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return count > 0, count
        
    except Exception as e:
        logger.error(f"Error in simple check: {e}")
        return False, 0


def get_failed_reports_count() -> int:
    """✅ عدد التقارير المتخطاة بسبب كثرة الفشل"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM image_generation_failures
            WHERE attempt_count >= %s
        """, (MAX_FAILURE_ATTEMPTS,))
        
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
        
    except:
        return 0


# =============================================================================
# MAIN
# =============================================================================

def generate_images() -> dict:
    """Main image generation function"""
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info(f"🎨 Image Generation Job started at {start_time}")
    logger.info(f"⚙️  Config: {REPORTS_PER_RUN} reports/run, skip after {MAX_FAILURE_ATTEMPTS} failures")

    # ✅ Condition Check
    has_work, reports_count = has_reports_without_images(hours=CHECK_HOURS)
    
    if not has_work:
        skipped_count = get_failed_reports_count()
        logger.info("⏭️ No reports without images found, skipping")
        if skipped_count > 0:
            logger.info(f"   ℹ️  {skipped_count} reports skipped due to repeated failures")
        logger.info("=" * 60)
        return {'skipped': True, 'reason': 'no_new_data', 'permanently_skipped': skipped_count}
    
    logger.info(f"📊 Found {reports_count} reports needing images")

    generator = None
    try:
        from app.services.generators.image_generator import ImageGenerator
        
        generator = ImageGenerator()
        
        logger.info(f"⚙️ Limit: {REPORTS_PER_RUN} images per run")
        
        # ✅ تشغيل التوليد
        stats = generator.generate_for_all_reports(
            force_update=False,
            limit=REPORTS_PER_RUN
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"✅ Image generation completed in {duration:.2f}s")
        logger.info(f"📊 Reports processed: {stats.get('total_reports', 0)}")
        logger.info(f"📊 Images created: {stats.get('success', 0)}")
        logger.info(f"📊 Skipped: {stats.get('skipped', 0)}")
        logger.info(f"📊 Failed: {stats.get('failed', 0)}")
        logger.info("=" * 60)
        
        return {
            'skipped': False,
            'duration': duration,
            'stats': stats
        }
        
    except Exception as e:
        logger.error(f"❌ Image generation failed: {e}")
        import traceback
        traceback.print_exc()
        logger.info("=" * 60)
        
        # ✅ الـ Job يكمل حتى لو في error
        return {'skipped': False, 'error': str(e), 'partial': True}
    
    finally:
        if generator:
            try:
                generator.close()
            except:
                pass


# =============================================================================
# UTILITY: Reset failed reports
# =============================================================================

def reset_failed_reports(report_id: int = None):
    """
    ✅ إعادة تعيين التقارير الفاشلة للمحاولة من جديد
    
    Usage:
        reset_failed_reports()        # كل التقارير
        reset_failed_reports(123)     # تقرير محدد
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        if report_id:
            cursor.execute("DELETE FROM image_generation_failures WHERE report_id = %s", (report_id,))
            print(f"✅ Reset failure record for report #{report_id}")
        else:
            cursor.execute("DELETE FROM image_generation_failures")
            print(f"✅ Reset all failure records")
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error resetting: {e}")


if __name__ == "__main__":
    # ✅ دعم reset من command line
    if len(sys.argv) > 1:
        if sys.argv[1] == "--reset":
            if len(sys.argv) > 2 and sys.argv[2].isdigit():
                reset_failed_reports(int(sys.argv[2]))
            else:
                reset_failed_reports()
        elif sys.argv[1] == "--status":
            has_work, count = has_reports_without_images()
            skipped = get_failed_reports_count()
            print(f"📊 Reports needing images: {count}")
            print(f"⏭️  Permanently skipped: {skipped}")
        else:
            print("Usage:")
            print("  python image_generation_job.py           # Run job")
            print("  python image_generation_job.py --status  # Check status")
            print("  python image_generation_job.py --reset   # Reset all failures")
            print("  python image_generation_job.py --reset 123  # Reset specific report")
    else:
        generate_images()