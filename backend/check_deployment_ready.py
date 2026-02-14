#!/usr/bin/env python3
"""
🔍 Deployment Readiness Check
تحقق من جاهزية المشروع للـ deployment على Railway
"""
import os
import sys

def check_env_vars():
    """فحص المتغيرات البيئية المطلوبة"""
    print("\n1️⃣ Checking Environment Variables...")
    
    required_vars = [
        'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT',
        'GEMINI_API_KEY',
        'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'S3_BUCKET_NAME'
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
            print(f"   ❌ {var} - Missing")
        else:
            print(f"   ✅ {var} - Set")
    
    return len(missing) == 0, missing

def check_files():
    """فحص الملفات المطلوبة"""
    print("\n2️⃣ Checking Required Files...")
    
    required_files = [
        'Dockerfile.worker',
        'worker.py',
        'requirements.txt',
        'settings.py'
    ]
    
    missing = []
    for file in required_files:
        if os.path.exists(file):
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} - Missing")
            missing.append(file)
    
    return len(missing) == 0, missing


def check_database():
    """فحص الاتصال بقاعدة البيانات"""
    print("\n3️⃣ Checking Database Connection...")
    
    try:
        from settings import DB_CONFIG
        import psycopg2
        
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Check scheduled_tasks table
        cur.execute("SELECT COUNT(*) FROM scheduled_tasks WHERE status = 'active'")
        active_tasks = cur.fetchone()[0]
        print(f"   ✅ Database connected")
        print(f"   📋 Active tasks: {active_tasks}")
        
        # Check audio_transcription task
        cur.execute("""
            SELECT id, name, schedule_pattern 
            FROM scheduled_tasks 
            WHERE task_type = 'audio_transcription' AND status = 'active'
        """)
        audio_task = cur.fetchone()
        if audio_task:
            print(f"   ✅ Audio transcription task: {audio_task[1]} ({audio_task[2]})")
        else:
            print(f"   ⚠️  Audio transcription task not found or inactive")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")
        return False

def check_dependencies():
    """فحص المكتبات المطلوبة"""
    print("\n4️⃣ Checking Python Dependencies...")
    
    required_packages = [
        'fastapi', 'psycopg2', 'google.generativeai',
        'boto3', 'croniter', 'arabic_reshaper'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} - Not installed")
            missing.append(package)
    
    return len(missing) == 0, missing

def main():
    print("═" * 70)
    print("🔍 Railway Deployment Readiness Check")
    print("═" * 70)
    
    all_good = True
    
    # Check environment variables
    env_ok, missing_env = check_env_vars()
    if not env_ok:
        all_good = False
        print(f"\n   ⚠️  Missing env vars: {', '.join(missing_env)}")
    
    # Check files
    files_ok, missing_files = check_files()
    if not files_ok:
        all_good = False
        print(f"\n   ⚠️  Missing files: {', '.join(missing_files)}")
    
    # Check database
    db_ok = check_database()
    if not db_ok:
        all_good = False
    
    # Check dependencies
    deps_ok, missing_deps = check_dependencies()
    if not deps_ok:
        all_good = False
        print(f"\n   ⚠️  Missing packages: {', '.join(missing_deps)}")
    
    print("\n" + "═" * 70)
    if all_good:
        print("✅ All checks passed! Ready for deployment.")
    else:
        print("❌ Some checks failed. Fix issues before deploying.")
    print("═" * 70 + "\n")
    
    return 0 if all_good else 1

if __name__ == "__main__":
    sys.exit(main())
