#!/usr/bin/env python3
"""
⏰ Job Timeout Manager
═══════════════════════════════════════════════════════════════
يضمن إن الـ jobs ما تعلق أكثر من وقت معين
يقتل الـ job إذا أخذ وقت أطول من المحدد

Features:
- Environment variable configuration
- Predefined timeouts for job types
- Signal-based timeout handling
- Graceful error handling

Usage:
    @timeout_job(300)  # 5 دقائق
    def my_job():
        # job code here
        pass
        
    @timeout_job_by_type('scraping')  # uses SCRAPING_TIMEOUT env var
    def scrape_news():
        # job code here
        pass
═══════════════════════════════════════════════════════════════
"""

import os
import signal
import functools
import logging
from typing import Callable, Any, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Exception raised when job times out"""
    pass


def timeout_handler(signum, frame):
    """Signal handler for timeout"""
    raise TimeoutError("Job timed out")


def timeout_job(timeout_seconds: int = 300):
    """
    Decorator لإضافة timeout للـ jobs
    
    Args:
        timeout_seconds: المدة القصوى بالثواني (default: 5 دقائق)
    
    Usage:
        @timeout_job(600)  # 10 دقائق
        def scrape_news():
            # job code
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Dict[str, Any]:
            job_name = func.__name__
            start_time = datetime.now()
            
            # Set up the timeout signal
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)
            
            try:
                logger.info(f"⏰ Starting {job_name} with {timeout_seconds}s timeout")
                result = func(*args, **kwargs)
                
                # Cancel the alarm
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
                
                duration = (datetime.now() - start_time).total_seconds()
                logger.info(f"✅ {job_name} completed in {duration:.1f}s")
                
                return result
                
            except TimeoutError:
                # Cancel the alarm
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
                
                duration = (datetime.now() - start_time).total_seconds()
                error_msg = f"Job {job_name} timed out after {timeout_seconds}s"
                logger.error(f"⏰❌ {error_msg}")
                
                return {
                    'error': error_msg,
                    'timeout': True,
                    'duration': duration
                }
                
            except Exception as e:
                # Cancel the alarm
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
                
                duration = (datetime.now() - start_time).total_seconds()
                logger.error(f"❌ {job_name} failed: {e}")
                
                return {
                    'error': str(e),
                    'timeout': False,
                    'duration': duration
                }
        
        return wrapper
    return decorator


# Predefined timeouts for different job types (with env var support)
def get_env_timeout(env_key: str, default: int) -> int:
    """Get timeout from environment variable or use default"""
    try:
        return int(os.getenv(env_key, default))
    except (ValueError, TypeError):
        logger.warning(f"Invalid {env_key} value, using default: {default}s")
        return default


JOB_TIMEOUTS = {
    'scraping': lambda: get_env_timeout('SCRAPING_TIMEOUT', 600),        # 10 دقائق
    'clustering': lambda: get_env_timeout('CLUSTERING_TIMEOUT', 180),    # 3 دقائق
    'reports': lambda: get_env_timeout('REPORTS_TIMEOUT', 300),          # 5 دقائق
    'social_media': lambda: get_env_timeout('SOCIAL_MEDIA_TIMEOUT', 240), # 4 دقائق
    'images': lambda: get_env_timeout('IMAGES_TIMEOUT', 900),            # 15 دقيقة
    'audio': lambda: get_env_timeout('AUDIO_TIMEOUT', 600),              # 10 دقائق
    'video': lambda: get_env_timeout('VIDEO_TIMEOUT', 1200),             # 20 دقيقة
    'publishing': lambda: get_env_timeout('PUBLISHING_TIMEOUT', 400),    # 5 دقائق
    'broadcast': lambda: get_env_timeout('BROADCAST_TIMEOUT', 1000),      # 10 دقائق
    'default': lambda: get_env_timeout('DEFAULT_JOB_TIMEOUT', 300),      # 5 دقائق
}


def get_job_timeout(job_type: str) -> int:
    """
    احصل على الـ timeout المناسب لنوع الـ job
    
    Args:
        job_type: نوع الـ job
    
    Returns:
        int: الـ timeout بالثواني
    """
    timeout_func = JOB_TIMEOUTS.get(job_type, JOB_TIMEOUTS['default'])
    timeout = timeout_func()
    
    logger.debug(f"Timeout for {job_type}: {timeout}s")
    return timeout


def timeout_job_by_type(job_type: str):
    """
    Decorator يستخدم الـ timeout المحدد مسبقاً لنوع الـ job
    
    Args:
        job_type: نوع الـ job من JOB_TIMEOUTS
    
    Usage:
        @timeout_job_by_type('scraping')
        def scrape_news():
            # job code
            pass
    """
    timeout_seconds = get_job_timeout(job_type)
    return timeout_job(timeout_seconds)


def is_timeout_enabled() -> bool:
    """Check if job timeouts are enabled via environment variable"""
    return os.getenv('ENABLE_JOB_TIMEOUTS', 'true').lower() in ('true', '1', 'yes')


def conditional_timeout_job_by_type(job_type: str):
    """
    Decorator يطبق timeout بس إذا كان مفعل في الـ environment
    
    Args:
        job_type: نوع الـ job
    
    Usage:
        @conditional_timeout_job_by_type('scraping')
        def scrape_news():
            # job code
            pass
    """
    if is_timeout_enabled():
        return timeout_job_by_type(job_type)
    else:
        # Return identity decorator (no timeout)
        def decorator(func):
            return func
        return decorator