#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🩺 Scheduler Health Monitor
مراقب صحة نظام الـ Scheduler والـ Workers
"""

import os
import sys
import psycopg2
from datetime import datetime, timezone, timedelta
from typing import Dict, List

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


def get_scheduler_health() -> Dict:
    """
    فحص صحة الـ Scheduler
    """
    conn = get_db_connection()
    if not conn:
        return {'status': 'error', 'message': 'Database connection failed'}
    
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc)
        
        # إحصائيات المهام
        cursor.execute("""
            SELECT 
                COUNT(*) as total_tasks,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_tasks,
                COUNT(CASE WHEN status = 'paused' THEN 1 END) as paused_tasks,
                COUNT(CASE WHEN locked_at IS NOT NULL THEN 1 END) as locked_tasks,
                COUNT(CASE WHEN next_run_at <= %s AND status = 'active' AND locked_at IS NULL THEN 1 END) as due_tasks,
                COUNT(CASE WHEN fail_count > 0 THEN 1 END) as failed_tasks
            FROM scheduled_tasks
        """, (now,))
        
        stats = cursor.fetchone()
        
        # المهام المقفلة لفترة طويلة
        cursor.execute("""
            SELECT task_type, locked_by, locked_at, 
                   EXTRACT(EPOCH FROM (%s - locked_at))/60 as locked_minutes
            FROM scheduled_tasks
            WHERE locked_at IS NOT NULL
            AND locked_at < %s - INTERVAL '30 minutes'
        """, (now, now))
        
        stuck_tasks = []
        for row in cursor.fetchall():
            stuck_tasks.append({
                'task_type': row[0],
                'locked_by': row[1],
                'locked_at': row[2],
                'locked_minutes': round(row[3], 1)
            })
        
        # آخر تشغيل للمهام
        cursor.execute("""
            SELECT task_type, last_run_at, next_run_at, last_status, fail_count
            FROM scheduled_tasks
            WHERE status = 'active'
            ORDER BY 
                CASE WHEN next_run_at IS NULL THEN 1 ELSE 0 END,
                next_run_at ASC
        """)
        
        tasks_status = []
        for row in cursor.fetchall():
            task_type, last_run_at, next_run_at, last_status, fail_count = row
            
            # حساب متى آخر تشغيل
            if last_run_at:
                if last_run_at.tzinfo is None:
                    last_run_at = last_run_at.replace(tzinfo=timezone.utc)
                last_run_minutes = (now - last_run_at).total_seconds() / 60
            else:
                last_run_minutes = None
            
            # حساب متى التشغيل التالي
            if next_run_at:
                if next_run_at.tzinfo is None:
                    next_run_at = next_run_at.replace(tzinfo=timezone.utc)
                next_run_minutes = (next_run_at - now).total_seconds() / 60
            else:
                next_run_minutes = None
            
            tasks_status.append({
                'task_type': task_type,
                'last_run_minutes_ago': round(last_run_minutes, 1) if last_run_minutes else None,
                'next_run_in_minutes': round(next_run_minutes, 1) if next_run_minutes else None,
                'last_status': last_status,
                'fail_count': fail_count or 0,
                'is_overdue': next_run_minutes is not None and next_run_minutes < 0
            })
        
        cursor.close()
        conn.close()
        
        return {
            'status': 'healthy',
            'timestamp': now.isoformat(),
            'stats': {
                'total_tasks': stats[0],
                'active_tasks': stats[1],
                'paused_tasks': stats[2],
                'locked_tasks': stats[3],
                'due_tasks': stats[4],
                'failed_tasks': stats[5]
            },
            'stuck_tasks': stuck_tasks,
            'tasks_status': tasks_status
        }
        
    except Exception as e:
        if conn:
            conn.close()
        return {'status': 'error', 'message': str(e)}


def get_recent_logs(limit: int = 20) -> List[Dict]:
    """
    جلب آخر logs
    """
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                stl.id,
                st.task_type,
                stl.status,
                stl.execution_time_seconds,
                stl.result,
                stl.error_message,
                stl.executed_at,
                stl.locked_by
            FROM scheduled_task_logs stl
            JOIN scheduled_tasks st ON stl.scheduled_task_id = st.id
            ORDER BY stl.executed_at DESC
            LIMIT %s
        """, (limit,))
        
        logs = []
        for row in cursor.fetchall():
            logs.append({
                'id': row[0],
                'task_type': row[1],
                'status': row[2],
                'execution_time': row[3],
                'result': row[4],
                'error_message': row[5],
                'executed_at': row[6].isoformat() if row[6] else None,
                'worker_id': row[7]
            })
        
        cursor.close()
        conn.close()
        return logs
        
    except Exception as e:
        if conn:
            conn.close()
        return []


