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
    
    def process_audio_async(self, file: UploadFile, user_id: Optional[int] = None, source_type_id: int = 6) -> Dict:
        """
        Async Pipeline: Audio → WAV → S3 → Return 200 → Background Processing
        
        Returns immediately after saving file to S3.
        Background job handles: STT → Refiner → Classifier → raw_news
        """
        
        print(f"\n{'='*70}")
        print(f"🎙️ Processing Audio (ASYNC): {file.filename}")
        print(f"{'='*70}")
        
        uploaded_file_id = None
        
        try:
            # Get file info
            original_filename = file.filename
            mime_type = file.content_type or 'audio/mpeg'
            
            # Read file content
            file.file.seek(0)
            audio_bytes = file.file.read()
            file_size = len(audio_bytes)
            
            print(f"\n📋 Original File: {original_filename} ({file_size} bytes)")
            print(f"   MIME Type: {mime_type}")
            
            # ========================================
            # Step 1: Convert to WAV (same as video)
            # ========================================
            print("\n🔄 Step 1: Converting to WAV...")
            wav_file = self._convert_to_wav(audio_bytes, original_filename)
            
            if not wav_file:
                # Save metadata with error before returning
                uploaded_file_id = self._save_metadata_with_error(
                    original_filename=original_filename,
                    file_size=file_size,
                    mime_type=mime_type,
                    error_msg='فشل تحويل الصوت إلى WAV'
                )
                return {'success': False, 'error': 'فشل تحويل الصوت', 'step': 'conversion', 'uploaded_file_id': uploaded_file_id}
            
            # ========================================
            # Step 2: Upload WAV to S3
            # ========================================
            print("\n📤 Step 2: Uploading to S3...")
            upload_result = self.s3_uploader.upload_audio(wav_file.file, wav_file.filename)
            
            if not upload_result['success']:
                uploaded_file_id = self._save_metadata_with_error(
                    original_filename=original_filename,
                    file_size=file_size,
                    mime_type=mime_type,
                    error_msg=f"فشل رفع الملف: {upload_result.get('error')}"
                )
                return {'success': False, 'error': f"فشل رفع الملف: {upload_result.get('error')}", 'step': 'upload', 'uploaded_file_id': uploaded_file_id}
            
            audio_url = upload_result['url']
            print(f"✅ Uploaded: {audio_url}")
            
            # ========================================
            # Step 3: Save metadata (pending status)
            # ========================================
            print("\n💾 Step 3: Saving metadata...")
            
            # Get WAV file size
            wav_file.file.seek(0, 2)  # Seek to end
            wav_size = wav_file.file.tell()
            wav_file.file.seek(0)  # Reset
            
            uploaded_file_id = self._save_metadata(
                original_filename=original_filename,
                stored_filename=upload_result['s3_key'].split('/')[-1],
                file_path=audio_url,
                file_size=wav_size,
                mime_type='audio/wav'
            )
            
            if not uploaded_file_id:
                return {'success': False, 'error': 'فشل حفظ metadata', 'step': 'metadata'}
            
            print(f"   ✅ Saved with ID: {uploaded_file_id}")
            
            # ========================================
            # Step 4: Schedule background processing
            # ========================================
            print("\n⏳ Step 4: Scheduling background processing...")
            self._schedule_background_processing(uploaded_file_id, audio_url, source_type_id)
            
            print(f"\n✅ SUCCESS! Processing scheduled (ID: {uploaded_file_id})")
            print("   The file will be processed in the background.")
            print("   Check /api/media/input/audio/status/{id} for progress.")
            
            return {
                'success': True,
                'news_id': None,  # Not available yet
                'title': None,
                'content': None,
                'category': None,
                'tags': None,
                'uploaded_file_id': uploaded_file_id,
                'audio_url': audio_url,
                'transcription': None,
                'message': 'Processing scheduled. Check status endpoint for updates.'
            }
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            
            # Try to save error if we have uploaded_file_id
            if uploaded_file_id:
                self._update_error(uploaded_file_id, str(e))
            
            return {'success': False, 'error': str(e), 'step': 'unknown', 'uploaded_file_id': uploaded_file_id}
    
    def _schedule_background_processing(self, uploaded_file_id: int, audio_url: str, source_type_id: int):
        """
        Schedule background processing for audio file
        Creates a job in scheduled_tasks for audio_transcription
        """
        try:
            import json
            from datetime import datetime, timezone
            
            # Insert into scheduled_tasks for background processing
            self.cursor.execute("""
                INSERT INTO scheduled_tasks (
                    name, task_type, schedule_pattern, status, 
                    last_status, max_concurrent_runs, created_at
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, NOW()
                )
                RETURNING id
            """, (
                f"Audio Processing #{uploaded_file_id}",
                'audio_transcription',
                '*/1 * * * *',  # Run every minute
                'active',
                'ready',
                1
            ))
            
            job_id = self.cursor.fetchone()[0]
            
            # Save job reference in uploaded_files
            self.cursor.execute("""
                UPDATE uploaded_files
                SET processing_status = 'pending',
                    metadata = metadata || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
            """, (
                json.dumps({
                    'scheduled_job_id': job_id,
                    'audio_url': audio_url,
                    'source_type_id': source_type_id,
                    'scheduled_at': datetime.now(timezone.utc).isoformat()
                }),
                uploaded_file_id
            ))
            
            self.conn.commit()
            print(f"   ✅ Scheduled job #{job_id} for background processing")
            
        except Exception as e:
            print(f"   ⚠️  Failed to schedule background job: {e}")
            self.conn.rollback()
    
    def process_audio(self, file: UploadFile, user_id: Optional[int] = None, source_type_id: int = 6) -> Dict:
        """
        Pipeline: Audio → WAV → S3 → STT → Refiner → Classifier → raw_news
        """
        
        print(f"\n{'='*70}")
        print(f"🎙️ Processing Audio: {file.filename}")
        print(f"{'='*70}")
        
        uploaded_file_id = None
        
        try:
            # Get file info
            original_filename = file.filename
            mime_type = file.content_type or 'audio/mpeg'
            
            # Read file content
            file.file.seek(0)
            audio_bytes = file.file.read()
            file_size = len(audio_bytes)
            
            print(f"\n📋 Original File: {original_filename} ({file_size} bytes)")
            print(f"   MIME Type: {mime_type}")
            
            # ========================================
            # Step 1: Convert to WAV (same as video)
            # ========================================
            print("\n🔄 Step 1: Converting to WAV...")
            wav_file = self._convert_to_wav(audio_bytes, original_filename)
            
            if not wav_file:
                # Save metadata with error before returning
                uploaded_file_id = self._save_metadata_with_error(
                    original_filename=original_filename,
                    file_size=file_size,
                    mime_type=mime_type,
                    error_msg='فشل تحويل الصوت إلى WAV'
                )
                return {'success': False, 'error': 'فشل تحويل الصوت', 'step': 'conversion', 'uploaded_file_id': uploaded_file_id}
            
            # ========================================
            # Step 2: Upload WAV to S3
            # ========================================
            print("\n📤 Step 2: Uploading to S3...")
            upload_result = self.s3_uploader.upload_audio(wav_file.file, wav_file.filename)
            
            if not upload_result['success']:
                uploaded_file_id = self._save_metadata_with_error(
                    original_filename=original_filename,
                    file_size=file_size,
                    mime_type=mime_type,
                    error_msg=f"فشل رفع الملف: {upload_result.get('error')}"
                )
                return {'success': False, 'error': f"فشل رفع الملف: {upload_result.get('error')}", 'step': 'upload', 'uploaded_file_id': uploaded_file_id}
            
            audio_url = upload_result['url']
            print(f"✅ Uploaded: {audio_url}")
            
            # ========================================
            # Step 3: Save metadata
            # ========================================
            print("\n💾 Step 3: Saving metadata...")
            
            # Get WAV file size
            wav_file.file.seek(0, 2)  # Seek to end
            wav_size = wav_file.file.tell()
            wav_file.file.seek(0)  # Reset
            
            uploaded_file_id = self._save_metadata(
                original_filename=original_filename,
                stored_filename=upload_result['s3_key'].split('/')[-1],
                file_path=audio_url,
                file_size=wav_size,
                mime_type='audio/wav'
            )
            
            if not uploaded_file_id:
                return {'success': False, 'error': 'فشل حفظ metadata', 'step': 'metadata'}
            
            print(f"   ✅ Saved with ID: {uploaded_file_id}")
            
            # ========================================
            # Step 4: Transcribe
            # ========================================
            print("\n🎙️ Step 4: Transcribing...")
            stt_result = self.stt_service.transcribe_audio(audio_url)
            
            if not stt_result['success']:
                error_msg = stt_result.get('error', 'STT failed')
                self._update_error(uploaded_file_id, error_msg)
                return {'success': False, 'error': f"فشل STT: {error_msg}", 'step': 'stt', 'uploaded_file_id': uploaded_file_id}
            
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
                return {'success': False, 'error': 'فشل Refiner', 'step': 'refiner', 'uploaded_file_id': uploaded_file_id}
            
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
                return {'success': False, 'error': 'فشل حفظ الخبر', 'step': 'save_news', 'uploaded_file_id': uploaded_file_id}
            
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
            
            # Try to save error if we have uploaded_file_id
            if uploaded_file_id:
                self._update_error(uploaded_file_id, str(e))
            
            return {'success': False, 'error': str(e), 'step': 'unknown', 'uploaded_file_id': uploaded_file_id}
    
    def _convert_to_wav(self, audio_bytes: bytes, filename: str) -> Optional[UploadFile]:
        """Convert audio to WAV (16kHz, mono) - same as video extraction"""
        try:
            # Save to temp file
            file_ext = os.path.splitext(filename)[1].lower()
            if not file_ext:
                file_ext = '.webm'  # default for browser recordings
            
            temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
            temp_input.write(audio_bytes)
            temp_input.close()
            
            print(f"   📁 Temp input: {temp_input.name} ({len(audio_bytes)} bytes)")
            
            # Convert to WAV
            temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_output_path = temp_output.name
            temp_output.close()
            
            try:
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
            except Exception as conv_error:
                print(f"   ❌ MoviePy conversion failed: {conv_error}")
                # Cleanup
                try:
                    os.unlink(temp_input.name)
                    os.unlink(temp_output_path)
                except:
                    pass
                return None
            
            # Read WAV
            with open(temp_output_path, 'rb') as f:
                wav_content = f.read()
            
            # Cleanup
            os.unlink(temp_input.name)
            os.unlink(temp_output_path)
            
            if len(wav_content) < 1000:
                print(f"   ❌ WAV file too small: {len(wav_content)} bytes")
                return None
            
            print(f"   ✅ Converted to WAV: {len(wav_content)} bytes")
            
            return UploadFile(
                filename=os.path.splitext(filename)[0] + '.wav',
                file=BytesIO(wav_content)
            )
            
        except Exception as e:
            print(f"   ❌ Conversion failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _save_metadata(self, original_filename, stored_filename, file_path, file_size, mime_type):
        """Save metadata to uploaded_files"""
        try:
            import json
            query = """
                INSERT INTO uploaded_files (
                    original_filename, stored_filename, file_path, file_size,
                    file_type, mime_type, processing_status, retry_count, metadata, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
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
    
    def _save_metadata_with_error(self, original_filename, file_size, mime_type, error_msg):
        """Save metadata with error status (for early failures)"""
        try:
            import json
            query = """
                INSERT INTO uploaded_files (
                    original_filename, stored_filename, file_path, file_size,
                    file_type, mime_type, processing_status, retry_count, 
                    error_message, metadata, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
                RETURNING id
            """
            self.cursor.execute(query, (
                original_filename, 
                '',  # no stored filename yet
                '',  # no file path yet
                file_size,
                'audio', 
                mime_type, 
                'failed', 
                0, 
                error_msg,
                json.dumps({'early_failure': True})
            ))
            uploaded_file_id = self.cursor.fetchone()[0]
            self.conn.commit()
            print(f"   ⚠️ Saved failed record with ID: {uploaded_file_id}")
            return uploaded_file_id
        except Exception as e:
            print(f"❌ Save metadata with error failed: {e}")
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
            query = """
                UPDATE uploaded_files 
                SET processing_status = 'failed', 
                    error_message = %s,
                    retry_count = COALESCE(retry_count, 0) + 1,
                    updated_at = NOW()
                WHERE id = %s
            """
            self.cursor.execute(query, (error_msg, uploaded_file_id))
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

    # ============================================
    # Helper methods for video_input_processor
    # ============================================

    def _upload_to_s3(self, file: UploadFile, file_type: str = "audio") -> Dict:
        """Upload file to S3"""
        try:
            if file_type == "video":
                result = self.s3_uploader.upload_video(file.file, file.filename)
            else:
                result = self.s3_uploader.upload_audio(file.file, file.filename)
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _save_uploaded_file_metadata(self, original_filename, stored_filename, file_path, file_size, file_type, mime_type):
        """Save metadata to uploaded_files"""
        try:
            import json
            query = """
                INSERT INTO uploaded_files (
                    original_filename, stored_filename, file_path, file_size,
                    file_type, mime_type, processing_status, retry_count, metadata, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
                RETURNING id
            """
            self.cursor.execute(query, (
                original_filename, stored_filename, file_path, file_size,
                file_type, mime_type, 'pending', 0, json.dumps({})
            ))
            uploaded_file_id = self.cursor.fetchone()[0]
            self.conn.commit()
            return uploaded_file_id
        except Exception as e:
            print(f"❌ Save metadata error: {e}")
            self.conn.rollback()
            return None

    def _transcribe_audio(self, audio_url: str) -> Dict:
        """Transcribe audio using STT"""
        try:
            result = self.stt_service.transcribe_audio(audio_url)
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _refine_text(self, text: str) -> Dict:
        """Refine text using NewsRefiner"""
        try:
            result = self.news_refiner.refine_to_news(text)
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _classify_news(self, title: str, content: str):
        """Classify news using Gemini"""
        try:
            category, tags_str, _, _ = classify_with_gemini(title, content)
            return category, tags_str, None, None
        except Exception as e:
            return None, None, None, None

    def _save_to_raw_news(self, title, content, tags, category, uploaded_file_id, original_text, source_type_id):
        """Save to raw_news"""
        try:
            import json
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
                json.dumps({'source_type': 'video'})
            ))
            news_id = self.cursor.fetchone()[0]
            self.conn.commit()
            return news_id
        except Exception as e:
            print(f"❌ Save news error: {e}")
            self.conn.rollback()
            return None

    def _update_uploaded_file_status(self, uploaded_file_id, status):
        """Update status"""
        try:
            query = "UPDATE uploaded_files SET processing_status = %s, processed_at = NOW() WHERE id = %s"
            self.cursor.execute(query, (status, uploaded_file_id))
            self.conn.commit()
        except:
            self.conn.rollback()
