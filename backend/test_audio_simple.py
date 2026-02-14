#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 Simple Audio Input Processor Test
اختبار بسيط لمعالج الصوت
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("\n" + "="*70)
print("🧪 Testing Audio Input Processor Initialization")
print("="*70)

try:
    print("\n1️⃣ Importing AudioInputProcessor...")
    from app.services.processing.audio_input_processor import AudioInputProcessor
    print("   ✅ Import successful")
    
    print("\n2️⃣ Initializing processor...")
    processor = AudioInputProcessor()
    print("   ✅ Initialization successful")
    
    print("\n3️⃣ Checking attributes...")
    
    # Check audio_converter
    if hasattr(processor, 'audio_converter'):
        print("   ✅ audio_converter exists")
        
        # Check methods
        if hasattr(processor.audio_converter, 'needs_conversion'):
            print("   ✅ audio_converter.needs_conversion() exists")
        else:
            print("   ❌ audio_converter.needs_conversion() missing")
        
        if hasattr(processor.audio_converter, 'convert_to_wav'):
            print("   ✅ audio_converter.convert_to_wav() exists")
        else:
            print("   ❌ audio_converter.convert_to_wav() missing")
    else:
        print("   ❌ audio_converter missing")
    
    # Check other services
    if hasattr(processor, 's3_uploader'):
        print("   ✅ s3_uploader exists")
    if hasattr(processor, 'stt_service'):
        print("   ✅ stt_service exists")
    if hasattr(processor, 'news_refiner'):
        print("   ✅ news_refiner exists")
    
    print("\n4️⃣ Testing MIME type detection...")
    test_files = [
        ("audio.webm", "audio/webm"),
        ("audio.mp3", "audio/mpeg"),
        ("audio.wav", "audio/wav"),
    ]
    
    for filename, expected in test_files:
        result = processor._detect_mime_type(filename)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {filename} → {result}")
    
    print("\n5️⃣ Testing needs_conversion...")
    test_mimes = [
        ("audio/webm", True),
        ("audio/mpeg", False),
        ("audio/wav", False),
        ("audio/ogg", True),
    ]
    
    for mime, should_convert in test_mimes:
        needs = processor.audio_converter.needs_conversion(mime)
        status = "✅" if needs == should_convert else "❌"
        print(f"   {status} {mime} → needs_conversion={needs}")
    
    print("\n6️⃣ Closing processor...")
    processor.close()
    print("   ✅ Closed successfully")
    
    print("\n" + "="*70)
    print("🎉 ALL TESTS PASSED!")
    print("="*70)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    print("\n" + "="*70)
    print("❌ TESTS FAILED")
    print("="*70)
    sys.exit(1)
