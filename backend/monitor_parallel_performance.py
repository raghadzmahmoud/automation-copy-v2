#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📊 Parallel Performance Monitor
مراقب أداء التشغيل المتوازي للـ Production Scheduler
"""

import os
import sys
import time
import psycopg2
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settings import DB_CONFIG


def get_db_connection():
    """إنشاء اتصال بقاعدة البيانات"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None


def get_parallel_execution_stats(hours: int = 1):
    """
    إحصائيات التشغيل المتوازي
    """
    conn = get_db_connection()
    if not conn:
        return {}
    
    try:
        cursor = conn.cursor()
        
        # الحصول على logs من آخر ساعة
        since_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        cursor.execute("""
            SELECT 
                st.task_type,
                stl.started_at,
                stl.finished_at,
                stl.execution_time_seconds,
                stl.status,
                stl.locked_by
            FROM scheduled_task_logs stl
            JOIN scheduled_tasks st ON stl.scheduled_task_id = st.id
            WHERE stl.executed_at >= %s
            AND stl.started_at IS NOT NULL
            AND stl.finished_at IS NOT NULL
            ORDER BY stl.started_at
        """, (since_time,))
        
        logs = []
        for row in cursor.fetchall():
            task_type, started_at, finished_at, execution_time, status, locked_by = row
            
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            if finished_at.tzinfo is None:
                finished_at = finished_at.replace(tzinfo=timezone.utc)
            
            logs.append({
                'task_type': task_type,
                'started_at': started_at,
                'finished_at': finished_at,
                'execution_time': execution_time,
                'status': status,
                'worker_id': locked_by
            })
        
        cursor.close()
        conn.close()
        
        return analyze_parallel_execution(logs)
        
    except Exception as e:
        print(f"❌ Error getting parallel stats: {e}")
        if conn:
            conn.close()
        return {}


def analyze_parallel_execution(logs):
    """
    تحليل التشغيل المتوازي
    """
    if not logs:
        return {'error': 'No logs found'}
    
    # إحصائيات عامة
    total_jobs = len(logs)
    successful_jobs = sum(1 for log in logs if log['status'] == 'completed')
    failed_jobs = total_jobs - successful_jobs
    
    # إحصائيات حسب نوع المهمة
    task_stats = defaultdict(lambda: {'count': 0, 'success': 0, 'total_time': 0, 'workers': set()})
    
    for log in logs:
        task_type = log['task_type']
        task_stats[task_type]['count'] += 1
        if log['status'] == 'completed':
            task_stats[task_type]['success'] += 1
        task_stats[task_type]['total_time'] += log['execution_time'] or 0
        if log['worker_id']:
            task_stats[task_type]['workers'].add(log['worker_id'])
    
    # تحليل التشغيل المتوازي
    parallel_analysis = analyze_concurrent_execution(logs)
    
    # إحصائيات الـ workers
    worker_stats = Counter(log['worker_id'] for log in logs if log['worker_id'])
    
    return {
        'total_jobs': total_jobs,
        'successful_jobs': successful_jobs,
        'failed_jobs': failed_jobs,
        'success_rate': (successful_jobs / total_jobs * 100) if total_jobs > 0 else 0,
        'task_stats': dict(task_stats),
        'worker_stats': dict(worker_stats),
        'parallel_analysis': parallel_analysis,
        'time_range': {
            'start': min(log['started_at'] for log in logs),
            'end': max(log['finished_at'] for log in logs)
        }
    }


def analyze_concurrent_execution(logs):
    """
    تحليل التشغيل المتزامن
    """
    # إنشاء timeline للتشغيل
    events = []
    
    for log in logs:
        events.append({
            'time': log['started_at'],
            'type': 'start',
            'task_type': log['task_type'],
            'worker_id': log['worker_id']
        })
        events.append({
            'time': log['finished_at'],
            'type': 'end',
            'task_type': log['task_type'],
            'worker_id': log['worker_id']
        })
    
    # ترتيب الأحداث حسب الوقت
    events.sort(key=lambda x: x['time'])
    
    # تتبع التشغيل المتزامن
    concurrent_jobs = []
    max_concurrent = 0
    concurrent_by_task = defaultdict(int)
    max_concurrent_by_task = defaultdict(int)
    
    for event in events:
        if event['type'] == 'start':
            concurrent_jobs.append(event)
            concurrent_by_task[event['task_type']] += 1
        else:
            # إزالة المهمة المنتهية
            concurrent_jobs = [job for job in concurrent_jobs 
                             if not (job['task_type'] == event['task_type'] and 
                                   job['worker_id'] == event['worker_id'])]
            concurrent_by_task[event['task_type']] -= 1
        
        # تحديث الحد الأقصى
        current_concurrent = len(concurrent_jobs)
        max_concurrent = max(max_concurrent, current_concurrent)
        
        for task_type, count in concurrent_by_task.items():
            max_concurrent_by_task[task_type] = max(max_concurrent_by_task[task_type], count)
    
    return {
        'max_concurrent_jobs': max_concurrent,
        'max_concurrent_by_task': dict(max_concurrent_by_task),
        'parallel_efficiency': (max_concurrent / 5 * 100) if max_concurrent > 0 else 0  # 5 workers
    }


