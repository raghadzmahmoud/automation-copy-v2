#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📻 Broadcast Job
═══════════════════════════════════════════════════════════════
Job موحد للنشرات والموجزات
يقرأ الإعدادات من broadcast_configs ويولد حسب الوقت

يستخدم مع start_worker.py
═══════════════════════════════════════════════════════════════
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import psycopg2
from croniter import croniter

from settings import DB_CONFIG

# Logging setup
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'broadcast_job.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# BROADCAST GENERATION
# =============================================================================

def update_next_run_at(task_type: str, cron_pattern: str) -> bool:
    """
    تحديث next_run_at بعد التوليد الناجح
    
    Args:
        task_type: نوع المهمة (broadcast_generation, bulletin_generation, digest_generation)
        cron_pattern: نمط الـ cron من broadcast_configs
    
    Returns:
        bool: نجاح أم لا
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # حساب next_run_at حسب cron pattern
        now = datetime.now()
        cron = croniter(cron_pattern, now)
        next_run = cron.get_next(datetime)
        
        # تحديث المهمة
        cursor.execute("""
            UPDATE scheduled_tasks
            SET next_run_at = %s,
                last_status = 'ready'
            WHERE task_type = %s
        """, (next_run, task_type))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"📅 Updated {task_type}: next_run_at = {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error updating next_run_at for {task_type}: {e}")
        return False


def generate_broadcast(config_code: str = None) -> Dict:
    """
    توليد بث واحد أو كل البثات المستحقة
    
    Args:
        config_code: كود محدد ('digest', 'bulletin') أو None للكل
    
    Returns:
        dict مع النتائج
    """
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info(f"📻 Broadcast Job started at {start_time}")
    
    generator = None
    try:
        from app.services.generators.broadcast_generator import BroadcastGenerator
        
        generator = BroadcastGenerator()
        
        if config_code:
            # توليد نوع محدد
            logger.info(f"🎯 Generating specific: {config_code}")
            result = generator.generate(config_code)
            
            results = {config_code: result}
            
            if result.success and not result.skipped:
                # توليد الصوت
                _generate_audio_for_broadcast(result)
        else:
            # توليد كل المستحق
            logger.info("🔄 Checking all due broadcasts...")
            results = generator.generate_all_due()
            
            # توليد الصوت لكل بث جديد
            for code, result in results.items():
                if result.success and not result.skipped:
                    _generate_audio_for_broadcast(result)
        
        # تحديث next_run_at بعد التوليد الناجح
        if results and any(r.success and not r.skipped for r in results.values()):
            cron_pattern = _get_cron_pattern(generator)
            if cron_pattern:
                update_next_run_at('broadcast_generation', cron_pattern)
                update_next_run_at('bulletin_generation', cron_pattern)
                update_next_run_at('digest_generation', cron_pattern)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # إحصائيات
        generated = sum(1 for r in results.values() if r.success and not r.skipped)
        skipped = sum(1 for r in results.values() if r.skipped)
        failed = sum(1 for r in results.values() if not r.success)
        
        logger.info(f"✅ Broadcast Job completed in {duration:.2f}s")
        logger.info(f"📊 Generated: {generated}, Skipped: {skipped}, Failed: {failed}")
        logger.info("=" * 60)
        
        return {
            'success': True,
            'duration': duration,
            'generated': generated,
            'skipped': skipped,
            'failed': failed,
            'results': {k: {
                'success': v.success,
                'broadcast_id': v.broadcast_id,
                'skipped': v.skipped,
                'message': v.message
            } for k, v in results.items()}
        }
        
    except Exception as e:
        logger.error(f"❌ Broadcast Job failed: {e}")
        import traceback
        traceback.print_exc()
        logger.info("=" * 60)
        return {
            'success': False,
            'error': str(e)
        }
    
    finally:
        if generator:
            try:
                generator.close()
            except:
                pass


def _get_cron_pattern(generator: 'BroadcastGenerator') -> Optional[str]:
    """
    جلب cron pattern من broadcast_configs
    
    Args:
        generator: BroadcastGenerator instance
    
    Returns:
        str: cron pattern أو None
    """
    try:
        generator.cursor.execute("""
            SELECT schedule_pattern FROM scheduled_tasks 
            WHERE task_type = 'broadcast_generation' 
            AND status = 'active'
            LIMIT 1
        """)
        row = generator.cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.warning(f"⚠️ Error getting cron pattern: {e}")
        return None


def _generate_audio_for_broadcast(result) -> bool:
    """
    توليد صوت للبث الجديد
    
    Args:
        result: BroadcastResult object
    
    Returns:
        bool: نجاح أم لا
    """
    if not result.broadcast_id:
        return False
    
    try:
        from app.services.generators.bulletin_audio_generator import BulletinAudioGenerator
        
        logger.info(f"🎙️ Generating audio for {result.config_code} #{result.broadcast_id}...")
        
        gen = BulletinAudioGenerator()
        try:
            if result.config_code == 'digest':
                audio_result = gen.generate_for_digest(result.broadcast_id, force_update=False)
            else:
                audio_result = gen.generate_for_bulletin(result.broadcast_id, force_update=False)
            
            if audio_result.success:
                logger.info(f"✅ Audio generated: {audio_result.audio_url}")
                return True
            else:
                logger.warning(f"⚠️ Audio generation failed: {audio_result.error_message}")
                return False
                
        finally:
            gen.close()
            
    except ImportError:
        logger.warning("⚠️ BulletinAudioGenerator not available, skipping audio")
        return False
    except Exception as e:
        logger.error(f"❌ Audio generation error: {e}")
        return False


# =============================================================================
# SPECIFIC GENERATORS (للتوافق مع start_worker.py القديم)
# =============================================================================

def generate_bulletin_job() -> Dict:
    """توليد النشرة فقط - للتوافق مع الكود القديم"""
    logger.info("📻 generate_bulletin_job() called")
    return generate_broadcast('bulletin')


def generate_digest_job() -> Dict:
    """توليد الموجز فقط - للتوافق مع الكود القديم"""
    logger.info("📰 generate_digest_job() called")
    return generate_broadcast('digest')


def generate_all_broadcasts() -> Dict:
    """توليد كل البثات المستحقة"""
    logger.info("🔄 generate_all_broadcasts() called")
    return generate_broadcast(None)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        config_code = sys.argv[1]
        if config_code == 'all':
            generate_broadcast(None)
        else:
            generate_broadcast(config_code)
    else:
        # توليد كل المستحق
        generate_broadcast(None)