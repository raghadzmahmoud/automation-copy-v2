#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔧 Apply Scheduler Database Migration
تطبيق تعديلات قاعدة البيانات للـ Production Job Runner
"""

import os
import sys
import psycopg2
from datetime import datetime, timezone

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settings import DB_CONFIG


def apply_migration():
    """تطبيق migration للـ scheduler"""
    print("🔧 Applying scheduler database migration...")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("📋 Current scheduled_tasks structure:")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'scheduled_tasks'
            ORDER BY ordinal_position
        """)
        
        for row in cursor.fetchall():
            print(f"   {row[0]}: {row[1]} ({'NULL' if row[2] == 'YES' else 'NOT NULL'})")
        
        print("\n🔄 Adding new columns...")
        
        # Add new columns
        migrations = [
            "ALTER TABLE scheduled_tasks ADD COLUMN IF NOT EXISTS next_run_at TIMESTAMP NULL",
            "ALTER TABLE scheduled_tasks ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP NULL", 
            "ALTER TABLE scheduled_tasks ADD COLUMN IF NOT EXISTS locked_by TEXT NULL",
            "ALTER TABLE scheduled_tasks ADD COLUMN IF NOT EXISTS fail_count INT DEFAULT 0",
            "ALTER TABLE scheduled_tasks ADD COLUMN IF NOT EXISTS last_status TEXT NULL",
            "ALTER TABLE scheduled_tasks ADD COLUMN IF NOT EXISTS max_concurrent_runs INT DEFAULT 1"
        ]
        
        for migration in migrations:
            try:
                cursor.execute(migration)
                print(f"   ✅ {migration}")
            except Exception as e:
                print(f"   ⚠️  {migration} - {e}")
        
        print("\n📊 Creating indexes...")
        
        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_due ON scheduled_tasks (status, next_run_at)",
            "CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_lock ON scheduled_tasks (locked_at)",
            "CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_type_status ON scheduled_tasks (task_type, status)"
        ]
        
        for index in indexes:
            try:
                cursor.execute(index)
                print(f"   ✅ {index}")
            except Exception as e:
                print(f"   ⚠️  {index} - {e}")
        
        print("\n📝 Updating scheduled_task_logs...")
        
        # Update logs table
        log_migrations = [
            "ALTER TABLE scheduled_task_logs ADD COLUMN IF NOT EXISTS started_at TIMESTAMP NULL",
            "ALTER TABLE scheduled_task_logs ADD COLUMN IF NOT EXISTS finished_at TIMESTAMP NULL",
            "ALTER TABLE scheduled_task_logs ADD COLUMN IF NOT EXISTS locked_by TEXT NULL"
        ]
        
        for migration in log_migrations:
            try:
                cursor.execute(migration)
                print(f"   ✅ {migration}")
            except Exception as e:
                print(f"   ⚠️  {migration} - {e}")
        
        print("\n🔄 Initializing existing tasks...")
        
        # Initialize existing tasks
        now = datetime.now(timezone.utc)
        
        cursor.execute("""
            UPDATE scheduled_tasks 
            SET next_run_at = COALESCE(last_run_at, %s),
                last_status = 'ready'
            WHERE next_run_at IS NULL AND status = 'active'
        """, (now,))
        
        updated_count = cursor.rowcount
        print(f"   ✅ Initialized {updated_count} active tasks")
        
        # Commit all changes
        conn.commit()
        
        print("\n📋 Updated scheduled_tasks structure:")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'scheduled_tasks'
            ORDER BY ordinal_position
        """)
        
        for row in cursor.fetchall():
            print(f"   {row[0]}: {row[1]} ({'NULL' if row[2] == 'YES' else 'NOT NULL'})")
        
        print("\n📊 Current tasks status:")
        cursor.execute("""
            SELECT task_type, status, next_run_at, last_status, fail_count
            FROM scheduled_tasks
            ORDER BY id
        """)
        
        for row in cursor.fetchall():
            task_type, status, next_run_at, last_status, fail_count = row
            next_run_str = next_run_at.strftime('%H:%M:%S') if next_run_at else 'NULL'
            print(f"   {task_type}: {status} | next: {next_run_str} | status: {last_status} | fails: {fail_count}")
        
        cursor.close()
        conn.close()
        
        print("\n✅ Migration completed successfully!")
        print("\n🚀 Next steps:")
        print("   1. Run: python scheduler.py (in background)")
        print("   2. Run: python worker.py (one or more instances)")
        print("   3. Check logs in logs/ directory")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


if __name__ == "__main__":
    success = apply_migration()
    sys.exit(0 if success else 1)