def print_performance_report(hours: int = 1):
    """
    طباعة تقرير الأداء المتوازي
    """
    print(f"📊 Parallel Performance Report (Last {hours} hour{'s' if hours > 1 else ''})")
    print("=" * 70)
    
    stats = get_parallel_execution_stats(hours)
    
    if 'error' in stats:
        print(f"❌ {stats['error']}")
        return
    
    if stats['total_jobs'] == 0:
        print("📭 No jobs executed in the specified time period")
        return
    
    # إحصائيات عامة
    print(f"📈 Overall Performance:")
    print(f"   Total Jobs: {stats['total_jobs']}")
    print(f"   Successful: {stats['successful_jobs']} ({stats['success_rate']:.1f}%)")
    print(f"   Failed: {stats['failed_jobs']}")
    
    # تحليل التشغيل المتوازي
    parallel = stats['parallel_analysis']
    print(f"\n🚀 Parallel Execution Analysis:")
    print(f"   Max Concurrent Jobs: {parallel['max_concurrent_jobs']}/5 workers")
    print(f"   Parallel Efficiency: {parallel['parallel_efficiency']:.1f}%")
    
    if parallel['max_concurrent_by_task']:
        print(f"   Max Concurrent by Task Type:")
        for task_type, max_concurrent in parallel['max_concurrent_by_task'].items():
            print(f"      • {task_type}: {max_concurrent} simultaneous")
    
    # إحصائيات الـ workers
    print(f"\n⚙️ Worker Distribution:")
    total_worker_jobs = sum(stats['worker_stats'].values())
    for worker_id, job_count in sorted(stats['worker_stats'].items()):
        percentage = (job_count / total_worker_jobs * 100) if total_worker_jobs > 0 else 0
        print(f"   {worker_id}: {job_count} jobs ({percentage:.1f}%)")
    
    # إحصائيات حسب نوع المهمة
    print(f"\n📋 Task Type Performance:")
    for task_type, task_data in sorted(stats['task_stats'].items()):
        count = task_data['count']
        success = task_data['success']
        success_rate = (success / count * 100) if count > 0 else 0
        avg_time = (task_data['total_time'] / count) if count > 0 else 0
        worker_count = len(task_data['workers'])
        
        print(f"   {task_type}:")
        print(f"      Jobs: {count} ({success_rate:.1f}% success)")
        print(f"      Avg Time: {avg_time:.1f}s")
        print(f"      Workers Used: {worker_count}")
    
    # توصيات للتحسين
    print(f"\n💡 Performance Insights:")
    
    if parallel['max_concurrent_jobs'] < 3:
        print(f"   ⚠️  Low parallelism detected ({parallel['max_concurrent_jobs']}/5 workers)")
        print(f"      Consider increasing max_concurrent_runs for more task types")
    elif parallel['max_concurrent_jobs'] >= 4:
        print(f"   🔥 Excellent parallelism! ({parallel['max_concurrent_jobs']}/5 workers)")
        print(f"      System is efficiently utilizing available workers")
    
    # تحقق من توزيع العمل
    worker_jobs = list(stats['worker_stats'].values())
    if worker_jobs:
        min_jobs = min(worker_jobs)
        max_jobs = max(worker_jobs)
        if max_jobs > min_jobs * 2:
            print(f"   ⚠️  Uneven worker distribution detected")
            print(f"      Some workers are handling significantly more jobs")
    
    # الوقت المغطى
    time_range = stats['time_range']
    duration = (time_range['end'] - time_range['start']).total_seconds() / 60
    print(f"\n⏱️ Time Period: {duration:.1f} minutes")
    print(f"   From: {time_range['start'].strftime('%H:%M:%S')}")
    print(f"   To: {time_range['end'].strftime('%H:%M:%S')}")


def monitor_live_performance(duration: int = 60):
    """
    مراقبة الأداء المباشر
    """
    print(f"🔴 Live Performance Monitor (Running for {duration} seconds)")
    print("=" * 60)
    print("Press Ctrl+C to stop early")
    
    start_time = time.time()
    
    try:
        while time.time() - start_time < duration:
            # عرض الحالة الحالية
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                
                # المهام قيد التشغيل
                cursor.execute("""
                    SELECT task_type, locked_by, 
                           EXTRACT(EPOCH FROM (NOW() - locked_at))/60 as running_minutes
                    FROM scheduled_tasks
                    WHERE locked_at IS NOT NULL
                    ORDER BY locked_at
                """)
                
                running_tasks = cursor.fetchall()
                
                print(f"\r🔄 Currently Running ({len(running_tasks)}/5): ", end="")
                
                if running_tasks:
                    task_summary = []
                    for task_type, worker_id, running_minutes in running_tasks:
                        worker_short = worker_id.split('-')[-1] if worker_id else '?'
                        task_summary.append(f"{task_type[:10]}({worker_short})")
                    print(" | ".join(task_summary), end="")
                else:
                    print("No active jobs", end="")
                
                cursor.close()
                conn.close()
            
            time.sleep(2)
        
        print(f"\n\n✅ Live monitoring completed")
        
    except KeyboardInterrupt:
        print(f"\n\n⏹️ Live monitoring stopped by user")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor parallel performance of Production Scheduler')
    parser.add_argument('--hours', type=int, default=1, help='Hours of history to analyze')
    parser.add_argument('--live', type=int, help='Run live monitor for N seconds')
    
    args = parser.parse_args()
    
    if args.live:
        monitor_live_performance(args.live)
    else:
        print_performance_report(args.hours)