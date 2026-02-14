#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎙️ STT Service (Speech-to-Text)
تحويل الصوت إلى نص باستخدام Google Cloud Speech-to-Text
يدعم الملفات الطويلة (> 1 دقيقة) والـ WebM format
"""

import os
import sys
import subprocess
import tempfile
from typing import Optional, Dict
import requests

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
    يدعم الملفات الطويلة وتحويل الـ WebM تلقائياً
    """
    
    def __init__(self):
        """Initialize Google Cloud Speech-to-Text"""
        try:
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
                
            else:
                raise ValueError("Google credentials not found")
            
        except Exception as e:
            print(f"❌ STTService initialization failed: {e}")
            raise
    
    def transcribe_audio(self, audio_url: str, max_retries: int = 3) -> Dict:
        """
        تحويل ملف صوتي إلى نص
        يدعم الملفات الطويلة وتحويل الـ WebM تلقائياً
        """
        
        if not audio_url:
            return {'success': False, 'error': 'رابط الصوت فارغ'}
        
        print(f"🎙️ Transcribing audio: {audio_url}")
        
        audio_file_path = None
        wav_file_path = None
        
        try:
            # ========================================
            # Step 1: Download audio
            # ========================================
            audio_file_path = self._download_audio(audio_url)
            print(f"✅ Audio downloaded: {audio_file_path}")
            
            # ========================================
            # Step 2: Convert to WAV if needed
            # ========================================
            file_extension = audio_url.split('.')[-1].lower()
            
            if file_extension in ['webm', 'ogg', 'm4a']:
                print(f"🔄 Converting {file_extension} to WAV...")
                wav_file_path = self._convert_to_wav(audio_file_path)
                if wav_file_path:
                    print(f"✅ Converted to WAV: {wav_file_path}")
                    working_file = wav_file_path
                    encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16
                    sample_rate = 16000
                else:
                    print(f"⚠️ Conversion failed, trying original format")
                    working_file = audio_file_path
                    encoding = self._get_audio_encoding(file_extension)
                    sample_rate = None
            else:
                working_file = audio_file_path
                encoding = self._get_audio_encoding(file_extension)
                sample_rate = None
            
            # ========================================
            # Step 3: Read audio content
            # ========================================
            with open(working_file, 'rb') as f:
                audio_content = f.read()
            
            file_size_mb = len(audio_content) / (1024 * 1024)
            print(f"📊 Audio size: {file_size_mb:.2f} MB")
            
            # ========================================
            # Step 4: Transcribe with retries
            # ========================================
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    print(f"🤖 Transcribing... (attempt {attempt + 1}/{max_retries})")
                    
                    # Build config
                    config_params = {
                        'encoding': encoding,
                        'language_code': 'ar-SA',
                        'alternative_language_codes': ['ar-EG', 'ar-JO', 'ar-PS'],
                        'enable_automatic_punctuation': True,
                        'model': 'default',
                    }
                    
                    if sample_rate:
                        config_params['sample_rate_hertz'] = sample_rate
                    
                    config = speech.RecognitionConfig(**config_params)
                    audio = speech.RecognitionAudio(content=audio_content)
                    
                    # Try sync first, then async for long audio
                    print(f"   📤 Sending to Google Cloud Speech API...")
                    
                    try:
                        response = self.client.recognize(config=config, audio=audio)
                    except Exception as sync_error:
                        error_str = str(sync_error)
                        if 'Sync input too long' in error_str or 'audio too long' in error_str.lower():
                            print(f"   ⏳ Audio too long, using async recognition...")
                            response = self._transcribe_long_audio(audio_content, config)
                        else:
                            raise sync_error
                    
                    # Extract transcription
                    transcription = self._extract_transcription(response)
                    
                    if not transcription or len(transcription) < 10:
                        print(f"⚠️ Transcription too short: {len(transcription) if transcription else 0} chars")
                        if attempt < max_retries - 1:
                            continue
                        else:
                            return {'success': False, 'error': 'النص المستخرج قصير جداً أو فارغ'}
                    
                    confidence = self._calculate_confidence(response)
                    
                    print(f"✅ Transcription successful: {len(transcription)} chars")
                    print(f"   Preview: {transcription[:100]}...")
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
                    last_error = str(e)
                    print(f"❌ Attempt {attempt + 1} failed: {e}")
                    
                    # Don't retry for certain errors
                    if 'sample rate' in last_error.lower():
                        break
                    
                    continue
            
            return {
                'success': False,
                'error': f'فشل التحويل بعد {max_retries} محاولات: {last_error}'
            }
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return {'success': False, 'error': str(e)}
            
        finally:
            # Cleanup temp files
            self._cleanup(audio_file_path)
            self._cleanup(wav_file_path)
    
    def _transcribe_long_audio(self, audio_content: bytes, config: speech.RecognitionConfig):
        """
        Transcribe long audio using async recognition
        """
        audio = speech.RecognitionAudio(content=audio_content)
        
        operation = self.client.long_running_recognize(config=config, audio=audio)
        print(f"   ⏳ Waiting for long audio transcription...")
        
        # Wait for completion (timeout 5 minutes)
        response = operation.result(timeout=300)
        
        return response
    
    def _convert_to_wav(self, input_path: str) -> Optional[str]:
        """
        Convert audio to WAV format (16kHz, mono)
        """
        try:
            # Create output path
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix='.wav').name
            
            # Try ffmpeg conversion
            cmd = [
                'ffmpeg', '-y', '-i', input_path,
                '-ar', '16000',      # 16kHz sample rate
                '-ac', '1',          # mono
                '-acodec', 'pcm_s16le',  # LINEAR16
                output_path
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                timeout=60,
                text=True
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                if file_size > 1000:  # At least 1KB
                    return output_path
            
            # Cleanup failed output
            self._cleanup(output_path)
            return None
            
        except Exception as e:
            print(f"   ⚠️ FFmpeg conversion failed: {e}")
            return None
    
    def _download_audio(self, audio_url: str) -> str:
        """Download audio file from URL"""
        extension = audio_url.split('.')[-1].lower()
        if extension not in ['mp3', 'wav', 'ogg', 'm4a', 'webm', 'flac']:
            extension = 'mp3'
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{extension}')
        temp_file_path = temp_file.name
        temp_file.close()
        
        print(f"📥 Downloading audio from: {audio_url}")
        response = requests.get(audio_url, stream=True, timeout=60)
        response.raise_for_status()
        
        with open(temp_file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        file_size = os.path.getsize(temp_file_path)
        print(f"✅ Downloaded: {file_size / 1024 / 1024:.2f} MB")
        
        return temp_file_path
    
    def _get_audio_encoding(self, file_extension: str) -> speech.RecognitionConfig.AudioEncoding:
        """Get audio encoding based on file extension"""
        encoding_map = {
            'mp3': speech.RecognitionConfig.AudioEncoding.MP3,
            'wav': speech.RecognitionConfig.AudioEncoding.LINEAR16,
            'ogg': speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            'flac': speech.RecognitionConfig.AudioEncoding.FLAC,
            'webm': speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            'm4a': speech.RecognitionConfig.AudioEncoding.MP3
        }
        return encoding_map.get(file_extension, speech.RecognitionConfig.AudioEncoding.MP3)
    
    def _extract_transcription(self, response) -> str:
        """Extract transcription text from response"""
        parts = []
        for result in response.results:
            if result.alternatives:
                parts.append(result.alternatives[0].transcript)
        return ' '.join(parts).strip()
    
    def _calculate_confidence(self, response) -> float:
        """Calculate average confidence"""
        confidences = []
        for result in response.results:
            if result.alternatives:
                confidences.append(result.alternatives[0].confidence)
        return sum(confidences) / len(confidences) if confidences else 0.0
    
    def _cleanup(self, file_path: str):
        """Delete temp file"""
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️ Cleaned up: {file_path}")
        except Exception as e:
            print(f"⚠️ Cleanup failed: {e}")
