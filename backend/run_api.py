#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🚀 تشغيل AI Media Center API محلياً
"""

import os
import sys
import subprocess
import signal
import time

def run_api():
    """تشغيل الـ FastAPI application"""
    
    print("=" * 60)
    print("🚀 تشغيل AI Media Center API محلياً")
    print("=" * 60)
    
    # التحقق من وجود ملف .env
    if not os.path.exists('.env'):
        print("⚠️  تحذير: ملف .env غير موجود")
        print("   قم بنسخ .env.example إلى .env وتعديل الإعدادات")
        if os.path.exists('.env.example'):
            with open('.env.example', 'r') as f:
                example_content = f.read()
            print(f"\nمحتوى .env.example:\n{example_content}")
    
    # تعيين PORT إذا لم يكن موجوداً
    port = os.getenv('PORT', '8000')
    os.environ['PORT'] = port
    
    print(f"📌 المجلد الحالي: {os.getcwd()}")
    print(f"🌐 الـ Host: 0.0.0.0")
    print(f"🔌 الـ Port: {port}")
    print(f"📚 API Docs: http://localhost:{port}/docs")
    print(f"🌐 Public URL: http://0.0.0.0:{port}")
    print("=" * 60)
    
    # بناء الأمر
    command = [
        'uvicorn',
        'app.main:app',
        '--host', '0.0.0.0',
        '--port', port,
        '--reload'
    ]
    
    print(f"▶️  الأمر: {' '.join(command)}")
    print("=" * 60)
    print("🔄 جاري التشغيل... (اضغط Ctrl+C للإيقاف)")
    print("=" * 60)
    
    try:
        # تشغيل الأمر
        subprocess.run(command)
    except KeyboardInterrupt:
        print("\n⏹️  تم إيقاف الخادم")
    except Exception as e:
        print(f"❌ خطأ: {e}")
        sys.exit(1)

def check_dependencies():
    """التحقق من تثبيت المتطلبات"""
    print("🔍 التحقق من المتطلبات...")
    
    # التحقق من uvicorn
    try:
        import uvicorn
        print("✅ uvicorn مثبت")
    except ImportError:
        print("❌ uvicorn غير مثبت")
        print("   قم بتثبيته: pip install uvicorn")
        return False
    
    # التحقق من fastapi
    try:
        import fastapi
        print("✅ fastapi مثبت")
    except ImportError:
        print("❌ fastapi غير مثبت")
        print("   قم بتثبيته: pip install fastapi")
        return False
    
    # التحقق من psycopg2
    try:
        import psycopg2
        print("✅ psycopg2 مثبت")
    except ImportError:
        print("❌ psycopg2 غير مثبت")
        print("   قم بتثبيته: pip install psycopg2-binary")
        return False
    
    return True

if __name__ == "__main__":
    # تغيير المسار إلى مجلد backend إذا لزم الأمر
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if not current_dir.endswith('backend'):
        backend_dir = os.path.join(current_dir, 'backend')
        if os.path.exists(backend_dir):
            os.chdir(backend_dir)
            print(f"📁 تغيير المسار إلى: {backend_dir}")
    
    # التحقق من المتطلبات
    if check_dependencies():
        run_api()
    else:
        print("\n⚠️  يرجى تثبيت المتطلبات أولاً:")
        print("   pip install -r requirements.txt")
        sys.exit(1)