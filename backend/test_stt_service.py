#!/usr/bin/env python3
"""
🧪 Test STT Service
Quick test to verify Google Cloud Speech-to-Text is working
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

def test_credentials():
    """Test if Google credentials are configured"""
    print("=" * 60)
    print("🔑 Checking Google Cloud Credentials")
    print("=" * 60)
    
    credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    if credentials_json:
        print("✅ GOOGLE_CREDENTIALS_JSON is set")
        print(f"   Length: {len(credentials_json)} chars")
        # Check if it's valid JSON
        try:
            import json
            creds = json.loads(credentials_json)
            print(f"   Project ID: {creds.get('project_id', 'N/A')}")
            print(f"   Client Email: {creds.get('client_email', 'N/A')[:50]}...")
        except:
            print("   ⚠️  Warning: Could not parse as JSON")
    else:
        print("❌ GOOGLE_CREDENTIALS_JSON is NOT set")
    
    if credentials_path:
        print(f"\n✅ GOOGLE_APPLICATION_CREDENTIALS is set: {credentials_path}")
        if os.path.exists(credentials_path):
            print("   ✅ File exists")
        else:
            print("   ❌ File does NOT exist")
    else:
        print("\n❌ GOOGLE_APPLICATION_CREDENTIALS is NOT set")
    
    return bool(credentials_json or (credentials_path and os.path.exists(credentials_path)))


def test_stt_init():
    """Test STT Service initialization"""
    print("\n" + "=" * 60)
    print("🎙️ Testing STT Service Initialization")
    print("=" * 60)
    
    try:
        from app.services.generators.stt_service import STTService
        stt = STTService()
        print("✅ STT Service initialized successfully!")
        return stt
    except Exception as e:
        print(f"❌ STT Service initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_transcription(stt, audio_url: str):
    """Test actual transcription"""
    print("\n" + "=" * 60)
    print("🎤 Testing Transcription")
    print("=" * 60)
    print(f"Audio URL: {audio_url}")
    
    try:
        result = stt.transcribe_audio(audio_url)
        
        if result.get('success'):
            print("\n✅ Transcription successful!")
            print(f"\n📝 Text: {result.get('text', '')[:200]}...")
            print(f"\n📊 Stats:")
            print(f"   Confidence: {result.get('confidence', 0):.2%}")
            print(f"   Characters: {result.get('char_count', 0)}")
            print(f"   Words: {result.get('word_count', 0)}")
        else:
            print(f"\n❌ Transcription failed: {result.get('error')}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("\n" + "=" * 70)
    print("🧪 STT SERVICE TEST")
    print("=" * 70)
    
    # Test 1: Credentials
    if not test_credentials():
        print("\n⚠️  No valid credentials found. Please configure:")
        print("   - GOOGLE_CREDENTIALS_JSON (for production)")
        print("   - GOOGLE_APPLICATION_CREDENTIALS (for local dev)")
        return
    
    # Test 2: STT Init
    stt = test_stt_init()
    if not stt:
        return
    
    # Test 3: Transcription (optional)
    print("\n" + "=" * 60)
    audio_url = input("Enter audio URL to test (or press Enter to skip): ").strip()
    
    if audio_url:
        test_transcription(stt, audio_url)
    else:
        print("⏭️  Skipped transcription test")
    
    print("\n" + "=" * 70)
    print("🏁 Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    main()
