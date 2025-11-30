#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎨 Image Generator Service - Final Fixed Version
توليد صور للتقارير ورفعها على S3 في folder image/
"""

import os
import sys
import time
import io
import psycopg2
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import boto3
from botocore.exceptions import ClientError

from settings import GEMINI_API_KEY, GEMINI_IMAGE_MODEL, DB_CONFIG

try:
    from google import genai
    from PIL import Image
except ImportError:
    print("❌ Required packages not installed.")
    print("   Run: pip install google-genai Pillow boto3")
    sys.exit(1)


@dataclass
class ImageGenerationResult:
    """نتيجة توليد الصورة"""
    success: bool
    image_url: Optional[str] = None
    s3_path: Optional[str] = None
    error_message: Optional[str] = None
    prompt_used: Optional[str] = None


class ImageGenerator:
    """مولد الصور للتقارير باستخدام Gemini"""
    
    def __init__(self):
        """تهيئة المولد"""
        self.conn = None
        self.cursor = None
        
        # اتصال قاعدة البيانات
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print("✅ ImageGenerator initialized (Database)")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise
        
        # تهيئة S3 Client
        try:
            self.s3_client = boto3.client('s3')
            self.bucket_name = os.getenv('S3_BUCKET_NAME', 'media-automation-bucket')
            self.s3_folder = os.getenv('S3_IMAGE_FOLDER', 'image/')
            print(f"✅ S3 client initialized (Bucket: {self.bucket_name})")
            print(f"   📁 Upload folder: {self.s3_folder}")
        except Exception as e:
            print(f"❌ S3 client initialization failed: {e}")
            raise
        
        # تهيئة Gemini Client
        try:
            self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            self.image_model = GEMINI_IMAGE_MODEL
            print(f"✅ Gemini client initialized (Model: {self.image_model})")
        except Exception as e:
            print(f"❌ Gemini client failed: {e}")
            raise
        
        # Content Type ID for Generated Images
        self.content_type_id = 6
    
    def generate_for_report(
        self,
        report_id: int,
        force_update: bool = False
    ) -> ImageGenerationResult:
        """توليد صورة لتقرير واحد"""
        print(f"\n{'='*70}")
        print(f"🎨 Generating Image for Report #{report_id}")
        print(f"{'='*70}")
        
        # جلب التقرير
        report = self._fetch_report(report_id)
        if not report:
            return ImageGenerationResult(
                success=False,
                error_message="Report not found"
            )
        
        print(f"📰 Report: {report['title'][:60]}...")
        
        # فحص وجود صورة مسبقاً
        existing_image = self._get_existing_image(report_id)
        
        if existing_image and not force_update:
            print(f"⏭️  Image already exists (ID: {existing_image['id']})")
            return ImageGenerationResult(
                success=True,
                image_url=existing_image['file_url'],
                s3_path=existing_image['file_url']
            )
        
        # إنشاء prompt للصورة
        image_prompt = self._create_image_prompt(report)
        print(f"📝 Prompt created ({len(image_prompt)} chars)")
        
        # توليد الصورة ورفعها على S3 مباشرة
        generation_result = self._generate_and_upload_image(image_prompt, report_id)
        
        if not generation_result.success:
            print(f"❌ Image generation failed: {generation_result.error_message}")
            return generation_result
        
        print(f"✅ Image generated and uploaded successfully")
        s3_url = generation_result.image_url
        
        # حفظ في قاعدة البيانات
        if existing_image:
            success = self._update_image_record(
                content_id=existing_image['id'],
                report_id=report_id,
                s3_url=s3_url,
                prompt=image_prompt
            )
            action = "Updated"
        else:
            success = self._save_image_record(
                report_id=report_id,
                s3_url=s3_url,
                prompt=image_prompt
            )
            action = "Created"
        
        if success:
            print(f"✅ {action} database record")
            return ImageGenerationResult(
                success=True,
                image_url=s3_url,
                s3_path=s3_url,
                prompt_used=image_prompt
            )
        else:
            return ImageGenerationResult(
                success=False,
                error_message=f"Failed to {action.lower()} database record"
            )
    
    def generate_for_all_reports(
        self,
        force_update: bool = False,
        limit: int = 10
    ) -> Dict:
        """توليد صور لكل التقارير"""
        print(f"\n{'='*70}")
        print(f"🎨 Generating Images for All Reports")
        print(f"{'='*70}")
        
        if force_update:
            reports = self._fetch_recent_reports(limit)
        else:
            reports = self._fetch_reports_without_images(limit)
        
        if not reports:
            print("📭 No reports need image generation")
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
                print("   ⏳ Waiting 60 seconds before next request...")
                time.sleep(60)
        
        print(f"\n{'='*70}")
        print(f"📊 Final Results:")
        print(f"   • Reports: {stats['total_reports']}")
        print(f"   • Success: {stats['success']}")
        print(f"   • Updated: {stats['updated']}")
        print(f"   • Failed: {stats['failed']}")
        print(f"{'='*70}")
        
        return stats
    
    def _create_image_prompt(self, report: Dict) -> str:
        """إنشاء prompt لتوليد الصورة"""
        title = report['title']
        content = report['content']
        
        keywords = self._extract_keywords(title, content)
        keywords_str = "، ".join(keywords[:5])
        
        prompt = f"""أنشئ صورة إخبارية احترافية واقعية تُمثل هذا الخبر:

العنوان: {title}

الموضوع: {keywords_str}

المتطلبات:
- صورة واقعية عالية الجودة
- أسلوب صحافة احترافية
- مناسبة للبث الإخباري
- بدون نصوص أو علامات مائية
- بدون وجوه أشخاص محددين
- تركيب متوازن وجذاب
- إضاءة احترافية
- دقة عالية مناسبة للنشر

الحجم: أفقي (16:9)
الأسلوب: تصوير صحفي واقعي
"""
        return prompt
    
    def _extract_keywords(self, title: str, content: str) -> List[str]:
        """استخراج كلمات مفتاحية"""
        stop_words = {
            'في', 'من', 'إلى', 'على', 'عن', 'مع', 'بعد', 'قبل',
            'أن', 'ال', 'و', 'أو', 'هذا', 'هذه', 'ذلك', 'التي', 'الذي'
        }
        
        text = f"{title} {content}"
        words = text.split()
        
        keywords = []
        for word in words:
            cleaned = word.strip('.,،؛:!؟"\'()')
            if len(cleaned) > 3 and cleaned not in stop_words:
                keywords.append(cleaned)
        
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                unique_keywords.append(kw)
                seen.add(kw)
            if len(unique_keywords) >= 10:
                break
        
        return unique_keywords
    
    def _generate_and_upload_image(self, prompt: str, report_id: int, retries: int = 3) -> ImageGenerationResult:
        """
        ✅ توليد الصورة ورفعها مباشرة على S3
        في folder image/ بدون ACL
        """
        for attempt in range(retries):
            try:
                print(f"   🎨 Generating image (attempt {attempt + 1}/{retries})...")
                
                # استدعاء Gemini
                response = self.gemini_client.models.generate_content(
                    model=self.image_model,
                    contents=[prompt]
                )
                
                # استخراج البيانات
                image_bytes = None
                
                for part in response.parts:
                    if part.text is not None:
                        print(f"   ℹ️  Response text: {part.text[:100]}")
                    
                    elif part.inline_data is not None:
                        try:
                            # ✅ الطريقة 1: استخدام as_image()
                            pil_image = part.as_image()
                            if pil_image:
                                # ✅ حفظ في BytesIO بدون format= keyword
                                buffer = io.BytesIO()
                                pil_image.save(buffer, "PNG")  # PNG كـ format string عادي
                                buffer.seek(0)  # العودة لبداية الـ buffer
                                image_bytes = buffer.getvalue()
                                print(f"   ✅ Image extracted using as_image()")
                                break
                        except Exception as e:
                            print(f"   ⚠️  as_image() failed: {e}")
                            
                            # ✅ الطريقة 2: البيانات الخام مباشرة
                            try:
                                image_bytes = part.inline_data.data
                                print(f"   ✅ Image extracted as raw bytes")
                                break
                            except Exception as e2:
                                print(f"   ⚠️  Raw extraction failed: {e2}")
                
                # ✅ رفع على S3 مباشرة
                if image_bytes:
                    timestamp = int(time.time())
                    file_name = f"report_{report_id}_{timestamp}.png"
                    s3_key = f"{self.s3_folder}{file_name}"  # image/report_9_1234567890.png
                    
                    print(f"   📤 Uploading to S3: {s3_key}")
                    
                    # ✅ رفع بدون ACL (حل مشكلة AccessControlListNotSupported)
                    self.s3_client.put_object(
                        Bucket=self.bucket_name,
                        Key=s3_key,
                        Body=image_bytes,
                        ContentType='image/png'
                        # ❌ بدون ACL='public-read' - السبب: الـ bucket ما بيسمح ACLs
                    )
                    
                    # ✅ بناء الـ URL العام
                    s3_url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_key}"
                    print(f"   ✅ Uploaded successfully: {s3_url}")
                    
                    return ImageGenerationResult(
                        success=True,
                        image_url=s3_url,
                        prompt_used=prompt
                    )
                else:
                    raise ValueError("No image data in response")
                
            except Exception as e:
                error_msg = str(e)
                print(f"   ⚠️  Error: {error_msg[:200]}")
                
                # فحص rate limit
                if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
                    if attempt < retries - 1:
                        wait_time = 60
                        print(f"   ⏳ Rate limit hit. Waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        return ImageGenerationResult(
                            success=False,
                            error_message="Rate limit exceeded. Please try again later."
                        )
                
                # أخطاء أخرى
                if attempt < retries - 1:
                    print(f"   🔄 Retrying in 10 seconds...")
                    time.sleep(10)
                    continue
                else:
                    return ImageGenerationResult(
                        success=False,
                        error_message=f"Generation failed: {error_msg[:300]}"
                    )
        
        return ImageGenerationResult(
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
    
    def _fetch_reports_without_images(self, limit: int = 10) -> List[Dict]:
        """جلب التقارير بدون صور"""
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
    
    def _fetch_recent_reports(self, limit: int = 10) -> List[Dict]:
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
    
    def _get_existing_image(self, report_id: int) -> Optional[Dict]:
        """جلب الصورة الموجودة"""
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
            print(f"   ❌ Error checking existing image: {e}")
            return None
    
    def _save_image_record(self, report_id: int, s3_url: str, prompt: str) -> bool:
        """حفظ سجل الصورة"""
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
                'Generated Image',
                'AI-generated image for news report',
                s3_url,
                prompt,
                'published'
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"   ❌ Error saving image record: {e}")
            self.conn.rollback()
            return False
    
    def _update_image_record(self, content_id: int, report_id: int, s3_url: str, prompt: str) -> bool:
        """تحديث سجل الصورة"""
        try:
            self.cursor.execute("""
                UPDATE generated_content
                SET file_url = %s,
                    content = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (s3_url, prompt, content_id))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"   ❌ Error updating image record: {e}")
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
        
        generator = ImageGenerator()
        result = generator.generate_for_report(report_id, force_update=True)
        
        if result.success:
            print(f"\n✅ Success!")
            print(f"   Image URL: {result.image_url}")
        else:
            print(f"\n❌ Failed: {result.error_message}")
        
        generator.close()
    else:
        print("Usage: python -m app.services.image_generator <report_id>")