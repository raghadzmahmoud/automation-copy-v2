#!/usr/bin/env python3
"""
🧪 Test Audio Upload Flow
اختبار الفلو الكامل من Upload لحد raw_news
"""
import psycopg2
from settings import DB_CONFIG

def check_audio_flow():
    """فحص الفلو الكامل"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("\n" + "="*70)
    print("🎙️ Audio Upload Flow Status")
    print("="*70)
    
    # 1. Check scheduled task
    print("\n1️⃣ Scheduled Task:")
    cur.execute("""
        SELECT id, name, task_type, schedule_pattern, status, 
               next_run_at, last_run_at, last_status
        FROM scheduled_tasks 
        WHERE task_type = 'audio_transcription'
    """)
    
    task = cur.fetchone()
    if task:
        print(f"   ✅ Task exists: {task[1]}")
        print(f"   📅 Schedule: {task[3]}")
        print(f"   🟢 Status: {task[4]}")
        print(f"   ⏰ Next run: {task[5]}")
        print(f"   📊 Last status: {task[7]}")
    else:
        print("   ❌ No audio_transcription task found!")
    
    # 2. Check pending files
    print("\n2️⃣ Pending Audio Files:")
    cur.execute("""
        SELECT COUNT(*), processing_status
        FROM uploaded_files
        WHERE file_type = 'audio'
        GROUP BY processing_status
        ORDER BY processing_status
    """)
    
    statuses = cur.fetchall()
    if statuses:
        for count, status in statuses:
            icon = "⏳" if status == "pending" else "✅" if status == "completed" else "❌"
            print(f"   {icon} {status}: {count} files")
    else:
        print("   📭 No audio files uploaded yet")
    
    # 3. Check recent uploads
    print("\n3️⃣ Recent Uploads (last 5):")
    cur.execute("""
        SELECT id, original_filename, processing_status, 
               created_at, processed_at
        FROM uploaded_files
        WHERE file_type = 'audio'
        ORDER BY created_at DESC
        LIMIT 5
    """)
    
    recent = cur.fetchall()
    if recent:
        for row in recent:
            status_icon = "⏳" if row[2] == "pending" else "✅" if row[2] == "completed" else "❌"
            print(f"   {status_icon} [{row[0]}] {row[1]}")
            print(f"      Status: {row[2]}, Created: {row[3]}")
            if row[4]:
                print(f"      Processed: {row[4]}")
    else:
        print("   📭 No uploads yet")
    
    # 4. Check news created from audio
    print("\n4️⃣ News from Audio:")
    cur.execute("""
        SELECT COUNT(*)
        FROM raw_news
        WHERE source_type_id IN (6, 7)
    """)
    
    news_count = cur.fetchone()[0]
    print(f"   📰 Total news from audio: {news_count}")
    
    if news_count > 0:
        cur.execute("""
            SELECT id, title, category_id, collected_at
            FROM raw_news
            WHERE source_type_id IN (6, 7)
            ORDER BY collected_at DESC
            LIMIT 3
        """)
        
        print("\n   Recent news:")
        for row in cur.fetchall():
            print(f"   📄 [{row[0]}] {row[1][:50]}...")
            print(f"      Category: {row[2]}, Date: {row[3]}")
    
    # 5. Check worker logs
    print("\n5️⃣ Recent Job Executions:")
    cur.execute("""
        SELECT task_type, status, started_at, finished_at, error_message
        FROM scheduled_task_logs
        WHERE task_type = 'audio_transcription'
        ORDER BY started_at DESC
        LIMIT 3
    """)
    
    logs = cur.fetchall()
    if logs:
        for row in logs:
            status_icon = "✅" if row[1] == "completed" else "❌"
            print(f"   {status_icon} {row[0]}: {row[1]}")
            print(f"      Started: {row[2]}")
            if row[4]:
                print(f"      Error: {row[4]}")
    else:
        print("   📭 No execution logs yet")
    
    print("\n" + "="*70)
    print("✅ Flow check complete!")
    print("="*70 + "\n")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_audio_flow()
