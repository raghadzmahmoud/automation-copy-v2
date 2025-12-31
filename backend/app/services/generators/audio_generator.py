#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎙️ Audio Generator Service
توليد صوت للأخبار باستخدام Google Text-to-Speech

📁 S3 Path: generated/audios/
"""

import os
import sys
import time
import psycopg2
from datetime import datetime, timezone
from typing import Dict, Optional
from dataclasses import dataclass
import boto3

from settings import DB_CONFIG

# Google Text-to-Speech
try:
    from google.cloud import texttospeech
except ImportError:
    print("❌ google-cloud-texttospeech not installed")
    print("   Run: pip install google-cloud-texttospeech")
    sys.exit(1)


@dataclass
class AudioGenerationResult:
    """نتيجة توليد الصوت"""
    success: bool
    audio_url: Optional[str] = None
    s3_path: Optional[str] = None
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None


class AudioGenerator:
    """مولد الصوت للتقارير"""
    
    def __init__(self):
        """تهيئة المولد"""
        self.conn = None
        self.cursor = None
        
        # اتصال قاعدة البيانات
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print("✅ AudioGenerator initialized (Database)")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise
        
        # تهيئة S3 Client
        try:
            self.s3_client = boto3.client('s3')
            self.bucket_name = os.getenv('S3_BUCKET_NAME', 'media-automation-bucket')
            
            # ✅ المسار الصحيح: generated/audios/
            self.s3_folder = os.getenv('S3_GENERATED_AUDIOS_FOLDER', 'generated/audios/')
            
            print(f"✅ S3 client initialized (Bucket: {self.bucket_name})")
            print(f"   📁 Upload folder: {self.s3_folder}")
        except Exception as e:
            print(f"❌ S3 client initialization failed: {e}")
            raise
        
        # تهيئة Google Text-to-Speech Client
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
                self.tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
                print(f"✅ Google TTS client initialized (from JSON env var)")
                
            elif credentials_path and os.path.exists(credentials_path):
                self.tts_client = texttospeech.TextToSpeechClient()
                print(f"✅ Google TTS client initialized (from file)")
                print(f"   🔑 Using credentials: {credentials_path}")
                
            else:
                raise ValueError(
                    "Google credentials not found. Set one of:\n"
                    "  - GOOGLE_CREDENTIALS_JSON (for Render/production)\n"
                    "  - GOOGLE_APPLICATION_CREDENTIALS (for local development)"
                )
            
        except Exception as e:
            print(f"❌ Google TTS client failed: {e}")
            raise
        
        # Content Type ID for Generated Audio
        self.content_type_id = 7
    
    def generate_for_report(
        self,
        report_id: int,
        force_update: bool = False
    ) -> AudioGenerationResult:
        """توليد صوت لتقرير واحد"""
        print(f"\n{'='*70}")
        print(f"🎙️ Generating Audio for Report #{report_id}")
        print(f"{'='*70}")
        
        # جلب التقرير
        report = self._fetch_report(report_id)
        if not report:
            return AudioGenerationResult(
                success=False,
                error_message="Report not found"
            )
        
        print(f"📰 Report: {report['title'][:60]}...")
        
        # فحص وجود صوت مسبقاً
        existing_audio = self._get_existing_audio(report_id)
        
        if existing_audio and not force_update:
            print(f"⏭️  Audio already exists (ID: {existing_audio['id']})")
            return AudioGenerationResult(
                success=True,
                audio_url=existing_audio['file_url'],
                s3_path=existing_audio['file_url']
            )
        
        # إنشاء نص بصيغة إذاعية
        broadcast_text = self._create_broadcast_text(report)
        print(f"📝 Broadcast text created ({len(broadcast_text)} chars)")
        
        # توليد الصوت ورفعه على S3
        generation_result = self._generate_and_upload_audio(
            text=broadcast_text,
            report_id=report_id
        )
        
        if not generation_result.success:
            print(f"❌ Audio generation failed: {generation_result.error_message}")
            return generation_result
        
        print(f"✅ Audio generated and uploaded successfully")
        s3_url = generation_result.audio_url
        
        # حفظ في قاعدة البيانات
        if existing_audio:
            success = self._update_audio_record(
                content_id=existing_audio['id'],
                report_id=report_id,
                s3_url=s3_url,
                text_content=broadcast_text
            )
            action = "Updated"
        else:
            success = self._save_audio_record(
                report_id=report_id,
                s3_url=s3_url,
                text_content=broadcast_text
            )
            action = "Created"
        
        if success:
            print(f"✅ {action} database record")
            return AudioGenerationResult(
                success=True,
                audio_url=s3_url,
                s3_path=s3_url
            )
        else:
            return AudioGenerationResult(
                success=False,
                error_message=f"Failed to {action.lower()} database record"
            )
    
    def generate_for_all_reports(
        self,
        force_update: bool = False,
        limit: int = 10
    ) -> Dict:
        """توليد صوت لكل التقارير"""
        print(f"\n{'='*70}")
        print(f"🎙️ Generating Audio for All Reports")
        print(f"{'='*70}")
        
        if force_update:
            reports = self._fetch_recent_reports(limit)
        else:
            reports = self._fetch_reports_without_audio(limit)
        
        if not reports:
            print("📭 No reports need audio generation")
            return {
                'total_reports': 0,
                'success': 0,
                'failed': 0,
                'skipped': 0
            }
        
        print(f"📋 Found {len(reports)} reports to process")
        
        stats = {
            'total_reports': len(reports),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'updated': 0
        }
        
        for i, report in enumerate(reports, 1):
            print(f"\n[{i}/{len(reports)}] Report #{report['id']}")
            
            result = self.generate_for_report(
                report_id=report['id'],
                force_update=force_update
            )
            
            if result.success:
                if force_update:
                    stats['updated'] += 1
                else:
                    stats['success'] += 1
            else:
                stats['failed'] += 1
            
            # تأخير بين الطلبات
            if i < len(reports):
                print("   ⏳ Waiting 5 seconds...")
                time.sleep(5)
        
        print(f"\n{'='*70}")
        print(f"📊 Final Results:")
        print(f"   • Reports: {stats['total_reports']}")
        print(f"   • Success: {stats['success']}")
        print(f"   • Updated: {stats['updated']}")
        print(f"   • Failed: {stats['failed']}")
        print(f"{'='*70}")
        
        return stats
    
    def _create_broadcast_text(self, report: Dict) -> str:
        """إنشاء نص بصيغة إذاعية"""
        title = report['title']
        content = report['content']
        
        broadcast = f"""
{title}

