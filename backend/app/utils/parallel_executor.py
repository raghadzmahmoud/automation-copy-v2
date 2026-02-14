#!/usr/bin/env python3
"""
🔄 Parallel Job Executor
═══════════════════════════════════════════════════════════════
يشغل الـ jobs بشكل parallel مع timeout وإدارة الأخطاء
يضمن إن job واحد ما يعطل الباقي

Features:
- Parallel execution مع threading
- Individual timeouts لكل job
- Error isolation (job واحد يفشل ما يأثر على الباقي)
- Progress monitoring
- Graceful shutdown
═══════════════════════════════════════════════════════════════
"""

import threading
import time
import logging
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class JobConfig:
    """Configuration for a single job"""
    name: str
    func: Callable
    timeout: int = 300  # 5 دقائق default
    retry_count: int = 0
    dependencies: List[str] = None  # jobs يجب تخلص قبل هذا
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class JobResult:
    """Result of job execution"""
    name: str
    success: bool
    duration: float
    result: Dict[str, Any]
    error: Optional[str] = None
    timeout: bool = False
    retries: int = 0


class ParallelJobExecutor:
    """
    Executor للـ jobs بشكل parallel مع dependency management
    """
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.jobs: Dict[str, JobConfig] = {}
        self.results: Dict[str, JobResult] = {}
        self.running_jobs: Dict[str, Future] = {}
        self.completed_jobs: set = set()
        self.failed_jobs: set = set()
        
    def add_job(self, job_config: JobConfig):
        """إضافة job للـ executor"""
        self.jobs[job_config.name] = job_config
        logger.info(f"📝 Added job: {job_config.name} (timeout: {job_config.timeout}s)")
    
    def can_run_job(self, job_name: str) -> bool:
        """تحقق إذا الـ job ممكن يشتغل (dependencies مكتملة)"""
        job = self.jobs[job_name]
        
        # تحقق إن كل الـ dependencies خلصت بنجاح
        for dep in job.dependencies:
            if dep not in self.completed_jobs:
                return False
        
        return True
    
    def run_single_job(self, job_config: JobConfig) -> JobResult:
        """تشغيل job واحد مع timeout"""
        start_time = datetime.now()
        job_name = job_config.name
        
        logger.info(f"▶️  Starting job: {job_name}")
        
        def target():
            try:
                return job_config.func()
            except Exception as e:
                return {'error': str(e)}
        
        # تشغيل الـ job في thread منفصل مع timeout
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(target)
        
        try:
            # انتظار النتيجة مع timeout
            result = future.result(timeout=job_config.timeout)
            duration = (datetime.now() - start_time).total_seconds()
            
            if result.get('error'):
                logger.error(f"❌ {job_name} failed: {result['error']}")
                return JobResult(
                    name=job_name,
                    success=False,
                    duration=duration,
                    result=result,
                    error=result['error']
                )
            else:
                logger.info(f"✅ {job_name} completed in {duration:.1f}s")
                return JobResult(
                    name=job_name,
                    success=True,
                    duration=duration,
                    result=result
                )
                
        except TimeoutError:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = f"Job timed out after {job_config.timeout}s"
            logger.error(f"⏰❌ {job_name}: {error_msg}")
            
            # محاولة إيقاف الـ job
            future.cancel()
            
            return JobResult(
                name=job_name,
                success=False,
                duration=duration,
                result={'error': error_msg},
                error=error_msg,
                timeout=True
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ {job_name} crashed: {e}")
            
            return JobResult(
                name=job_name,
                success=False,
                duration=duration,
                result={'error': str(e)},
                error=str(e)
            )
        
        finally:
            executor.shutdown(wait=False)
    
    def execute_all(self) -> Dict[str, JobResult]:
        """
        تشغيل كل الـ jobs مع مراعاة الـ dependencies
        """
        logger.info("=" * 60)
        logger.info(f"🚀 Starting parallel execution of {len(self.jobs)} jobs")
        logger.info(f"Max workers: {self.max_workers}")
        logger.info("=" * 60)
        
        start_time = datetime.now()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            
            while len(self.completed_jobs) + len(self.failed_jobs) < len(self.jobs):
                
                # ابحث عن jobs جاهزة للتشغيل
                ready_jobs = []
                for job_name, job_config in self.jobs.items():
                    if (job_name not in self.completed_jobs and 
                        job_name not in self.failed_jobs and 
                        job_name not in self.running_jobs and
                        self.can_run_job(job_name)):
                        ready_jobs.append(job_config)
                
                # شغل الـ jobs الجاهزة
                for job_config in ready_jobs:
                    if len(self.running_jobs) < self.max_workers:
                        future = executor.submit(self.run_single_job, job_config)
                        self.running_jobs[job_config.name] = future
                        logger.info(f"🔄 Submitted job: {job_config.name}")
                
                # تحقق من الـ jobs المكتملة
                completed_futures = []
                for job_name, future in self.running_jobs.items():
                    if future.done():
                        completed_futures.append(job_name)
                
                # معالجة النتائج
                for job_name in completed_futures:
                    future = self.running_jobs.pop(job_name)
                    result = future.result()
                    self.results[job_name] = result
                    
                    if result.success:
                        self.completed_jobs.add(job_name)
                    else:
                        self.failed_jobs.add(job_name)
                
                # انتظار قصير قبل التحقق مرة أخرى
                if not completed_futures and not ready_jobs:
                    time.sleep(1)
        
        total_duration = (datetime.now() - start_time).total_seconds()
        
        # ملخص النتائج
        logger.info("=" * 60)
        logger.info(f"🏁 Parallel execution completed in {total_duration:.1f}s")
        logger.info(f"✅ Successful: {len(self.completed_jobs)}")
        logger.info(f"❌ Failed: {len(self.failed_jobs)}")
        logger.info("=" * 60)
        
        for job_name, result in self.results.items():
            status = "✅" if result.success else "❌"
            timeout_info = " (TIMEOUT)" if result.timeout else ""
            logger.info(f"  {status} {job_name}: {result.duration:.1f}s{timeout_info}")
        
        logger.info("=" * 60)
        
        return self.results


# =============================================================================
# Helper Functions
# =============================================================================

def create_job_group(jobs: List[tuple], max_workers: int = 4) -> ParallelJobExecutor:
    """
    إنشاء مجموعة jobs للتشغيل المتوازي
    
    Args:
        jobs: قائمة من (name, func, timeout, dependencies)
        max_workers: عدد الـ workers المتوازية
    
    Returns:
        ParallelJobExecutor: executor جاهز للتشغيل
    """
    executor = ParallelJobExecutor(max_workers=max_workers)
    
    for job_info in jobs:
        if len(job_info) == 2:
            name, func = job_info
            timeout = 300
            dependencies = []
        elif len(job_info) == 3:
            name, func, timeout = job_info
            dependencies = []
        elif len(job_info) == 4:
            name, func, timeout, dependencies = job_info
        else:
            raise ValueError(f"Invalid job info: {job_info}")
        
        job_config = JobConfig(
            name=name,
            func=func,
            timeout=timeout,
            dependencies=dependencies
        )
        executor.add_job(job_config)
    
    return executor


def run_jobs_parallel(jobs: List[tuple], max_workers: int = 4) -> Dict[str, JobResult]:
    """
    تشغيل مجموعة jobs بشكل متوازي
    
    Args:
        jobs: قائمة من (name, func, timeout, dependencies)
        max_workers: عدد الـ workers المتوازية
    
    Returns:
        Dict[str, JobResult]: نتائج كل الـ jobs
    """
    executor = create_job_group(jobs, max_workers)
    return executor.execute_all()