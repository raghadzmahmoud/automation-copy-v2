#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎙️ STT Service (Speech-to-Text)
تحويل الصوت إلى نص باستخدام Google Cloud Speech-to-Text
"""

import os
import sys
from typing import Optional, Dict
import requests
import tempfile

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Google Cloud Speech-to-Text
try:
    from google.cloud import speech
except ImportError:
    print("❌ google-cloud-speech not installed")
    print("   Run: pip install google-cloud-speech")
    sys.exit(1)


class STTService:
    """
    تحويل ملفات الصوت إلى نص
    
    Usage:
        stt = STTService()
        result = stt.transcribe_audio("https://s3.../audio.mp3")
        # Returns: {'success': True, 'text': '...', 'language': 'ar'}
    """
    
    def __init__(self):
        """Initialize Google Cloud Speech-to-Text"""
        try:
            # نفس طريقة TTS بالضبط! ✅
            credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            
            if credentials_json:
                import json
                from google.oauth2 import service_account
                
                credentials_dict = json.loads(credentials_json)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_dict,
                    scopes=['https://www.googleapis.com/auth/cloud-platform']
                )
                self.client = speech.SpeechClient(credentials=credentials)
                print("✅ STTService initialized (from JSON env var)")
                
            elif credentials_path and os.path.exists(credentials_path):
                self.client = speech.SpeechClient()
                print("✅ STTService initialized (from file)")
                print(f"   🔑 Using credentials: {credentials_path}")
                
            else:
                raise ValueError(
                    "Google credentials not found. Set one of:\n"
                    "  - GOOGLE_CREDENTIALS_JSON (for Render/production)\n"
                    "  - GOOGLE_APPLICATION_CREDENTIALS (for local development)"
                )
            
        except Exception as e:
            print(f"❌ STTService initialization failed: {e}")
            raise
    
    def transcribe_audio(self, audio_url: str, max_retries: int = 3) -> Dict:
        """
        تحويل ملف صوتي إلى نص
        
        Args:
            audio_url: رابط الملف الصوتي (S3 URL)
            max_retries: عدد المحاولات عند الفشل
        
        Returns:
            {
                'success': True/False,
                'text': 'النص المستخرج من الصوت',
                'language': 'ar',
                'confidence': 0.95,
                'char_count': 120,
                'word_count': 20,
                'error': 'رسالة الخطأ (لو في)'
            }
        """
        
        if not audio_url:
            return {
                'success': False,
                'error': 'رابط الصوت فارغ'
            }
        
        print(f"🎙️ Transcribing audio: {audio_url}")
        
        # ========================================
        # تحميل الملف من S3
        # ========================================
        try:
            audio_file_path = self._download_audio(audio_url)
            print(f"✅ Audio downloaded: {audio_file_path}")
        except Exception as e:
            return {
                'success': False,
                'error': f'فشل تحميل الملف: {str(e)}'
            }
        
        # ========================================
        # محاولات الـ Transcription
        # ========================================
        for attempt in range(max_retries):
            try:
                print(f"🤖 Transcribing... (attempt {attempt + 1}/{max_retries})")
                
                # قراءة الملف الصوتي
                with open(audio_file_path, 'rb') as audio_file:
                    audio_content = audio_file.read()
                
                # تحديد نوع الملف
                file_extension = audio_url.split('.')[-1].lower()
                encoding = self._get_audio_encoding(file_extension)
                
                # إعداد Audio Config
                audio = speech.RecognitionAudio(content=audio_content)
                
                config = speech.RecognitionConfig(
                    encoding=encoding,
                    language_code='ar-SA',  # Arabic (Saudi Arabia)
                    alternative_language_codes=['ar-EG', 'ar-JO', 'ar-PS'],  # Egyptian, Jordanian, Palestinian
                    enable_automatic_punctuation=True,
                    model='default',
                    use_enhanced=True  # استخدام النموذج المحسّن
                )
                
                # استدعاء Google Cloud Speech API
                print(f"   📤 Sending to Google Cloud Speech API...")
                response = self.client.recognize(config=config, audio=audio)
                
                # استخراج النص
                transcription = self._extract_transcription(response)
                
                # التحقق من النتيجة
                if not transcription or len(transcription) < 10:
                    print(f"⚠️  Transcription too short: {len(transcription) if transcription else 0} chars")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return {
                            'success': False,
                            'error': 'النص المستخرج قصير جداً أو فارغ'
                        }
                
                # حساب الثقة المتوسطة
                confidence = self._calculate_confidence(response)
                
                print(f"✅ Transcription successful: {len(transcription)} chars")
                print(f"   Preview: {transcription[:100]}...")
                print(f"   Confidence: {confidence:.2%}")
                
                # حذف الملف المؤقت
                self._cleanup(audio_file_path)
                
                return {
                    'success': True,
                    'text': transcription,
                    'language': 'ar',
                    'confidence': confidence,
                    'char_count': len(transcription),
                    'word_count': len(transcription.split())
                }
                
            except Exception as e:
                print(f"❌ Attempt {attempt + 1} failed: {e}")
                
                # حذف الملف المؤقت
                try:
                    self._cleanup(audio_file_path)
                except:
                    pass
                
                if attempt == max_retries - 1:
                    # آخر محاولة فشلت
                    return {
                        'success': False,
                        'error': f'فشل التحويل بعد {max_retries} محاولات: {str(e)}'
                    }
                
                continue
        
        # كل المحاولات فشلت
        return {
            'success': False,
            'error': 'فشل تحويل الصوت إلى نص'
        }
    
    def transcribe_audio_file(self, file_path: str) -> Dict:
        """
        تحويل ملف صوتي محلي إلى نص
        (للاستخدام المباشر بدون S3)
        
        Args:
            file_path: مسار الملف المحلي
        
        Returns:
            نفس صيغة transcribe_audio()
        """
        
        if not os.path.exists(file_path):
            return {
                'success': False,
                'error': 'الملف غير موجود'
            }
        
        try:
            print(f"🎙️ Transcribing local file: {file_path}")
            
            # قراءة الملف
            with open(file_path, 'rb') as audio_file:
                audio_content = audio_file.read()
            
            # تحديد نوع الملف
            file_extension = file_path.split('.')[-1].lower()
            encoding = self._get_audio_encoding(file_extension)
            
            # إعداد Config
            audio = speech.RecognitionAudio(content=audio_content)
            
            config = speech.RecognitionConfig(
                encoding=encoding,
                language_code='ar-SA',
                alternative_language_codes=['ar-EG', 'ar-JO', 'ar-PS'],
                enable_automatic_punctuation=True,
                model='default',
                use_enhanced=True
            )
            
            # Transcription
            print(f"   📤 Sending to Google Cloud Speech API...")
            response = self.client.recognize(config=config, audio=audio)
            
            # استخراج النص
            transcription = self._extract_transcription(response)
            
            if not transcription:
                return {
                    'success': False,
                    'error': 'لم يتم استخراج أي نص'
                }
            
            # حساب الثقة
            confidence = self._calculate_confidence(response)
            
            print(f"✅ Transcription successful: {len(transcription)} chars")
            print(f"   Confidence: {confidence:.2%}")
            
            return {
                'success': True,
                'text': transcription,
                'language': 'ar',
                'confidence': confidence,
                'char_count': len(transcription),
                'word_count': len(transcription.split())
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'فشل التحويل: {str(e)}'
            }
    
    def _download_audio(self, audio_url: str) -> str:
        """
        تحميل الملف الصوتي من S3
        
        Returns:
            str: مسار الملف المؤقت
        """
        
        # استخراج الامتداد من URL
        extension = audio_url.split('.')[-1].lower()
        if extension not in ['mp3', 'wav', 'ogg', 'm4a', 'webm', 'flac']:
            extension = 'mp3'  # default
        
        # إنشاء ملف مؤقت
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=f'.{extension}'
        )
        temp_file_path = temp_file.name
        temp_file.close()
        
        # تحميل الملف
        print(f"📥 Downloading audio from: {audio_url}")
        response = requests.get(audio_url, stream=True, timeout=60)
        response.raise_for_status()
        
        # حفظ الملف
        with open(temp_file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # التحقق من الحجم
        file_size = os.path.getsize(temp_file_path)
        print(f"✅ Downloaded: {file_size / 1024 / 1024:.2f} MB")
        
        return temp_file_path
    
    def _get_audio_encoding(self, file_extension: str) -> speech.RecognitionConfig.AudioEncoding:
        """
        تحديد نوع التشفير بناءً على امتداد الملف
        """
        encoding_map = {
            'mp3': speech.RecognitionConfig.AudioEncoding.MP3,
            'wav': speech.RecognitionConfig.AudioEncoding.LINEAR16,
            'ogg': speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            'flac': speech.RecognitionConfig.AudioEncoding.FLAC,
            'webm': speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            'm4a': speech.RecognitionConfig.AudioEncoding.MP3  # fallback
        }
        
        return encoding_map.get(file_extension, speech.RecognitionConfig.AudioEncoding.MP3)
    
    def _extract_transcription(self, response) -> str:
        """
        استخراج النص من response
        """
        transcription_parts = []
        
        for result in response.results:
            # أخذ أفضل alternative
            if result.alternatives:
                transcription_parts.append(result.alternatives[0].transcript)
        
        return ' '.join(transcription_parts).strip()
    
    def _calculate_confidence(self, response) -> float:
        """
        حساب متوسط الثقة
        """
        confidences = []
        
        for result in response.results:
            if result.alternatives:
                confidences.append(result.alternatives[0].confidence)
        
        if confidences:
            return sum(confidences) / len(confidences)
        else:
            return 0.0
    
    def _cleanup(self, file_path: str):
        """حذف الملف المؤقت"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️  Cleaned up: {file_path}")
        except Exception as e:
            print(f"⚠️  Cleanup failed: {e}")