def print_health_report():
    """
    طباعة تقرير صحة النظام
    """
    print("🩺 Scheduler Health Report")
    print("=" * 50)
    
    health = get_scheduler_health()
    
    if health['status'] == 'error':
        print(f"❌ Error: {health['message']}")
        return
    
    stats = health['stats']
    print(f"📊 Task Statistics:")
    print(f"   Total Tasks: {stats['total_tasks']}")
    print(f"   Active: {stats['active_tasks']}")
    print(f"   Paused: {stats['paused_tasks']}")
    print(f"   Currently Running: {stats['locked_tasks']}")
    print(f"   Due Now: {stats['due_tasks']}")
    print(f"   With Failures: {stats['failed_tasks']}")
    
    # المهام المعلقة
    if health['stuck_tasks']:
        print(f"\n⚠️  Stuck Tasks ({len(health['stuck_tasks'])}):")
        for task in health['stuck_tasks']:
            print(f"   {task['task_type']}: locked by {task['locked_by']} for {task['locked_minutes']}min")
    
    # حالة المهام
    print(f"\n📅 Tasks Status:")
    for task in health['tasks_status'][:10]:  # أول 10 مهام
        task_type = task['task_type']
        last_run = f"{task['last_run_minutes_ago']}min ago" if task['last_run_minutes_ago'] else "never"
        next_run = f"in {task['next_run_in_minutes']}min" if task['next_run_in_minutes'] else "not scheduled"
        status = task['last_status'] or 'unknown'
        fails = task['fail_count']
        
        status_icon = "🔴" if task['is_overdue'] else "🟢" if task['next_run_in_minutes'] and task['next_run_in_minutes'] > 0 else "🟡"
        fail_str = f" ({fails} fails)" if fails > 0 else ""
        
        print(f"   {status_icon} {task_type}: last {last_run}, next {next_run} [{status}]{fail_str}")
    
    # آخر logs
    print(f"\n📝 Recent Logs:")
    logs = get_recent_logs(10)
    for log in logs:
        status_icon = "✅" if log['status'] == 'completed' else "❌"
        execution_time = f"{log['execution_time']:.1f}s" if log['execution_time'] else "0s"
        worker = log['worker_id'] or 'unknown'
        
        print(f"   {status_icon} {log['task_type']}: {execution_time} by {worker}")
        if log['error_message']:
            print(f"      Error: {log['error_message'][:100]}...")


def cleanup_old_logs(days: int = 30):
    """
    تنظيف الـ logs القديمة
    """
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        cursor.execute("""
            DELETE FROM scheduled_task_logs
            WHERE executed_at < %s
        """, (cutoff_date,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"🧹 Cleaned {deleted_count} logs older than {days} days")
        return True
        
    except Exception as e:
        print(f"❌ Error cleaning logs: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "cleanup":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            cleanup_old_logs(days)
        elif sys.argv[1] == "json":
            import json
            health = get_scheduler_health()
            print(json.dumps(health, indent=2, default=str))
        else:
            print("Usage: python scheduler_health.py [cleanup|json]")
    else:
        print_health_report()