{content}
        """
        
        return broadcast.strip()
    
    def _generate_and_upload_audio(
        self,
        text: str,
        report_id: int,
        retries: int = 3
    ) -> AudioGenerationResult:
        """توليد الصوت ورفعه على S3"""
        
        for attempt in range(retries):
            try:
                print(f"   🎙️ Generating audio (attempt {attempt + 1}/{retries})...")
                
                input_text = texttospeech.SynthesisInput(text=text)
                
                voice = texttospeech.VoiceSelectionParams(
                    language_code="ar-XA",
                    name="ar-XA-Chirp3-HD-Achird",
                    ssml_gender=texttospeech.SsmlVoiceGender.MALE
                )
                
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3
                )
                
                response = self.tts_client.synthesize_speech(
                    input=input_text,
                    voice=voice,
                    audio_config=audio_config
                )
                
                audio_bytes = response.audio_content
                print(f"   ✅ Audio generated ({len(audio_bytes):,} bytes)")
                
                # ✅ Upload to S3: generated/audios/
                timestamp = int(time.time())
                file_name = f"report_{report_id}_{timestamp}.mp3"
                s3_key = f"{self.s3_folder}{file_name}"
                
                print(f"   📤 Uploading to S3: {s3_key}")
                
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=audio_bytes,
                    ContentType='audio/mpeg'
                )
                
                s3_url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_key}"
                print(f"   ✅ Uploaded successfully: {s3_url}")
                
                return AudioGenerationResult(
                    success=True,
                    audio_url=s3_url
                )
                
            except Exception as e:
                error_msg = str(e)
                print(f"   ⚠️  Error: {error_msg[:300]}")
                
                if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
                    if attempt < retries - 1:
                        wait_time = 60
                        print(f"   ⏳ Rate limit hit. Waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        return AudioGenerationResult(
                            success=False,
                            error_message="Rate limit exceeded"
                        )
                
                if attempt < retries - 1:
                    print(f"   🔄 Retrying in 10 seconds...")
                    time.sleep(10)
                    continue
                else:
                    return AudioGenerationResult(
                        success=False,
                        error_message=f"Generation failed: {error_msg[:300]}"
                    )
        
        return AudioGenerationResult(
            success=False,
            error_message="Max retries exceeded"
        )
    
    def _fetch_report(self, report_id: int) -> Optional[Dict]:
        """جلب تقرير"""
        try:
            self.cursor.execute("""
                SELECT id, title, content, updated_at
                FROM generated_report
                WHERE id = %s
            """, (report_id,))
            
            row = self.cursor.fetchone()
            if not row:
                return None
            
            return {
                'id': row[0],
                'title': row[1],
                'content': row[2],
                'updated_at': row[3]
            }
        except Exception as e:
            print(f"   ❌ Error fetching report: {e}")
            return None
    
    def _fetch_reports_without_audio(self, limit: int = 10):
        """جلب التقارير بدون صوت"""
        try:
            query = """
                SELECT 
                    gr.id,
                    gr.title,
                    gr.content,
                    gr.updated_at
                FROM generated_report gr
                WHERE gr.status = 'draft'
                    AND NOT EXISTS (
                        SELECT 1
                        FROM generated_content gc
                        WHERE gc.report_id = gr.id
                            AND gc.content_type_id = %s
                    )
                ORDER BY gr.created_at DESC
                LIMIT %s
            """
            
            self.cursor.execute(query, (self.content_type_id, limit))
            rows = self.cursor.fetchall()
            
            return [
                {
                    'id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'updated_at': row[3]
                }
                for row in rows
            ]
        except Exception as e:
            print(f"   ❌ Error fetching reports: {e}")
            return []
    
    def _fetch_recent_reports(self, limit: int = 10):
        """جلب التقارير الأخيرة"""
        try:
            query = """
                SELECT 
                    id,
                    title,
                    content,
                    updated_at
                FROM generated_report
                WHERE status = 'draft'
                ORDER BY updated_at DESC
                LIMIT %s
            """
            
            self.cursor.execute(query, (limit,))
            rows = self.cursor.fetchall()
            
            return [
                {
                    'id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'updated_at': row[3]
                }
                for row in rows
            ]
        except Exception as e:
            print(f"   ❌ Error fetching reports: {e}")
            return []
    
    def _get_existing_audio(self, report_id: int) -> Optional[Dict]:
        """جلب الصوت الموجود"""
        try:
            self.cursor.execute("""
                SELECT id, file_url, updated_at
                FROM generated_content
                WHERE report_id = %s
                    AND content_type_id = %s
                LIMIT 1
            """, (report_id, self.content_type_id))
            
            row = self.cursor.fetchone()
            if not row:
                return None
            
            return {
                'id': row[0],
                'file_url': row[1],
                'updated_at': row[2]
            }
        except Exception as e:
            print(f"   ❌ Error checking existing audio: {e}")
            return None
    
    def _save_audio_record(self, report_id: int, s3_url: str, text_content: str) -> bool:
        """حفظ سجل الصوت"""
        try:
            self.cursor.execute("""
                INSERT INTO generated_content (
                    report_id,
                    content_type_id,
                    title,
                    description,
                    file_url,
                    content,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (
                report_id,
                self.content_type_id,
                'Generated Audio',
                'AI-generated audio for news report',
                s3_url,
                text_content,
                'published'
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"   ❌ Error saving audio record: {e}")
            self.conn.rollback()
            return False
    
    def _update_audio_record(
        self, 
        content_id: int, 
        report_id: int, 
        s3_url: str, 
        text_content: str
    ) -> bool:
        """تحديث سجل الصوت"""
        try:
            self.cursor.execute("""
                UPDATE generated_content
                SET file_url = %s,
                    content = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (s3_url, text_content, content_id))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"   ❌ Error updating audio record: {e}")
            self.conn.rollback()
            return False
    
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


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        report_id = int(sys.argv[1])
        
        generator = AudioGenerator()
        result = generator.generate_for_report(report_id, force_update=True)
        
        if result.success:
            print(f"\n✅ Success!")
            print(f"   Audio URL: {result.audio_url}")
        else:
            print(f"\n❌ Failed: {result.error_message}")
        
        generator.close()
    else:
        print("Usage: python -m app.services.audio_generator <report_id>")