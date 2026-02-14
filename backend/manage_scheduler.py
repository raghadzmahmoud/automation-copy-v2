#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎛️ Scheduler Management Tool
أداة إدارة نظام الـ Production Scheduler
"""

import os
import sys
import argparse
import psycopg2
from datetime import datetime, timezone, timedelta

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


def list_tasks():
    """عرض كل المهام"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, task_type, schedule_pattern, status, 
                   last_run_at, next_run_at, last_status, fail_count,
                   locked_at, locked_by, max_concurrent_runs
            FROM scheduled_tasks
            ORDER BY id
        """)
        
        print("📋 Scheduled Tasks:")
        print("-" * 140)
        print(f"{'ID':<3} {'Name':<25} {'Type':<20} {'Status':<8} {'Last Run':<12} {'Next Run':<12} {'Fails':<5} {'MaxConc':<7} {'Locked By':<15}")
        print("-" * 140)
        
        for row in cursor.fetchall():
            task_id, name, task_type, schedule_pattern, status, last_run_at, next_run_at, last_status, fail_count, locked_at, locked_by, max_concurrent = row
            
            last_run_str = last_run_at.strftime('%H:%M:%S') if last_run_at else 'Never'
            next_run_str = next_run_at.strftime('%H:%M:%S') if next_run_at else 'Not set'
            fail_count = fail_count or 0
            locked_by = locked_by or ''
            max_concurrent = max_concurrent or 1
            
            print(f"{task_id:<3} {name[:24]:<25} {task_type[:19]:<20} {status:<8} {last_run_str:<12} {next_run_str:<12} {fail_count:<5} {max_concurrent:<7} {locked_by[:14]:<15}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error listing tasks: {e}")
        if conn:
            conn.close()


def pause_task(task_type: str):
    """إيقاف مهمة"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE scheduled_tasks
            SET status = 'paused'
            WHERE task_type = %s
        """, (task_type,))
        
        if cursor.rowcount > 0:
            print(f"⏸️  Paused task: {task_type}")
        else:
            print(f"❌ Task not found: {task_type}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error pausing task: {e}")
        if conn:
            conn.rollback()
            conn.close()


def resume_task(task_type: str):
    """استئناف مهمة"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE scheduled_tasks
            SET status = 'active',
                fail_count = 0,
                last_status = 'ready'
            WHERE task_type = %s
        """, (task_type,))
        
        if cursor.rowcount > 0:
            print(f"▶️  Resumed task: {task_type}")
        else:
            print(f"❌ Task not found: {task_type}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error resuming task: {e}")
        if conn:
            conn.rollback()
            conn.close()


def force_run_task(task_type: str):
    """إجبار تشغيل مهمة الآن"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc)
        past_time = now - timedelta(minutes=1)
        
        cursor.execute("""
            UPDATE scheduled_tasks
            SET next_run_at = %s,
                locked_at = NULL,
                locked_by = NULL,
                last_status = 'ready'
            WHERE task_type = %s
        """, (past_time, task_type))
        
        if cursor.rowcount > 0:
            print(f"🚀 Forced run for task: {task_type}")
            print("   Task will be picked up by next worker poll")
        else:
            print(f"❌ Task not found: {task_type}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error forcing task run: {e}")
        if conn:
            conn.rollback()
            conn.close()


def unlock_task(task_type: str):
    """إلغاء قفل مهمة"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE scheduled_tasks
            SET locked_at = NULL,
                locked_by = NULL,
                last_status = 'unlocked'
            WHERE task_type = %s
        """, (task_type,))
        
        if cursor.rowcount > 0:
            print(f"🔓 Unlocked task: {task_type}")
        else:
            print(f"❌ Task not found: {task_type}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error unlocking task: {e}")
        if conn:
            conn.rollback()
            conn.close()