# ============================================
# 🧪 Testing Function
# ============================================

def test_stt():
    """Test the STT Service"""
    print("\n" + "=" * 60)
    print("🧪 TESTING STT SERVICE (Google Cloud Speech)")
    print("=" * 60)
    
    stt = STTService()
    
    # Test with a sample audio URL (you need to provide a real one)
    print("\n⚠️  To test STT, you need a real audio file URL from S3")
    print("   Example: https://your-bucket.s3.../original/audios/audio.mp3")
    
    audio_url = input("\nEnter audio URL (or press Enter to skip): ").strip()
    
    if audio_url:
        print(f"\n{'=' * 60}")
        print("Testing STT with provided URL")
        print(f"{'=' * 60}")
        
        result = stt.transcribe_audio(audio_url)
        
        if result['success']:
            print(f"\n✅ SUCCESS!")
            print(f"\n📝 Transcription:")
            print(f"   {result['text']}")
            print(f"\n📊 Stats:")
            print(f"   Language: {result.get('language', 'unknown')}")
            print(f"   Confidence: {result.get('confidence', 0):.2%}")
            print(f"   Characters: {result.get('char_count', 0)}")
            print(f"   Words: {result.get('word_count', 0)}")
        else:
            print(f"\n❌ FAILED!")
            print(f"   Error: {result.get('error', 'Unknown error')}")
    else:
        print("\n⏭️  Skipped - No URL provided")
        print("   STT Service is ready to use when you have audio files!")


if __name__ == "__main__":
    test_stt()