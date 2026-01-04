#!/usr/bin/env python3
"""
🔄 Processing Pipeline Job - Sequential Execution

يشتغل كل 20 دقيقة ويعمل كل المراحل بالترتيب:
1. Clustering
2. Report Generation  
3. Social Media
4. Image Generation
5. Audio Generation

كل مرحلة تشتغل بس إذا اللي قبلها خلص
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
import psycopg2
from settings import DB_CONFIG
from app.config.user_config import user_config

# Logging setup
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'processing_pipeline.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# PIPELINE STATE CHECK
# =============================================================================

def is_pipeline_running() -> bool:
    """
    تحقق إذا في pipeline شغال حاليًا
    نستخدم جدول scheduled_task_logs للتحقق
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # تحقق إذا في processing_pipeline شغال من آخر 30 دقيقة ولسا ما خلص
        cursor.execute("""
            SELECT COUNT(*) FROM scheduled_task_logs stl
            JOIN scheduled_tasks st ON stl.scheduled_task_id = st.id
            WHERE st.task_type = 'processing_pipeline'
            AND stl.executed_at >= NOW() - INTERVAL '30 minutes'
            AND stl.status = 'running'
        """)
        
        running_count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return running_count > 0
        
    except Exception as e:
        logger.error(f"Error checking pipeline status: {e}")
        return False


def mark_pipeline_start() -> int:
    """
    سجل بداية الـ pipeline
    Returns: log_id للتحديث لاحقًا
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # احصل على task_id للـ processing_pipeline
        cursor.execute("""
            SELECT id FROM scheduled_tasks 
            WHERE task_type = 'processing_pipeline'
        """)
        
        task_row = cursor.fetchone()
        if not task_row:
            logger.error("processing_pipeline task not found in scheduled_tasks")
            return None
        
        task_id = task_row[0]
        
        # سجل بداية التنفيذ
        cursor.execute("""
            INSERT INTO scheduled_task_logs 
            (scheduled_task_id, status, executed_at)
            VALUES (%s, 'running', NOW())
            RETURNING id
        """, (task_id,))
        
        log_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return log_id
        
    except Exception as e:
        logger.error(f"Error marking pipeline start: {e}")
        return None


def mark_pipeline_end(log_id: int, status: str, duration: float, error: str = None):
    """
    سجل نهاية الـ pipeline
    """
    if not log_id:
        return
        
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE scheduled_task_logs 
            SET status = %s, 
                execution_time_seconds = %s,
                error_message = %s
            WHERE id = %s
        """, (status, duration, error, log_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error marking pipeline end: {e}")


# =============================================================================
# PIPELINE EXECUTION
# =============================================================================

def run_processing_pipeline() -> dict:
    """
    Main pipeline function - يشغل كل المراحل بالترتيب
    """
    start_time = datetime.now()
    
    logger.info("=" * 80)
    logger.info(f"🔄 Processing Pipeline started at {start_time}")
    logger.info("=" * 80)
    
    # تحقق إذا في pipeline شغال
    if is_pipeline_running():
        logger.info("⏭️ Pipeline already running, skipping this cycle")
        logger.info("=" * 80)
        return {'skipped': True, 'reason': 'already_running'}
    
    # سجل بداية الـ pipeline
    log_id = mark_pipeline_start()
    
    results = {
        'skipped': False,
        'stages': {},
        'total_duration': 0,
        'success': True
    }
    
    try:
        # المراحل بالترتيب
        stages = [
            ('clustering', 'Clustering'),
            ('reports', 'Report Generation'),
            ('social_media', 'Social Media'),
            ('images', 'Image Generation'),
            ('audio', 'Audio Generation')
        ]
        
        for stage_key, stage_name in stages:
            stage_start = datetime.now()
            logger.info(f"🔄 Starting: {stage_name}")
            
            try:
                stage_result = run_stage(stage_key)
                stage_duration = (datetime.now() - stage_start).total_seconds()
                
                results['stages'][stage_key] = {
                    'success': not stage_result.get('error'),
                    'duration': stage_duration,
                    'result': stage_result
                }
                
                if stage_result.get('error'):
                    logger.error(f"❌ {stage_name} failed: {stage_result['error']}")
                    results['success'] = False
                else:
                    logger.info(f"✅ {stage_name} completed in {stage_duration:.2f}s")
                
            except Exception as e:
                stage_duration = (datetime.now() - stage_start).total_seconds()
                logger.error(f"❌ {stage_name} crashed: {e}")
                
                results['stages'][stage_key] = {
                    'success': False,
                    'duration': stage_duration,
                    'error': str(e)
                }
                results['success'] = False
        
        # حساب المدة الإجمالية
        total_duration = (datetime.now() - start_time).total_seconds()
        results['total_duration'] = total_duration
        
        # تسجيل النتيجة النهائية
        final_status = 'completed' if results['success'] else 'failed'
        mark_pipeline_end(log_id, final_status, total_duration)
        
        logger.info("=" * 80)
        logger.info(f"🏁 Pipeline {final_status} in {total_duration:.2f}s")
        
        # ملخص النتائج
        for stage_key, stage_data in results['stages'].items():
            status = "✅" if stage_data['success'] else "❌"
            logger.info(f"   {status} {stage_key}: {stage_data['duration']:.2f}s")
        
        logger.info("=" * 80)
        
        return results
        
    except Exception as e:
        total_duration = (datetime.now() - start_time).total_seconds()
        error_msg = str(e)
        
        mark_pipeline_end(log_id, 'failed', total_duration, error_msg)
        
        logger.error(f"❌ Pipeline crashed: {e}")
        logger.info("=" * 80)
        
        return {
            'skipped': False,
            'success': False,
            'error': error_msg,
            'total_duration': total_duration
        }


def run_stage(stage: str) -> dict:
    """
    تشغيل مرحلة واحدة من الـ pipeline
    """
    try:
        if stage == 'clustering':
            from app.jobs.clustering_job import cluster_news
            return cluster_news()
            
        elif stage == 'reports':
            from app.jobs.reports_job import generate_reports
            return generate_reports()
            
        elif stage == 'social_media':
            from app.jobs.social_media_job import generate_social_media_content
            return generate_social_media_content()
            
        elif stage == 'images':
            from app.jobs.image_generation_job import generate_images
            return generate_images()
            
        elif stage == 'audio':
            from app.jobs.audio_generation_job import generate_audio
            return generate_audio()
            
        else:
            return {'error': f'Unknown stage: {stage}'}
            
    except Exception as e:
        return {'error': str(e)}


if __name__ == "__main__":
    run_processing_pipeline()