def reset_failures(task_type: str = None):
    """إعادة تعيين عدد الفشل"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        if task_type:
            cursor.execute("""
                UPDATE scheduled_tasks
                SET fail_count = 0,
                    last_status = 'ready',
                    status = 'active'
                WHERE task_type = %s
            """, (task_type,))
            
            if cursor.rowcount > 0:
                print(f"🔄 Reset failures for task: {task_type}")
            else:
                print(f"❌ Task not found: {task_type}")
        else:
            cursor.execute("""
                UPDATE scheduled_tasks
                SET fail_count = 0,
                    last_status = 'ready',
                    status = 'active'
                WHERE fail_count > 0
            """)
            
            print(f"🔄 Reset failures for {cursor.rowcount} tasks")
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error resetting failures: {e}")
        if conn:
            conn.rollback()
            conn.close()


def show_logs(task_type: str = None, limit: int = 20):
    """عرض logs"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        query = """
            SELECT 
                stl.executed_at,
                st.task_type,
                stl.status,
                stl.execution_time_seconds,
                stl.result,
                stl.error_message,
                stl.locked_by
            FROM scheduled_task_logs stl
            JOIN scheduled_tasks st ON stl.scheduled_task_id = st.id
        """
        
        params = []
        if task_type:
            query += " WHERE st.task_type = %s"
            params.append(task_type)
        
        query += " ORDER BY stl.executed_at DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, params)
        
        print(f"📝 Recent Logs{f' for {task_type}' if task_type else ''} (last {limit}):")
        print("-" * 100)
        print(f"{'Time':<12} {'Task':<20} {'Status':<10} {'Duration':<8} {'Worker':<15} {'Result/Error':<30}")
        print("-" * 100)
        
        for row in cursor.fetchall():
            executed_at, task_type_log, status, execution_time, result, error_message, locked_by = row
            
            time_str = executed_at.strftime('%H:%M:%S') if executed_at else 'Unknown'
            duration_str = f"{execution_time:.1f}s" if execution_time else '0s'
            worker_str = locked_by[:14] if locked_by else 'Unknown'
            
            if status == 'completed':
                result_str = (result or 'OK')[:29]
            else:
                result_str = (error_message or 'Unknown error')[:29]
            
            status_icon = "✅" if status == 'completed' else "❌"
            
            print(f"{time_str:<12} {task_type_log[:19]:<20} {status_icon} {status:<8} {duration_str:<8} {worker_str:<15} {result_str:<30}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error showing logs: {e}")
        if conn:
            conn.close()


def manage_concurrency(task_type: str = None, new_value: int = None):
    """إدارة إعدادات التشغيل المتزامن"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        if task_type and new_value is not None:
            # تحديث قيمة محددة
            cursor.execute("""
                UPDATE scheduled_tasks
                SET max_concurrent_runs = %s
                WHERE task_type = %s
            """, (new_value, task_type))
            
            if cursor.rowcount > 0:
                print(f"✅ Updated {task_type}: max_concurrent_runs = {new_value}")
            else:
                print(f"❌ Task not found: {task_type}")
            
            conn.commit()
        
        # عرض الإعدادات الحالية
        cursor.execute("""
            SELECT task_type, max_concurrent_runs, status
            FROM scheduled_tasks
            ORDER BY max_concurrent_runs DESC, task_type
        """)
        
        print(f"\n📊 Current Concurrency Settings:")
        print("-" * 50)
        print(f"{'Task Type':<25} {'Max Concurrent':<15} {'Status':<8}")
        print("-" * 50)
        
        total_possible = 0
        for row in cursor.fetchall():
            task_type_row, max_concurrent, status = row
            total_possible += max_concurrent
            status_icon = "✅" if status == 'active' else "⏸️"
            print(f"{task_type_row[:24]:<25} {max_concurrent:<15} {status_icon} {status}")
        
        print("-" * 50)
        print(f"Total possible concurrent jobs: {total_possible}")
        print(f"Available workers: 5")
        print(f"Theoretical efficiency: {min(100, (5/total_possible)*100):.1f}%")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error managing concurrency: {e}")
        if conn:
            conn.rollback()
            conn.close()


def cleanup_logs(days: int = 30):
    """تنظيف logs قديمة"""
    conn = get_db_connection()
    if not conn:
        return
    
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
        
    except Exception as e:
        print(f"❌ Error cleaning logs: {e}")
        if conn:
            conn.rollback()
            conn.close()


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description='Production Scheduler Management Tool')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List tasks
    subparsers.add_parser('list', help='List all scheduled tasks')
    
    # Pause task
    pause_parser = subparsers.add_parser('pause', help='Pause a task')
    pause_parser.add_argument('task_type', help='Task type to pause')
    
    # Resume task
    resume_parser = subparsers.add_parser('resume', help='Resume a task')
    resume_parser.add_argument('task_type', help='Task type to resume')
    
    # Force run task
    run_parser = subparsers.add_parser('run', help='Force run a task now')
    run_parser.add_argument('task_type', help='Task type to run')
    
    # Unlock task
    unlock_parser = subparsers.add_parser('unlock', help='Unlock a stuck task')
    unlock_parser.add_argument('task_type', help='Task type to unlock')
    
    # Reset failures
    reset_parser = subparsers.add_parser('reset', help='Reset failure count')
    reset_parser.add_argument('task_type', nargs='?', help='Task type to reset (optional, resets all if not specified)')
    
    # Show logs
    logs_parser = subparsers.add_parser('logs', help='Show recent logs')
    logs_parser.add_argument('task_type', nargs='?', help='Task type to filter (optional)')
    logs_parser.add_argument('--limit', type=int, default=20, help='Number of logs to show')
    
    # Cleanup logs
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean old logs')
    cleanup_parser.add_argument('--days', type=int, default=30, help='Delete logs older than N days')
    
    # Health check
    subparsers.add_parser('health', help='Show scheduler health')
    
    # Performance monitoring
    perf_parser = subparsers.add_parser('performance', help='Show parallel performance stats')
    perf_parser.add_argument('--hours', type=int, default=1, help='Hours of history to analyze')
    
    # Concurrency management
    conc_parser = subparsers.add_parser('concurrency', help='Show/update concurrency settings')
    conc_parser.add_argument('task_type', nargs='?', help='Task type to update')
    conc_parser.add_argument('--set', type=int, help='Set max concurrent runs')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    print(f"🎛️  Scheduler Management - {args.command.upper()}")
    print("=" * 50)
    
    if args.command == 'list':
        list_tasks()
    elif args.command == 'pause':
        pause_task(args.task_type)
    elif args.command == 'resume':
        resume_task(args.task_type)
    elif args.command == 'run':
        force_run_task(args.task_type)
    elif args.command == 'unlock':
        unlock_task(args.task_type)
    elif args.command == 'reset':
        reset_failures(args.task_type)
    elif args.command == 'logs':
        show_logs(args.task_type, args.limit)
    elif args.command == 'cleanup':
        cleanup_logs(args.days)
    elif args.command == 'health':
        from scheduler_health import print_health_report
        print_health_report()
    elif args.command == 'performance':
        from monitor_parallel_performance import print_performance_report
        print_performance_report(args.hours)
    elif args.command == 'concurrency':
        manage_concurrency(args.task_type, args.set)


if __name__ == "__main__":
    main()