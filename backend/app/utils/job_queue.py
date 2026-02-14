#!/usr/bin/env python3
"""
📋 Job Queue System with Redis/Database Backend
═══════════════════════════════════════════════════════════════
نظام queue متقدم للـ jobs مع:
- Priority queues
- Retry mechanism
- Dead letter queue
- Job monitoring
- Distributed workers

هذا للمستقبل - يحتاج Redis أو database setup
═══════════════════════════════════════════════════════════════
"""

import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
import psycopg2
from settings import DB_CONFIG

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RETRY = "retry"
    DEAD = "dead"


class JobPriority(Enum):
    """Job priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class QueuedJob:
    """Job في الـ queue"""
    id: str
    name: str
    func_name: str
    args: Dict[str, Any]
    priority: JobPriority
    max_retries: int = 3
    timeout: int = 300
    created_at: datetime = None
    scheduled_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: JobStatus = JobStatus.PENDING
    retry_count: int = 0
    error_message: Optional[str] = None
    worker_id: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.scheduled_at is None:
            self.scheduled_at = datetime.now()


class JobQueue:
    """
    Job Queue Manager مع database backend
    """
    
    def __init__(self):
        self.setup_database()
    
    def setup_database(self):
        """إنشاء جداول الـ queue إذا لم تكن موجودة"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            # جدول الـ jobs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_queue (
                    id VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    func_name VARCHAR(255) NOT NULL,
                    args JSONB,
                    priority INTEGER DEFAULT 2,
                    max_retries INTEGER DEFAULT 3,
                    timeout_seconds INTEGER DEFAULT 300,
                    created_at TIMESTAMP DEFAULT NOW(),
                    scheduled_at TIMESTAMP DEFAULT NOW(),
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    status VARCHAR(50) DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    worker_id VARCHAR(255)
                )
            """)
            
            # إنشاء indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_job_queue_status_priority 
                ON job_queue (status, priority, scheduled_at)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_job_queue_worker 
                ON job_queue (worker_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_job_queue_created 
                ON job_queue (created_at)
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info("✅ Job queue database setup completed")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup job queue database: {e}")
            raise
    
    def enqueue(self, job: QueuedJob) -> bool:
        """إضافة job للـ queue"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO job_queue 
                (id, name, func_name, args, priority, max_retries, timeout_seconds,
                 created_at, scheduled_at, status, retry_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                job.id, job.name, job.func_name, json.dumps(job.args),
                job.priority.value, job.max_retries, job.timeout,
                job.created_at, job.scheduled_at, job.status.value, job.retry_count
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"📋 Enqueued job: {job.name} (ID: {job.id})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to enqueue job {job.name}: {e}")
            return False
    
    def dequeue(self, worker_id: str) -> Optional[QueuedJob]:
        """استخراج job من الـ queue للتشغيل"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            # البحث عن أعلى priority job جاهز للتشغيل
            cursor.execute("""
                UPDATE job_queue 
                SET status = 'running', 
                    started_at = NOW(), 
                    worker_id = %s
                WHERE id = (
                    SELECT id FROM job_queue 
                    WHERE status = 'pending' 
                    AND scheduled_at <= NOW()
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING *
            """, (worker_id,))
            
            row = cursor.fetchone()
            if not row:
                cursor.close()
                conn.close()
                return None
            
            # تحويل النتيجة لـ QueuedJob
            job = self._row_to_job(row)
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"📤 Dequeued job: {job.name} (ID: {job.id}) for worker {worker_id}")
            return job
            
        except Exception as e:
            logger.error(f"❌ Failed to dequeue job: {e}")
            return None
    
    def complete_job(self, job_id: str, success: bool, error_message: str = None):
        """تسجيل اكتمال الـ job"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            status = JobStatus.COMPLETED if success else JobStatus.FAILED
            
            cursor.execute("""
                UPDATE job_queue 
                SET status = %s, 
                    completed_at = NOW(),
                    error_message = %s
                WHERE id = %s
            """, (status.value, error_message, job_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"✅ Job {job_id} marked as {status.value}")
            
        except Exception as e:
            logger.error(f"❌ Failed to complete job {job_id}: {e}")
    
    def retry_job(self, job_id: str, error_message: str = None):
        """إعادة جدولة job للـ retry"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            # احصل على معلومات الـ job الحالية
            cursor.execute("""
                SELECT retry_count, max_retries FROM job_queue 
                WHERE id = %s
            """, (job_id,))
            
            row = cursor.fetchone()
            if not row:
                logger.error(f"Job {job_id} not found for retry")
                return False
            
            retry_count, max_retries = row
            
            if retry_count >= max_retries:
                # نقل للـ dead letter queue
                cursor.execute("""
                    UPDATE job_queue 
                    SET status = 'dead',
                        error_message = %s,
                        completed_at = NOW()
                    WHERE id = %s
                """, (f"Max retries exceeded: {error_message}", job_id))
                
                logger.warning(f"💀 Job {job_id} moved to dead letter queue")
            else:
                # جدولة للـ retry
                retry_delay = min(60 * (2 ** retry_count), 3600)  # exponential backoff
                scheduled_at = datetime.now() + timedelta(seconds=retry_delay)
                
                cursor.execute("""
                    UPDATE job_queue 
                    SET status = 'pending',
                        retry_count = retry_count + 1,
                        scheduled_at = %s,
                        error_message = %s,
                        worker_id = NULL,
                        started_at = NULL
                    WHERE id = %s
                """, (scheduled_at, error_message, job_id))
                
                logger.info(f"🔄 Job {job_id} scheduled for retry #{retry_count + 1} in {retry_delay}s")
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to retry job {job_id}: {e}")
            return False
    
    def get_queue_stats(self) -> Dict[str, int]:
        """احصائيات الـ queue"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT status, COUNT(*) 
                FROM job_queue 
                GROUP BY status
            """)
            
            stats = dict(cursor.fetchall())
            cursor.close()
            conn.close()
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Failed to get queue stats: {e}")
            return {}
    
    def cleanup_old_jobs(self, days: int = 7):
        """تنظيف الـ jobs القديمة"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM job_queue 
                WHERE completed_at < NOW() - INTERVAL '%s days'
                AND status IN ('completed', 'failed', 'dead')
            """, (days,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"🧹 Cleaned up {deleted_count} old jobs")
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ Failed to cleanup old jobs: {e}")
            return 0
    
    def _row_to_job(self, row) -> QueuedJob:
        """تحويل database row لـ QueuedJob"""
        return QueuedJob(
            id=row[0],
            name=row[1],
            func_name=row[2],
            args=json.loads(row[3]) if row[3] else {},
            priority=JobPriority(row[4]),
            max_retries=row[5],
            timeout=row[6],
            created_at=row[7],
            scheduled_at=row[8],
            started_at=row[9],
            completed_at=row[10],
            status=JobStatus(row[11]),
            retry_count=row[12],
            error_message=row[13],
            worker_id=row[14]
        )


# =============================================================================
# Helper Functions
# =============================================================================

def enqueue_job(name: str, func_name: str, args: Dict = None, 
                priority: JobPriority = JobPriority.NORMAL,
                timeout: int = 300, max_retries: int = 3,
                delay_seconds: int = 0) -> str:
    """
    إضافة job للـ queue
    
    Returns:
        str: job ID
    """
    import uuid
    
    job_id = str(uuid.uuid4())
    scheduled_at = datetime.now() + timedelta(seconds=delay_seconds)
    
    job = QueuedJob(
        id=job_id,
        name=name,
        func_name=func_name,
        args=args or {},
        priority=priority,
        timeout=timeout,
        max_retries=max_retries,
        scheduled_at=scheduled_at
    )
    
    queue = JobQueue()
    success = queue.enqueue(job)
    
    return job_id if success else None


def get_queue_status() -> Dict[str, Any]:
    """احصل على حالة الـ queue"""
    queue = JobQueue()
    stats = queue.get_queue_stats()
    
    return {
        'stats': stats,
        'total_jobs': sum(stats.values()),
        'active_jobs': stats.get('running', 0),
        'pending_jobs': stats.get('pending', 0),
        'failed_jobs': stats.get('failed', 0) + stats.get('dead', 0)
    }