#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎙️ Audio Input Processor V2 - Simplified
معالج إدخال الصوت - نفس طريقة الفيديو بالضبط

Pipeline:
User Audio → Convert to WAV → S3 → STT → Refiner → Classifier → raw_news
"""

import psycopg2
import os
import tempfile
from datetime import datetime
from typing import Dict, Optional
from fastapi import UploadFile
from io import BytesIO
from moviepy.editor import AudioFileClip

# Import our services
from app.utils.s3_uploader import S3Uploader
from app.services.generators.stt_service import STTService
from app.services.processing.news_refiner import NewsRefiner
from app.services.processing.classifier import classify_with_gemini

from settings import DB_CONFIG


class AudioInputProcessorV2:
    """
    معالج الصوت المدخل - يستخدم نفس طريقة الفيديو
    """
    
    def __init__(self):
        """تهيئة المعالج"""
        print("\n" + "=" * 60)
        print("🎙️ Initializing Audio Input Processor V2")
        print("=" * 60)
        
        # Initialize services
        self.s3_uploader = S3Uploader()
        self.stt_service = STTService()
        self.news_refiner = NewsRefiner()
        
        # Database connection
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cursor = self.conn.cursor()
        
        print("✅ All services initialized!")
        print("=" * 60 + "\n")
    
    def process_audio(self, file: UploadFile, user_id: Optional[int] = None, source_type_id: int = 6) -> Dict:
        """
        Pipeline: Audio → WAV → S3 → STT → Refiner → Classifier → raw_news
        """
        
        print(f"\n{'='*70}")
        print(f"🎙️ Processing Audio: {file.filename}")
        print(f"{'='*70}")
        
        try:
            # Get file info
            original_filename = file.filename
            mime_type = file.content_type or 'audio/mpeg'
            
            # Read file content
            file.file.seek(0)
            audio_bytes = file.file.read()
            file_size = len(audio_bytes)
            
            print(f"\n📋 Original File: {original_filename} ({file_size} bytes)")
            
            # ========================================
            # Step 1: Convert to WAV (same as video)
            # ========================================
            print("\n🔄 Step 1: Converting to WAV...")
            wav_file = self._convert_to_wav(audio_bytes, original_filename)
            
            if not wav_file:
                return {'success': False, 'error': 'فشل تحويل الصوت', 'step': 'conversion'}
            
            # ========================================
            # Step 2: Upload WAV to S3
            # ========================================
            print("\n📤 Step 2: Uploading to S3...")
            upload_result = self.s3_uploader.upload_audio(wav_file.file, wav_file.filename)
            
            if not upload_result['success']:
                return {'success': False, 'error': f"فشل رفع الملف: {upload_result.get('error')}", 'step': 'upload'}
            
            audio_url = upload_result['url']
            print(f"✅ Uploaded: {audio_url}")
            
            # ========================================
            # Step 3: Save metadata
            # ========================================
            print("\n💾 Step 3: Saving metadata...")
            uploaded_file_id = self._save_metadata(
                original_filename=original_filename,
                stored_filename=upload_result['s3_key'].split('/')[-1],
                file_path=audio_url,
                file_size=wav_file.file.tell(),
                mime_type='audio/wav'
            )
            
            if not uploaded_file_id:
                return {'success': False, 'error': 'فشل حفظ metadata', 'step': 'metadata'}
            
            # ========================================
            # Step 4: Transcribe
            # ========================================
            print("\n🎙️ Step 4: Transcribing...")
            stt_result = self.stt_service.transcribe_audio(audio_url)
            
            if not stt_result['success']:
                self._update_error(uploaded_file_id, stt_result.get('error', 'STT failed'))
                return {'success': False, 'error': f"فشل STT: {stt_result.get('error')}", 'step': 'stt'}
            
            transcription = stt_result['text']
            print(f"✅ Transcription: {transcription[:100]}...")
            
            # Update transcription
            self._update_transcription(uploaded_file_id, transcription, stt_result.get('confidence', 0))
            
            # ========================================
            # Step 5: Refine
            # ========================================
            print("\n✨ Step 5: Refining...")
            refine_result = self.news_refiner.refine_to_news(transcription)
            
            if not refine_result['success']:
                self._update_error(uploaded_file_id, 'Refiner failed')
                return {'success': False, 'error': 'فشل Refiner', 'step': 'refiner'}
            
            title = refine_result['title']
            content = refine_result['content']
            print(f"✅ Title: {title[:60]}...")
            
            # ========================================
            # Step 6: Classify
            # ========================================
            print("\n🏷️ Step 6: Classifying...")
            category, tags_str, _, _ = classify_with_gemini(title, content)
            print(f"✅ Category: {category}")
            
            # ========================================
            # Step 7: Save news
            # ========================================
            print("\n💾 Step 7: Saving news...")
            news_id = self._save_news(
                title=title,
                content=content,
                tags=tags_str,
                category=category,
                uploaded_file_id=uploaded_file_id,
                original_text=transcription,
                source_type_id=source_type_id
            )
            
            if not news_id:
                self._update_error(uploaded_file_id, 'فشل حفظ الخبر')
                return {'success': False, 'error': 'فشل حفظ الخبر', 'step': 'save_news'}
            
            # Update status
            self._update_status(uploaded_file_id, 'completed')
            
            print(f"\n✅ SUCCESS! News ID: {news_id}")
            
            return {
                'success': True,
                'news_id': news_id,
                'title': title,
                'content': content,
                'category': category,
                'tags': tags_str,
                'uploaded_file_id': uploaded_file_id,
                'audio_url': audio_url,
                'transcription': transcription
            }
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e), 'step': 'unknown'}
    
    def _convert_to_wav(self, audio_bytes: bytes, filename: str) -> Optional[UploadFile]:
        """Convert audio to WAV (16kHz, mono) - same as video extraction"""
        try:
            # Save to temp file
            temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1])
            temp_input.write(audio_bytes)
            temp_input.close()
            
            # Convert to WAV
            temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_output_path = temp_output.name
            temp_output.close()
            
            audio_clip = AudioFileClip(temp_input.name)
            audio_clip.write_audiofile(
                temp_output_path,
                codec="pcm_s16le",
                fps=16000,
                nbytes=2,
                ffmpeg_params=["-ac", "1"],
                logger=None
            )
            audio_clip.close()
            
            # Read WAV
            with open(temp_output_path, 'rb') as f:
                wav_content = f.read()
            
            # Cleanup
            os.unlink(temp_input.name)
            os.unlink(temp_output_path)
            
            print(f"   ✅ Converted to WAV: {len(wav_content)} bytes")
            
            return UploadFile(
                filename=os.path.splitext(filename)[0] + '.wav',
                file=BytesIO(wav_content)
            )
            
        except Exception as e:
            print(f"   ❌ Conversion failed: {e}")
            return None
    
    def _save_metadata(self, original_filename, stored_filename, file_path, file_size, mime_type):
        """Save metadata to uploaded_files"""
        try:
            import json
            query = """
                INSERT INTO uploaded_files (
                    original_filename, stored_filename, file_path, file_size,
                    file_type, mime_type, processing_status, retry_count, metadata, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
                RETURNING id
            """
            self.cursor.execute(query, (
                original_filename, stored_filename, file_path, file_size,
                'audio', mime_type, 'pending', 0, json.dumps({})
            ))
            uploaded_file_id = self.cursor.fetchone()[0]
            self.conn.commit()
            return uploaded_file_id
        except Exception as e:
            print(f"❌ Save metadata error: {e}")
            self.conn.rollback()
            return None
    
    def _update_transcription(self, uploaded_file_id, transcription, confidence):
        """Update transcription"""
        try:
            query = """
                UPDATE uploaded_files
                SET transcription = %s, transcription_confidence = %s,
                    processing_status = 'completed', updated_at = NOW()
                WHERE id = %s
            """
            self.cursor.execute(query, (transcription, confidence, uploaded_file_id))
            self.conn.commit()
        except:
            self.conn.rollback()
    
    def _update_status(self, uploaded_file_id, status):
        """Update status"""
        try:
            query = "UPDATE uploaded_files SET processing_status = %s, processed_at = NOW() WHERE id = %s"
            self.cursor.execute(query, (status, uploaded_file_id))
            self.conn.commit()
        except:
            self.conn.rollback()
    
    def _update_error(self, uploaded_file_id, error_msg):
        """Update with error"""
        try:
            import json
            query = "UPDATE uploaded_files SET processing_status = 'failed', metadata = %s::jsonb WHERE id = %s"
            self.cursor.execute(query, (json.dumps({'error': error_msg}), uploaded_file_id))
            self.conn.commit()
        except:
            self.conn.rollback()
    
    def _save_news(self, title, content, tags, category, uploaded_file_id, original_text, source_type_id):
        """Save to raw_news"""
        try:
            import json
            # Get category_id
            self.cursor.execute("SELECT id FROM categories WHERE name = %s", (category,))
            result = self.cursor.fetchone()
            category_id = result[0] if result else 7
            
            query = """
                INSERT INTO raw_news (
                    title, content_text, tags, category_id, source_id, language_id,
                    uploaded_file_id, original_text, source_type_id, metadata, collected_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
                RETURNING id
            """
            self.cursor.execute(query, (
                title, content, tags, category_id, None, 1,
                uploaded_file_id, original_text, source_type_id,
                json.dumps({'source_type': 'audio'})
            ))
            news_id = self.cursor.fetchone()[0]
            self.conn.commit()
            return news_id
        except Exception as e:
            print(f"❌ Save news error: {e}")
            self.conn.rollback()
            return None
    
    def close(self):
        """Close connections"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
        except:
            pass
