#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎙️ Audio Input Processor
معالج إدخال الصوت - يربط كل الخدمات مع بعض

Pipeline:
User Audio → S3 → STT → Refiner → Classifier → raw_news
"""

import psycopg2
from datetime import datetime
from typing import Dict, Optional
from fastapi import UploadFile

# Import our services
from app.utils.s3_uploader import S3Uploader
from app.services.generators.stt_service import STTService
from app.services.processing.news_refiner import NewsRefiner
from app.services.processing.classifier import classify_with_gemini

from settings import DB_CONFIG


class AudioInputProcessor:
    """
    معالج الصوت المدخل - ينسق كل الخدمات
    
    Usage:
        processor = AudioInputProcessor()
        result = processor.process_audio(audio_file)
        
        Returns:
        {
            'success': True,
            'news_id': 789,
            'title': 'القدس تشهد احتجاجات...',
            'uploaded_file_id': 456,
            'audio_url': 'https://s3...'
        }
    """
    
    def __init__(self):
        """تهيئة المعالج"""
        print("\n" + "=" * 60)
        print("🎙️ Initializing Audio Input Processor")
        print("=" * 60)
        
        # Initialize services
        try:
            self.s3_uploader = S3Uploader()
            print("✅ S3Uploader ready")
        except Exception as e:
            print(f"❌ S3Uploader failed: {e}")
            raise
        
        try:
            self.stt_service = STTService()
            print("✅ STTService ready")
        except Exception as e:
            print(f"❌ STTService failed: {e}")
            raise
        
        try:
            self.news_refiner = NewsRefiner()
            print("✅ NewsRefiner ready")
        except Exception as e:
            print(f"❌ NewsRefiner failed: {e}")
            raise
        
        # Database connection
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print("✅ Database connected")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise
        
        print("=" * 60)
        print("✅ Audio Input Processor initialized successfully!")
        print("=" * 60 + "\n")
    
    def process_audio(self, file: UploadFile, user_id: Optional[int] = None, source_type_id: int = 6) -> Dict:
        """
        Pipeline كامل: Audio → S3 → STT → Refiner → Classifier → raw_news
        
        Args:
            file: ملف الصوت من User (UploadFile)
            user_id: رقم المستخدم (optional)
            source_type_id: 6 = Audio Upload (default), 7 = Voice Record
        
        Returns:
            {
                'success': True/False,
                'news_id': 789,
                'title': '...',
                'uploaded_file_id': 456,
                'audio_url': '...',
                'error': '...' (if failed)
            }
        """
        
        print(f"\n{'='*70}")
        print(f"🎙️ Processing Audio: {file.filename}")
        print(f"{'='*70}")
        
        try:
            # ========================================
            # Get file size first (before upload)
            # ========================================
            try:
                file.file.seek(0, 2)  # Seek to end
                file_size = file.file.tell()
                file.file.seek(0)  # Reset to beginning
            except:
                # Fallback: read content and get length
                content = file.file.read()
                file_size = len(content)
                # Create new BytesIO with content
                from io import BytesIO
                file.file = BytesIO(content)
            
            # ========================================
            # Step 1: رفع الملف على S3
            # ========================================
            print("\n📤 Step 1: Uploading to S3...")
            upload_result = self._upload_to_s3(file)
            
            if not upload_result['success']:
                return {
                    'success': False,
                    'error': f"فشل رفع الملف: {upload_result.get('error')}",
                    'step': 'upload'
                }
            
            audio_url = upload_result['url']
            s3_key = upload_result['s3_key']
            
            # Extract stored filename from s3_key
            stored_filename = s3_key.split('/')[-1]
            
            # Detect mime_type from filename
            mime_type = self._detect_mime_type(file.filename)
            
            print(f"✅ Uploaded: {audio_url}")
            
            # ========================================
            # Step 2: حفظ metadata في uploaded_files
            # ========================================
            print("\n💾 Step 2: Saving metadata...")
            uploaded_file_id = self._save_uploaded_file_metadata(
                original_filename=file.filename,
                stored_filename=stored_filename,
               file_path=audio_url,
                file_size=file_size,
                file_type='audio',
                mime_type=mime_type
            )
            
            if not uploaded_file_id:
                return {
                    'success': False,
                    'error': 'فشل حفظ metadata',
                    'step': 'metadata'
                }
            
            print(f"✅ Saved metadata: uploaded_file_id = {uploaded_file_id}")
            
            # ========================================
            # Step 3: تحويل الصوت إلى نص (STT)
            # ========================================
            print("\n🎙️ Step 3: Speech-to-Text...")
            stt_result = self._transcribe_audio(audio_url, mime_type) 
            
            if not stt_result['success']:
                # Update status
                self._update_uploaded_file_status(uploaded_file_id, 'failed')
                return {
                    'success': False,
                    'error': f"فشل STT: {stt_result.get('error')}",
                    'step': 'stt',
                    'uploaded_file_id': uploaded_file_id
                }
            
            transcription = stt_result['text']
            confidence = stt_result.get('confidence', 0.0)
            print(f"✅ Transcription: {transcription[:100]}...")
            
            # Update uploaded_files
            self._update_transcription(uploaded_file_id, transcription, confidence)
            
            # ========================================
            # Step 4: تحسين النص (Refiner)
            # ========================================
            print("\n✨ Step 4: Refining text...")
            refine_result = self._refine_text(transcription)
            
            if not refine_result['success']:
                self._update_uploaded_file_status(uploaded_file_id, 'failed')
                return {
                    'success': False,
                    'error': f"فشل Refiner: {refine_result.get('error')}",
                    'step': 'refiner',
                    'uploaded_file_id': uploaded_file_id
                }
            
            title = refine_result['title']
            content = refine_result['content']
            print(f"✅ Title: {title[:60]}...")
            print(f"✅ Content: {len(content)} chars")
            
            # ========================================
            # Step 5: تصنيف الخبر (Classifier)
            # ========================================
            print("\n🏷️ Step 5: Classifying...")
            category, tags_str, tags_list, classify_success = self._classify_news(title, content)
            
            if not classify_success:
                print("⚠️  Classification failed, using defaults")
                category = 'عام'  # default
                tags_str = ''
                tags_list = []
            
            print(f"✅ Category: {category}")
            print(f"✅ Tags: {tags_str}")
            
            # ========================================
            # Step 6: حفظ الخبر في raw_news
            # ========================================
            print("\n💾 Step 6: Saving news to database...")
            news_id = self._save_to_raw_news(
                title=title,
                content=content,
                tags=tags_str,
                category=category,
                uploaded_file_id=uploaded_file_id,
                original_text=transcription,
                source_type_id=source_type_id  # 6 or 7
            )
            
            if not news_id:
                self._update_uploaded_file_status(uploaded_file_id, 'failed')
                return {
                    'success': False,
                    'error': 'فشل حفظ الخبر',
                    'step': 'save_news',
                    'uploaded_file_id': uploaded_file_id
                }
            
            print(f"✅ News saved: news_id = {news_id}")
            
            # Update uploaded_files status
            self._update_uploaded_file_status(uploaded_file_id, 'completed')
            
            # ========================================
            # النتيجة النهائية
            # ========================================
            print(f"\n{'='*70}")
            print(f"✅ SUCCESS! Audio processed completely")
            print(f"{'='*70}")
            print(f"📰 News ID: {news_id}")
            print(f"📁 Upload ID: {uploaded_file_id}")
            print(f"🎙️ Audio URL: {audio_url}")
            print(f"{'='*70}\n")
            
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
            print(f"\n❌ ERROR in process_audio: {e}")
            return {
                'success': False,
                'error': str(e),
                'step': 'unknown'
            }
    
    # ============================================
    # Helper Methods
    # ============================================
  

    def _upload_to_s3(self, file: UploadFile, file_type: str = "audio") -> Dict:
        try:
            if file_type == "video":
                return self.s3_uploader.upload_video(file.file, file.filename)
            else:
                return self.s3_uploader.upload_audio(file.file, file.filename)
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    
    def _save_uploaded_file_metadata(
        self, 
        original_filename: str,
        stored_filename: str,
        file_path: str,
        file_size: int,
        file_type: str,
        mime_type: str
    ) -> Optional[int]:
        """
        حفظ metadata في uploaded_files table
        
        Args:
            original_filename: اسم الملف الأصلي (من User)
            stored_filename: اسم الملف في S3
            file_path: S3 key الكامل
            file_size: حجم الملف بالـ bytes
            file_type: نوع الملف (audio)
            mime_type: نوع الـ MIME (audio/mpeg, audio/wav, etc.)
        
        Returns:
            uploaded_file_id (int) or None
        """
        try:
            import json
            
            query = """
                INSERT INTO uploaded_files (
                    original_filename,
                    stored_filename,
                    file_path,
                    file_size,
                    file_type,
                    mime_type,
                    processing_status,
                    retry_count,
                    metadata,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
                RETURNING id
            """
            
            self.cursor.execute(query, (
                original_filename,
                stored_filename,
                file_path,
                file_size,
                file_type,
                mime_type,
                'pending',
                0,  # retry_count
                json.dumps({})  # Convert dict to JSON string
            ))
            
            uploaded_file_id = self.cursor.fetchone()[0]
            self.conn.commit()
            
            return uploaded_file_id
            
        except Exception as e:
            print(f"❌ Error saving metadata: {e}")
            self.conn.rollback()
            return None
    
    def _update_transcription(self, uploaded_file_id: int, transcription: str, confidence: float = 0.0):
        """تحديث الـ transcription في uploaded_files"""
        try:
            query = """
                UPDATE uploaded_files
                SET transcription = %s,
                    transcription_confidence = %s,
                    processing_status = 'completed',
                    updated_at = NOW()
                WHERE id = %s
            """
            
            self.cursor.execute(query, (transcription, confidence, uploaded_file_id))
            self.conn.commit()
            
        except Exception as e:
            print(f"⚠️  Error updating transcription: {e}")
            self.conn.rollback()
    
    def _update_uploaded_file_status(self, uploaded_file_id: int, status: str):
        """تحديث حالة المعالجة"""
        try:
            query = """
                UPDATE uploaded_files
                SET processing_status = %s,
                    processed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """
            
            self.cursor.execute(query, (status, uploaded_file_id))
            self.conn.commit()
            
        except Exception as e:
            print(f"⚠️  Error updating status: {e}")
            self.conn.rollback()
    
    def _transcribe_audio(self, audio_url: str, mime_type: str = None) -> Dict:
        """
        تحويل الصوت إلى نص - مع دعم WebM
        """
        
        try:
            # Check if needs conversion
            if mime_type and self.audio_converter.needs_conversion(mime_type):
                print(f"   🔄 Converting {mime_type} to WAV...")
                
                # Convert
                wav_data = self.audio_converter.convert_to_wav(audio_url)
                
                if not wav_data:
                    return {'success': False, 'error': 'Conversion failed'}
                
                # Upload converted
                from fastapi import UploadFile
                wav_file = UploadFile(filename='converted.wav', file=wav_data)
                upload_result = self._upload_to_s3(wav_file, file_type='audio')
                
                # Use converted URL
                audio_url = upload_result['url']
            
            # Transcribe (original or converted)
            result = self.stt_service.transcribe_audio(audio_url)
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _refine_text(self, raw_text: str) -> Dict:
        """تحسين النص العامي إلى خبر احترافي"""
        try:
            result = self.news_refiner.refine_to_news(raw_text)
            return result
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _classify_news(self, title: str, content: str) -> tuple:
        """
        تصنيف الخبر
        
        Returns:
            (category, tags_str, tags_list, success)
        """
        try:
            category, tags_str, tags_list, success = classify_with_gemini(title, content)
            return category, tags_str, tags_list, success
        except Exception as e:
            print(f"⚠️  Classifier error: {e}")
            return 'عام', '', [], False
    
    def _save_to_raw_news(
        self,
        title: str,
        content: str,
        tags: str,
        category: str,
        uploaded_file_id: int,
        original_text: str,
        source_type_id: int = 6  # 6=Audio Upload, 7=Voice Record
    ) -> Optional[int]:
        """
        حفظ الخبر في raw_news table
        
        Args:
            title: عنوان الخبر
            content: محتوى الخبر
            tags: الكلمات المفتاحية
            category: اسم التصنيف (مثل "سياسة")
            uploaded_file_id: رقم الملف المرفوع
            original_text: النص الأصلي (العامي)
            source_type_id: 6 للـ Audio Upload، 7 للـ Voice Record
        
        Returns:
            news_id (int) or None
        """
        try:
            import json
            
            # Get category_id from category name
            category_id = self._get_category_id(category)
            
            # Language (Arabic = 1)
            language_id = 1
            
            # Create metadata with audio info
            metadata = {
                'source_type': 'audio_upload' if source_type_id == 6 else 'voice_record',
                'uploaded_file_id': uploaded_file_id,
                'has_transcription': True,
                'original_text_length': len(original_text)
            }
            
            # Insert news
            query = """
                INSERT INTO raw_news (
                    title,
                    content_text,
                    tags,
                    category_id,
                    source_id,
                    language_id,
                    uploaded_file_id,
                    original_text,
                    source_type_id,
                    metadata,
                    collected_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
                RETURNING id
            """
            
            self.cursor.execute(query, (
                title,
                content,
                tags,
                category_id,
                None,  # source_id = NULL (مش من RSS)
                language_id,
                uploaded_file_id,
                original_text,
                source_type_id,  # 6 or 7
                json.dumps(metadata)  # metadata as JSON
            ))
            
            news_id = self.cursor.fetchone()[0]
            self.conn.commit()
            
            return news_id
            
        except Exception as e:
            print(f"❌ Error saving news: {e}")
            self.conn.rollback()
            return None
    
    def _get_category_id(self, category_name: str) -> int:
        """الحصول على category_id من الاسم"""
        try:
            query = "SELECT id FROM categories WHERE name = %s"
            self.cursor.execute(query, (category_name,))
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
            else:
                # Default category (عام = 7)
                return 7
                
        except Exception as e:
            print(f"⚠️  Error getting category_id: {e}")
            return 7  # default
    
    def _detect_mime_type(self, filename: str) -> str:
        """
        تحديد mime_type من اسم الملف
        """
        extension = filename.lower().split('.')[-1]
        
        mime_types = {
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'ogg': 'audio/ogg',
            'webm': 'audio/webm',
            'm4a': 'audio/mp4',
            'flac': 'audio/flac',
            'aac': 'audio/aac',
            'opus': 'audio/opus'
        }
        
        return mime_types.get(extension, 'audio/mpeg')  # default: audio/mpeg
    
    def close(self):
        """إغلاق الاتصالات"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
            print("✅ Database connection closed")
        except Exception as e:
            print(f"⚠️  Error closing: {e}")


# ============================================
# 🧪 Testing (when run directly)
# ============================================

if __name__ == "__main__":
    print("Audio Input Processor")
    print("To test, import and use with FastAPI UploadFile")