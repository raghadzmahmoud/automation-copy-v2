#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🚀 Optimize Concurrency Settings
تحسين إعدادات التشغيل المتزامن للمهام
"""

import os
import sys
import psycopg2
from datetime import datetime, timezone

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settings import DB_CONFIG

# 🔥 Optimized concurrency settings for 5 workers (Content Generation + Social Media)
CONCURRENCY_SETTINGS = {
    # High concurrency - can run multiple instances safely
    'report_generation': 3,           # Reports can be generated in parallel
    'audio_transcription': 3,         # STT can process multiple files
    'social_media_generation': 2,     # Social media content generation
    'image_generation': 2,            # Image generation (if not too resource heavy)
    'audio_generation': 2,            # Audio generation
    
    # Medium concurrency - limited parallel execution
    'processing_pipeline': 1,         # Pipeline should be sequential
    
    # Low concurrency - must be sequential
    'scraping': 1,                    # Scraping should be coordinated
    'clustering': 1,                  # Clustering needs all data
    'broadcast_generation': 1,        # Broadcast generation
    'bulletin_generation': 1,         # Bulletin generation
    'digest_generation': 1,           # Digest generation
}


def update_concurrency_settings():
    """تحديث إعدادات التشغيل المتزامن"""
    print("🚀 Optimizing concurrency settings for 5 workers...")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # عرض الإعدادات الحالية
        cursor.execute("""
            SELECT task_type, max_concurrent_runs, status
            FROM scheduled_tasks
            ORDER BY task_type
        """)
        
        print("\n📋 Current settings:")
        current_settings = {}
        for row in cursor.fetchall():
            task_type, max_concurrent, status = row
            current_settings[task_type] = max_concurrent
            print(f"   {task_type}: {max_concurrent} concurrent runs ({status})")
        
        # تطبيق الإعدادات الجديدة
        print(f"\n🔄 Applying optimized settings...")
        updated_count = 0
        
        for task_type, new_concurrent_runs in CONCURRENCY_SETTINGS.items():
            current_runs = current_settings.get(task_type, 1)
            
            if current_runs != new_concurrent_runs:
                cursor.execute("""
                    UPDATE scheduled_tasks
                    SET max_concurrent_runs = %s
                    WHERE task_type = %s
                """, (new_concurrent_runs, task_type))
                
                if cursor.rowcount > 0:
                    print(f"   ✅ {task_type}: {current_runs} → {new_concurrent_runs}")
                    updated_count += 1
                else:
                    print(f"   ⚠️  {task_type}: not found in database")
            else:
                print(f"   ⏭️  {task_type}: already optimized ({new_concurrent_runs})")
        
        conn.commit()
        
        # عرض الإعدادات الجديدة
        cursor.execute("""
            SELECT task_type, max_concurrent_runs, status
            FROM scheduled_tasks
            ORDER BY max_concurrent_runs DESC, task_type
        """)
        
        print(f"\n📊 Updated settings (updated {updated_count} tasks):")
        total_possible_concurrent = 0
        
        for row in cursor.fetchall():
            task_type, max_concurrent, status = row
            total_possible_concurrent += max_concurrent
            status_icon = "✅" if status == 'active' else "⏸️"
            print(f"   {status_icon} {task_type}: {max_concurrent} concurrent runs")
        
        print(f"\n🎯 Performance Analysis:")
        print(f"   Total workers: 5")
        print(f"   Max theoretical concurrent jobs: {total_possible_concurrent}")
        print(f"   Efficiency: {min(100, (5/total_possible_concurrent)*100):.1f}%")
        
        # تحليل الأداء المتوقع
        print(f"\n📈 Expected Performance Improvements:")
        print(f"   🔥 High-concurrency tasks (2-3 workers each):")
        for task_type, concurrent in CONCURRENCY_SETTINGS.items():
            if concurrent >= 2:
                print(f"      • {task_type}: up to {concurrent}x faster")
        
        print(f"\n   ⚡ With 5 workers, you can now run:")
        print(f"      • 3 report generations simultaneously")
        print(f"      • 3 audio transcriptions simultaneously") 
        print(f"      • 2 image generations + 2 social media generations")
        print(f"      • Multiple content generation tasks in parallel")
        
        cursor.close()
        conn.close()
        
        print(f"\n✅ Concurrency optimization completed!")
        print(f"\n🚀 Next steps:")
        print(f"   1. Deploy the 5 workers to Render")
        print(f"   2. Monitor performance with: python scheduler_health.py")
        print(f"   3. Watch for parallel execution in logs")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating concurrency settings: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


def show_worker_distribution():
    """عرض توزيع العمل المتوقع على الـ workers"""
    print("\n🎯 Expected Worker Distribution (5 workers):")
    print("=" * 60)
    
    scenarios = [
        {
            "name": "Peak Load Scenario",
            "jobs": [
                ("report_generation", 3),
                ("audio_transcription", 2),
            ]
        },
        {
            "name": "Content Generation Scenario", 
            "jobs": [
                ("social_media_generation", 2),
                ("image_generation", 2),
                ("scraping", 1),
            ]
        },
        {
            "name": "Media Processing Scenario",
            "jobs": [
                ("audio_generation", 2),
                ("reel_generation", 2),
                ("clustering", 1),
            ]
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['name']}:")
        total_workers_used = sum(count for _, count in scenario['jobs'])
        
        for job_type, worker_count in scenario['jobs']:
            print(f"   • {job_type}: {worker_count} workers")
        
        print(f"   📊 Total workers used: {total_workers_used}/5")
        print(f"   🎯 Efficiency: {(total_workers_used/5)*100:.0f}%")


if __name__ == "__main__":
    print("🚀 Production Scheduler - Concurrency Optimization")
    print("=" * 60)
    
    success = update_concurrency_settings()
    
    if success:
        show_worker_distribution()
    
    sys.exit(0 if success else 1)