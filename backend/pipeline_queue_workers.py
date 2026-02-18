#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🚀 Pipeline Queue Workers - Real-Time Event-Driven Processing
═══════════════════════════════════════════════════════════════
Architecture: Hybrid

Queue-based (هذا الملف):
  clustering → report_generation → image_generation
  كل خبر جديد يمر بالمراحل فوراً بعد الـ scraping

Cron-based (worker.py):
  scraping + broadcast_generation
  يشتغل حسب جدول scheduled_tasks

═══════════════════════════════════════════════════════════════
Usage:
  # تشغيل كل الـ workers (الطريقة الموصى بها)
  python pipeline_queue_workers.py

  # تشغيل worker واحد فقط
  python pipeline_queue_workers.py --stage clustering
  python pipeline_queue_workers.py --stage report_generation
  python pipeline_queue_workers.py --stage image_generation

  # تشغيل كل الـ workers في نفس العملية (للتطوير)
  python pipeline_queue_workers.py --all-in-one
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import signal
import logging
import socket
import threading
import traceback
import argparse
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Callable

import psycopg2

# ─────────────────────────────────────────────────────────────
# Path Setup
# ─────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settings import DB_CONFIG

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────
WORKER_ID       = f"{socket.gethostname()}-{os.getpid()}"
POLL_INTERVAL   = int(os.getenv('QUEUE_POLL_INTERVAL', 2))   # ثانيتين
LOCK_TIMEOUT    = int(os.getenv('QUEUE_LOCK_TIMEOUT', 30))   # 30 دقيقة
MAX_ATTEMPTS    = int(os.getenv('QUEUE_MAX_ATTEMPTS', 3))

# Retry backoff بالدقائق
RETRY_BACKOFF = {1: 1, 2: 5, 3: 15}

# Pipeline order: كل stage تعرف اللي بعدها
NEXT_STAGE: Dict[str, Optional[str]] = {
    'clustering':       'report_generation',
    'report_generation':'image_generation',
    'image_generation': None,   # نهاية الـ pipeline
}

# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format=f'%(asctime)s - [%(name)s] - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(log_dir, f'pipeline_queue_{WORKER_ID}.log'),
            encoding='utf-8'
        ),
    ]
)


# ═══════════════════════════════════════════════════════════════
# Database Helpers
# ═══════════════════════════════════════════════════════════════

def get_conn():
    """إنشاء اتصال جديد بقاعدة البيانات"""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logging.getLogger('db').error(f"❌ DB connection failed: {e}")
        return None


