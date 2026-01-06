#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 Test STT Service Directly
اختبار مباشر لخدمة STT
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("\n" + "="*70)
print("🧪 Testing STT Service")
print("="*70)

try:
    print("\n1️⃣ Importing STTService...")
    from app.services.generators.stt_service import STTService
    print("   ✅ Import successful")
    
    print("\n2️⃣ Initializing STTService...")
    try:
        stt = STTService()
        print("   ✅ STTService initialized successfully")
    except Exception as e:
        print(f"   ❌ STTService initialization failed: {e}")
        print("\n💡 This is the problem! STT service can't initialize.")
        print("   Check your Google Cloud credentials:")
        print("   - GOOGLE_CREDENTIALS_JSON environment variable")
        print("   - or GOOGLE_APPLICATION_CREDENTIALS file path")
        sys.exit(1)
    
    print("\n3️⃣ Testing with a sample audio URL...")
    # Use the failed audio URL from database
    test_url = "https://media-automation-bucket.s3.us-east-1.amazonaws.com/original/audios/audio_20260106_130349_ab0d056d.mp3"
    
    print(f"   📥 Testing URL: {test_url}")
    result = stt.transcribe_audio(test_url)
    
    if result.get('success'):
        print(f"   ✅ Transcription successful!")
        print(f"   📝 Text: {result.get('text', '')[:100]}...")
        print(f"   🎯 Confidence: {result.get('confidence', 0):.2%}")
    else:
        print(f"   ❌ Transcription failed!")
        print(f"   ❌ Error: {result.get('error')}")
    
    print("\n" + "="*70)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
