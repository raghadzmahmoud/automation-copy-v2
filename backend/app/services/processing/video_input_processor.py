#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎥 Video Input Processor
معالج الفيديو - يرفع الفيديو، يستخرج الصوت، ويحفظ metadata
"""

import os
import tempfile
from typing import Dict, Optional
from fastapi import UploadFile
from moviepy.editor import VideoFileClip
from io import BytesIO
from app.services.processing.audio_input_processor import AudioInputProcessor

class VideoInputProcessor:
    def __init__(self):
        print("\n" + "=" * 60)
        print("🎥 Initializing Video Input Processor")
        print("=" * 60)
        try:
            self.audio_processor = AudioInputProcessor()
            print("✅ AudioInputProcessor ready")
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            raise

    def process_video(self, file: UploadFile, user_id: Optional[int] = None, source_type_id: int = 8) -> Dict:
        print(f"\n{'='*70}")
        print(f"🎥 Processing Video: {file.filename}")
        print(f"{'='*70}")

        try:
            # --- 1. تحضير البيانات مسبقاً قبل الرفع (هام جداً) ---
            original_filename = file.filename
            mime_type = file.content_type or 'video/mp4'
            
            # قراءة المحتوى بالكامل في الذاكرة لتجنب خطأ I/O بعد الرفع
            file.file.seek(0)
            video_bytes = file.file.read()
            video_size = len(video_bytes)
            
            # إعادة بناء الـ Stream للرفع لـ S3
            file.file = BytesIO(video_bytes)

            # --- 2. رفع الفيديو الأصلي لـ S3 ---
            print("\n📤 Step 1: Uploading Original Video to S3...")
            video_upload_result = self.audio_processor._upload_to_s3(
                file,
                file_type="video"
            )
                        
            if not video_upload_result['success']:
                return {'success': False, 'error': f"فشل رفع الفيديو: {video_upload_result.get('error')}"}
            
            video_url = video_upload_result['url']
            video_s3_key = video_upload_result['s3_key']

            # --- 3. حفظ بيانات الفيديو في الداتابيز ---
            print("💾 Step 2: Saving Video Metadata...")
            video_file_id = self.audio_processor._save_uploaded_file_metadata(
                original_filename=original_filename,
                stored_filename=video_s3_key.split('/')[-1],
                file_path=video_url,                file_size=video_size,
                file_type='video',
                mime_type=mime_type
            )

            # --- 4. استخراج الصوت من الفيديو ---
            print("\n🎵 Step 3: Extracting audio for processing...")
            # نستخدم نسخة الذاكرة (video_bytes) للاستخراج
            temp_upload_file = UploadFile(filename=original_filename, file=BytesIO(video_bytes))
            audio_upload_file = self._extract_audio_from_video(temp_upload_file)
            
            if not audio_upload_file:
                return {'success': False, 'error': 'فشل استخراج الصوت من الفيديو'}

            # --- 5. معالجة الصوت (السايكل الكاملة) ---
            print("🎙️ Step 4: Transcribing and Refining content...")
            # رفع الصوت مؤقتاً للحصول على URL للـ STT
            audio_tmp_upload = self.audio_processor._upload_to_s3(audio_upload_file)
            stt_result = self.audio_processor._transcribe_audio(audio_tmp_upload['url'])
            
            if not stt_result['success']:
                return {'success': False, 'error': 'فشل عملية تحويل الصوت لنص (STT)'}

            transcription = stt_result['text']

            # تحسين النص وتصنيفه
            refine_result = self.audio_processor._refine_text(transcription)
            category, tags_str, _, _ = self.audio_processor._classify_news(
                refine_result['title'], refine_result['content']
            )

            # --- 6. حفظ الخبر النهائي وربطه بالفيديو ---
            print("\n💾 Step 5: Saving news and linking to video...")
            news_id = self.audio_processor._save_to_raw_news(
                title=refine_result['title'],
                content=refine_result['content'],
                tags=tags_str,
                category=category,
                uploaded_file_id=video_file_id, 
                original_text=transcription,
                source_type_id=source_type_id
            )

            # تحديث الحالة
            self.audio_processor._update_uploaded_file_status(video_file_id, 'completed')
            self.audio_processor._update_transcription(video_file_id, transcription, stt_result.get('confidence', 0))

            return {
                'success': True,
                'news_id': news_id,
                'video_url': video_url,
                'title': refine_result['title'],
                'transcription': transcription
            }

        except Exception as e:
            print(f"❌ Critical Error in Video Processing: {e}")
            return {'success': False, 'error': str(e)}

    def _extract_audio_from_video(self, video_file: UploadFile) -> Optional[UploadFile]:
        try:
            video_file.file.seek(0)

            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_video:
                temp_video.write(video_file.file.read())
                temp_video_path = temp_video.name

            video_clip = VideoFileClip(temp_video_path)

            if not video_clip.audio:
                video_clip.close()
                os.unlink(temp_video_path)
                return None

            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
                temp_audio_path = temp_audio.name
                video_clip.audio.write_audiofile(
                    temp_audio_path,
                    codec="pcm_s16le",     # LINEAR16
                    fps=16000,             # sample rate
                    nbytes=2,
                    ffmpeg_params=["-ac", "1"],  # mono
                    logger=None
                )

            video_clip.close()
            os.unlink(temp_video_path)

            with open(temp_audio_path, 'rb') as f:
                audio_content = f.read()

            audio_file = UploadFile(
                filename=f"extracted_{os.path.splitext(video_file.filename)[0]}.wav",
                file=BytesIO(audio_content)
            )

            os.unlink(temp_audio_path)
            return audio_file

        except Exception as e:
            print(f"❌ Extraction Error: {e}")
            return None

    def close(self):
        self.audio_processor.close()