def enqueue(news_id: int, stage: str, conn=None) -> bool:
    """
    إضافة خبر لمرحلة معينة في الـ queue.
    يستخدم ON CONFLICT DO NOTHING لتجنب التكرار.

    Args:
        news_id: ID الخبر
        stage:   المرحلة (clustering / report_generation / image_generation)
        conn:    اتصال موجود (اختياري)

    Returns:
        True إذا أُضيف، False إذا كان موجوداً أو فشل
    """
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    if not conn:
        return False

    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO news_pipeline_queue (news_id, stage, status, next_run_at)
            VALUES (%s, %s, 'pending', NOW())
            ON CONFLICT DO NOTHING
        """, (news_id, stage))
        inserted = cur.rowcount > 0
        if own_conn:
            conn.commit()
        cur.close()
        return inserted
    except Exception as e:
        logging.getLogger('queue').error(f"❌ enqueue failed (news={news_id}, stage={stage}): {e}")
        if own_conn and conn:
            conn.rollback()
        return False
    finally:
        if own_conn and conn:
            conn.close()


def enqueue_batch(news_ids: list, stage: str = 'clustering') -> int:
    """
    إضافة مجموعة أخبار للـ queue دفعة واحدة.

    Args:
        news_ids: قائمة IDs الأخبار
        stage:    المرحلة (افتراضي: clustering)

    Returns:
        عدد الأخبار المُضافة فعلاً
    """
    if not news_ids:
        return 0

    conn = get_conn()
    if not conn:
        return 0

    try:
        cur = conn.cursor()
        count = 0
        for nid in news_ids:
            cur.execute("""
                INSERT INTO news_pipeline_queue (news_id, stage, status, next_run_at)
                VALUES (%s, %s, 'pending', NOW())
                ON CONFLICT DO NOTHING
            """, (nid, stage))
            count += cur.rowcount
        conn.commit()
        cur.close()
        return count
    except Exception as e:
        logging.getLogger('queue').error(f"❌ enqueue_batch failed: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Queue Worker Class
# ═══════════════════════════════════════════════════════════════

class PipelineStageWorker:
    """
    Worker لمرحلة واحدة من الـ pipeline.

    يسحب مهام من news_pipeline_queue بـ FOR UPDATE SKIP LOCKED،
    ينفذها، ثم يعمل enqueue للمرحلة التالية تلقائياً.
    """

    def __init__(self, stage: str):
        self.stage   = stage
        self.logger  = logging.getLogger(f'worker.{stage}')
        self.running = True
        self._jobs_done = 0
        self._lock   = threading.Lock()

        # استيراد الـ job function
        self.job_func: Optional[Callable] = self._import_job()

    # ─────────────────────────────────────────────────────────
    # Job Import
    # ─────────────────────────────────────────────────────────

    def _import_job(self) -> Optional[Callable]:
        """استيراد الـ job function المناسبة للمرحلة"""
        try:
            if self.stage == 'clustering':
                from app.jobs.clustering_job import cluster_news
                return cluster_news

            elif self.stage == 'report_generation':
                from app.jobs.reports_job import generate_reports
                return generate_reports

            elif self.stage == 'image_generation':
                from app.jobs.image_generation_job import generate_images
                return generate_images

            else:
                self.logger.error(f"❌ Unknown stage: {self.stage}")
                return None

        except ImportError as e:
            self.logger.error(f"❌ Failed to import job for {self.stage}: {e}")
            return None

    # ─────────────────────────────────────────────────────────
    # Queue Operations
    # ─────────────────────────────────────────────────────────

    def _fetch_task(self) -> Optional[Dict]:
        """
        جلب مهمة مستحقة من الـ queue مع locking.
        يستخدم FOR UPDATE SKIP LOCKED لتجنب التعارض بين workers.
        """
        conn = get_conn()
        if not conn:
            return None

        try:
            cur = conn.cursor()

            cur.execute(f"""
                SELECT id, news_id, stage, attempt_count
                FROM news_pipeline_queue
                WHERE stage  = %s
                  AND status = 'pending'
                  AND next_run_at <= NOW()
                  AND (
                      locked_at IS NULL
                      OR locked_at < NOW() - INTERVAL '{LOCK_TIMEOUT} minutes'
                  )
                ORDER BY next_run_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """, (self.stage,))

            row = cur.fetchone()
            if not row:
                cur.close()
                conn.close()
                return None

            task_id, news_id, stage, attempt_count = row

            # قفل المهمة
            now = datetime.now(timezone.utc)
            cur.execute("""
                UPDATE news_pipeline_queue
                SET status     = 'running',
                    locked_at  = %s,
                    locked_by  = %s,
                    started_at = %s
                WHERE id = %s
            """, (now, WORKER_ID, now, task_id))

            conn.commit()
            cur.close()
            conn.close()

            return {
                'id':            task_id,
                'news_id':       news_id,
                'stage':         stage,
                'attempt_count': attempt_count,
                'locked_at':     now,
            }

        except Exception as e:
            self.logger.error(f"❌ Error fetching task: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return None

    def _mark_done(self, task: Dict, result: str = None):
        """تحديد المهمة كمنتهية وإضافة المرحلة التالية للـ queue"""
        conn = get_conn()
        if not conn:
            return

        try:
            cur = conn.cursor()
            now = datetime.now(timezone.utc)

            # تحديث المهمة الحالية
            cur.execute("""
                UPDATE news_pipeline_queue
                SET status      = 'done',
                    locked_at   = NULL,
                    locked_by   = NULL,
                    finished_at = %s,
                    result      = %s
                WHERE id = %s
            """, (now, result, task['id']))

            # إضافة المرحلة التالية
            next_stage = NEXT_STAGE.get(self.stage)
            if next_stage and task.get('news_id'):
                cur.execute("""
                    INSERT INTO news_pipeline_queue (news_id, stage, status, next_run_at)
                    VALUES (%s, %s, 'pending', NOW())
                    ON CONFLICT DO NOTHING
                """, (task['news_id'], next_stage))

                if cur.rowcount > 0:
                    self.logger.info(
                        f"➡️  Enqueued news #{task['news_id']} → {next_stage}"
                    )

            conn.commit()
            cur.close()

        except Exception as e:
            self.logger.error(f"❌ Error marking done: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def _mark_failed(self, task: Dict, error: str):
        """تحديد المهمة كفاشلة مع retry backoff"""
        conn = get_conn()
        if not conn:
            return

        try:
            cur = conn.cursor()
            now = datetime.now(timezone.utc)
            attempt = task['attempt_count'] + 1

            if attempt >= MAX_ATTEMPTS:
                # فشل نهائي
                cur.execute("""
                    UPDATE news_pipeline_queue
                    SET status        = 'failed',
                        locked_at     = NULL,
                        locked_by     = NULL,
                        finished_at   = %s,
                        attempt_count = %s,
                        error_message = %s
                    WHERE id = %s
                """, (now, attempt, error[:1000], task['id']))

                self.logger.error(
                    f"❌ Task #{task['id']} (news={task['news_id']}) "
                    f"permanently failed after {attempt} attempts"
                )

            else:
                # إعادة جدولة مع backoff
                backoff = RETRY_BACKOFF.get(attempt, 15)
                next_run = now + timedelta(minutes=backoff)

                cur.execute("""
                    UPDATE news_pipeline_queue
                    SET status        = 'pending',
                        locked_at     = NULL,
                        locked_by     = NULL,
                        next_run_at   = %s,
                        attempt_count = %s,
                        error_message = %s
                    WHERE id = %s
                """, (next_run, attempt, error[:1000], task['id']))

                self.logger.warning(
                    f"⚠️  Task #{task['id']} failed (attempt {attempt}/{MAX_ATTEMPTS}), "
                    f"retry in {backoff}min"
                )

            conn.commit()
            cur.close()

        except Exception as e:
            self.logger.error(f"❌ Error marking failed: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    # ─────────────────────────────────────────────────────────
    # Job Execution
    # ─────────────────────────────────────────────────────────

    def _execute(self, task: Dict) -> Dict:
        """
        تنفيذ الـ job المرتبط بالمرحلة.

        ملاحظة: الـ jobs الحالية (cluster_news, generate_reports, generate_images)
        تعمل على batch (كل الأخبار غير المعالجة)، مش على خبر واحد.
        هذا مقبول لأن الـ queue تضمن الترتيب والتسلسل.
        """
        started = datetime.now(timezone.utc)

        self.logger.info(
            f"▶️  [{self.stage}] Processing task #{task['id']} "
            f"(news={task['news_id']}, attempt={task['attempt_count']+1})"
        )

        try:
            result = self.job_func()
            finished = datetime.now(timezone.utc)
            duration = (finished - started).total_seconds()

            # تحليل النتيجة
            if isinstance(result, dict):
                if result.get('error'):
                    return {
                        'success': False,
                        'error':   result['error'],
                        'result':  None,
                        'duration': duration,
                    }
                elif result.get('skipped'):
                    return {
                        'success': True,
                        'error':   None,
                        'result':  f"skipped: {result.get('reason', '')}",
                        'duration': duration,
                    }
                else:
                    summary = str(result.get(
                        'processed',
                        result.get('generated', result.get('count', 'done'))
                    ))
                    return {
                        'success': True,
                        'error':   None,
                        'result':  summary,
                        'duration': duration,
                    }
            else:
                return {
                    'success': True,
                    'error':   None,
                    'result':  str(result) if result else 'done',
                    'duration': duration,
                }

        except Exception as e:
            finished = datetime.now(timezone.utc)
            duration = (finished - started).total_seconds()
            self.logger.error(f"❌ [{self.stage}] Job exception: {e}")
            traceback.print_exc()
            return {
                'success': False,
                'error':   str(e),
                'result':  None,
                'duration': duration,
            }

    # ─────────────────────────────────────────────────────────
    # Main Loop
    # ─────────────────────────────────────────────────────────

    def run(self):
        """Main worker loop - يشتغل حتى يُوقف"""
        self.logger.info(f"🚀 [{self.stage}] Worker started (id={WORKER_ID})")

        if not self.job_func:
            self.logger.error(f"❌ [{self.stage}] No job function, exiting")
            return

        last_heartbeat = datetime.now()

        while self.running:
            try:
                task = self._fetch_task()

                if not task:
                    # لا توجد مهام - heartbeat كل دقيقة
                    if (datetime.now() - last_heartbeat).total_seconds() >= 60:
                        self.logger.debug(
                            f"💓 [{self.stage}] alive - {self._jobs_done} done"
                        )
                        last_heartbeat = datetime.now()
                    time.sleep(POLL_INTERVAL)
                    continue

                # تنفيذ الـ job
                exec_result = self._execute(task)

                if exec_result['success']:
                    self._mark_done(task, result=exec_result['result'])
                    with self._lock:
                        self._jobs_done += 1
                    self.logger.info(
                        f"✅ [{self.stage}] Task #{task['id']} done "
                        f"in {exec_result['duration']:.1f}s"
                    )
                else:
                    self._mark_failed(task, error=exec_result['error'])
                    self.logger.error(
                        f"❌ [{self.stage}] Task #{task['id']} failed "
                        f"in {exec_result['duration']:.1f}s: {exec_result['error']}"
                    )

            except KeyboardInterrupt:
                self.logger.info(f"⚠️  [{self.stage}] Keyboard interrupt")
                break

            except Exception as e:
                self.logger.error(f"❌ [{self.stage}] Loop error: {e}")
                traceback.print_exc()
                time.sleep(POLL_INTERVAL)

        self.logger.info(
            f"🛑 [{self.stage}] Worker stopped - {self._jobs_done} jobs done"
        )

    def stop(self):
        """إيقاف الـ worker بشكل نظيف"""
        self.running = False


# ═══════════════════════════════════════════════════════════════
# Multi-Stage Runner (All-in-One)
# ═══════════════════════════════════════════════════════════════

class PipelineQueueRunner:
    """
    يشغل كل الـ workers في threads منفصلة داخل نفس العملية.
    مفيد للـ development أو إذا كان عندك resource محدود.

    للـ production: شغّل كل worker في process منفصل.
    """

    STAGES = ['clustering', 'report_generation', 'image_generation']

    def __init__(self):
        self.logger  = logging.getLogger('pipeline.runner')
        self.workers = {}
        self.threads = {}
        self.running = True

    def start(self):
        """تشغيل كل الـ workers"""
        self.logger.info("═" * 70)
        self.logger.info("🚀 Pipeline Queue Runner Starting")
        self.logger.info(f"   Stages: {' → '.join(self.STAGES)}")
        self.logger.info(f"   Poll interval: {POLL_INTERVAL}s")
        self.logger.info(f"   Max attempts: {MAX_ATTEMPTS}")
        self.logger.info(f"   Lock timeout: {LOCK_TIMEOUT}min")
        self.logger.info("═" * 70)

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT,  self._signal_handler)

        # إنشاء وتشغيل workers
        for stage in self.STAGES:
            worker = PipelineStageWorker(stage)
            thread = threading.Thread(
                target=worker.run,
                name=f"worker-{stage}",
                daemon=True
            )
            self.workers[stage] = worker
            self.threads[stage] = thread
            thread.start()
            self.logger.info(f"   ✅ Started {stage} worker")

        self.logger.info("═" * 70)

        # انتظر حتى يُوقف
        try:
            while self.running:
                time.sleep(1)
                # تحقق من أن الـ threads لا تزال تعمل
                for stage, thread in self.threads.items():
                    if not thread.is_alive():
                        self.logger.warning(f"⚠️  {stage} thread died, restarting...")
                        worker = PipelineStageWorker(stage)
                        new_thread = threading.Thread(
                            target=worker.run,
                            name=f"worker-{stage}",
                            daemon=True
                        )
                        self.workers[stage] = worker
                        self.threads[stage] = new_thread
                        new_thread.start()

        except KeyboardInterrupt:
            pass

        self.stop()

    def stop(self):
        """إيقاف كل الـ workers"""
        self.logger.info("⚠️  Stopping all pipeline workers...")
        self.running = False

        for stage, worker in self.workers.items():
            worker.stop()

        # انتظر الـ threads
        for stage, thread in self.threads.items():
            thread.join(timeout=10)
            self.logger.info(f"   🛑 {stage} worker stopped")

        self.logger.info("✅ All pipeline workers stopped")

    def _signal_handler(self, signum, frame):
        self.logger.info(f"\n⚠️  Signal {signum} received, shutting down...")
        self.running = False


# ═══════════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════════

def show_queue_stats():
    """عرض إحصائيات الـ queue"""
    conn = get_conn()
    if not conn:
        print("❌ Cannot connect to database")
        return

    try:
        cur = conn.cursor()

        print("\n" + "═" * 60)
        print("📊 Pipeline Queue Statistics")
        print("═" * 60)

        cur.execute("""
            SELECT stage, status, COUNT(*), MIN(created_at), MAX(created_at)
            FROM news_pipeline_queue
            GROUP BY stage, status
            ORDER BY stage, status
        """)

        rows = cur.fetchall()
        if not rows:
            print("  (empty queue)")
        else:
            current_stage = None
            for stage, status, count, oldest, newest in rows:
                if stage != current_stage:
                    print(f"\n  📌 {stage}:")
                    current_stage = stage
                print(f"     {status:10s}: {count:5d}  (oldest: {oldest}, newest: {newest})")

        print("\n" + "═" * 60)

        # آخر 10 مهام
        cur.execute("""
            SELECT id, news_id, stage, status, attempt_count,
                   created_at, finished_at, error_message
            FROM news_pipeline_queue
            ORDER BY created_at DESC
            LIMIT 10
        """)

        rows = cur.fetchall()
        print("📋 Last 10 Queue Items:")
        for row in rows:
            qid, nid, stage, status, attempts, created, finished, error = row
            duration = ""
            if finished and created:
                duration = f" ({(finished - created).total_seconds():.1f}s)"
            err = f" ⚠️ {error[:50]}" if error else ""
            print(f"  #{qid:6d} news={nid} [{stage}] {status} (x{attempts}){duration}{err}")

        print("═" * 60 + "\n")

        cur.close()
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()


def reset_stuck_tasks(stage: str = None, minutes: int = 60):
    """
    إعادة تعيين المهام العالقة (running لفترة طويلة)

    Args:
        stage:   مرحلة محددة أو None للكل
        minutes: عدد الدقائق للاعتبار المهمة عالقة
    """
    conn = get_conn()
    if not conn:
        return

    try:
        cur = conn.cursor()

        if stage:
            cur.execute("""
                UPDATE news_pipeline_queue
                SET status    = 'pending',
                    locked_at = NULL,
                    locked_by = NULL
                WHERE status = 'running'
                  AND stage  = %s
                  AND locked_at < NOW() - INTERVAL '%s minutes'
            """, (stage, minutes))
        else:
            cur.execute(f"""
                UPDATE news_pipeline_queue
                SET status    = 'pending',
                    locked_at = NULL,
                    locked_by = NULL
                WHERE status = 'running'
                  AND locked_at < NOW() - INTERVAL '{minutes} minutes'
            """)

        count = cur.rowcount
        conn.commit()
        cur.close()
        print(f"✅ Reset {count} stuck tasks")

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Pipeline Queue Workers - Real-Time Event-Driven Processing'
    )
    parser.add_argument(
        '--stage',
        choices=['clustering', 'report_generation', 'image_generation'],
        help='تشغيل worker لمرحلة واحدة فقط'
    )
    parser.add_argument(
        '--all-in-one',
        action='store_true',
        help='تشغيل كل الـ workers في نفس العملية (للتطوير)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='عرض إحصائيات الـ queue'
    )
    parser.add_argument(
        '--reset-stuck',
        action='store_true',
        help='إعادة تعيين المهام العالقة'
    )
    parser.add_argument(
        '--enqueue',
        type=int,
        metavar='NEWS_ID',
        help='إضافة خبر يدوياً للـ queue (للاختبار)'
    )

    args = parser.parse_args()

    if args.stats:
        show_queue_stats()
        return

    if args.reset_stuck:
        reset_stuck_tasks()
        return

    if args.enqueue:
        success = enqueue(args.enqueue, 'clustering')
        if success:
            print(f"✅ News #{args.enqueue} enqueued for clustering")
        else:
            print(f"⚠️  News #{args.enqueue} already in queue or failed")
        return

    if args.stage:
        # تشغيل worker واحد
        worker = PipelineStageWorker(args.stage)

        def _stop(signum, frame):
            print(f"\n⚠️  Signal {signum}, stopping...")
            worker.stop()

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT,  _stop)

        worker.run()

    else:
        # تشغيل كل الـ workers (all-in-one أو الافتراضي)
        runner = PipelineQueueRunner()
        runner.start()


if __name__ == '__main__':
    main()
