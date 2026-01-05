#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎨 Image Generator Service (Enhanced)
توليد صور AI للتقارير باستخدام Gemini

📁 S3 Path: generated/images/

✅ التحسينات:
- تقليل وقت الانتظار (30 ثانية بدل 60)
- تسجيل الفشل للمحاولة لاحقاً
- تخطي التقارير اللي فشلت كتير
- Fallback prompt أبسط
"""

import os
import sys
import time
import io
import base64
import psycopg2
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass
import boto3
from PIL import Image, ImageEnhance

from settings import GEMINI_API_KEY, GEMINI_IMAGE_MODEL, DB_CONFIG

try:
    from google import genai
    from google.genai.types import GenerateContentConfig, Modality
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
    skipped: bool = False  # ✅ جديد: تم تخطيه؟


class ImageGenerator:
    """مولد الصور للتقارير باستخدام Gemini"""
    
    # ✅ الحد الأقصى لمحاولات الفشل قبل التخطي
    MAX_FAILURE_ATTEMPTS = 3
    
    # ✅ وقت الانتظار بين الطلبات (ثواني)
    WAIT_BETWEEN_REQUESTS = 30  # كان 60
    
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
            self.s3_folder = os.getenv('S3_GENERATED_IMAGES_FOLDER', 'generated/images/')
            
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
        
        # Facebook-optimized image settings
        self.facebook_specs = {
            'width': 1200,
            'height': 630,
            'ratio': 1.91,
            'quality': 95
        }
        
        print(f"📐 Facebook-optimized specs: {self.facebook_specs['width']}×{self.facebook_specs['height']}px")
        
        # ✅ إنشاء جدول تتبع الفشل إذا ما كان موجود
        self._ensure_failure_tracking_table()
    
    def _ensure_failure_tracking_table(self):
        """✅ إنشاء جدول تتبع فشل توليد الصور"""
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS image_generation_failures (
                    id SERIAL PRIMARY KEY,
                    report_id INTEGER NOT NULL,
                    error_message TEXT,
                    attempt_count INTEGER DEFAULT 1,
                    last_attempt_at TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(report_id)
                )
            """)
            self.conn.commit()
        except Exception as e:
            print(f"   ⚠️ Could not create failure tracking table: {e}")
            self.conn.rollback()
    
    def _get_failure_count(self, report_id: int) -> int:
        """✅ جلب عدد محاولات الفشل السابقة"""
        try:
            self.cursor.execute("""
                SELECT attempt_count FROM image_generation_failures
                WHERE report_id = %s
            """, (report_id,))
            row = self.cursor.fetchone()
            return row[0] if row else 0
        except:
            return 0
    
    def _record_failure(self, report_id: int, error_message: str):
        """✅ تسجيل فشل التوليد"""
        try:
            self.cursor.execute("""
                INSERT INTO image_generation_failures (report_id, error_message, attempt_count, last_attempt_at)
                VALUES (%s, %s, 1, NOW())
                ON CONFLICT (report_id) DO UPDATE SET
                    error_message = EXCLUDED.error_message,
                    attempt_count = image_generation_failures.attempt_count + 1,
                    last_attempt_at = NOW()
            """, (report_id, error_message[:500]))
            self.conn.commit()
        except Exception as e:
            print(f"   ⚠️ Could not record failure: {e}")
            self.conn.rollback()
    
    def _clear_failure(self, report_id: int):
        """✅ مسح سجل الفشل بعد النجاح"""
        try:
            self.cursor.execute("""
                DELETE FROM image_generation_failures WHERE report_id = %s
            """, (report_id,))
            self.conn.commit()
        except:
            self.conn.rollback()
    
    def generate_for_report(
        self,
        report_id: int,
        force_update: bool = False
    ) -> ImageGenerationResult:
        """توليد صورة لتقرير واحد"""
        print(f"\n{'='*70}")
        print(f"🎨 Generating Image for Report #{report_id}")
        print(f"{'='*70}")
        
        # ✅ فحص عدد محاولات الفشل السابقة
        failure_count = self._get_failure_count(report_id)
        if failure_count >= self.MAX_FAILURE_ATTEMPTS:
            print(f"⏭️  Skipping: Failed {failure_count} times before (max: {self.MAX_FAILURE_ATTEMPTS})")
            return ImageGenerationResult(
                success=False,
                skipped=True,
                error_message=f"Skipped: exceeded {self.MAX_FAILURE_ATTEMPTS} failures"
            )
        
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
                s3_path=existing_image['file_url'],
                skipped=True
            )
        
        # إنشاء prompt للصورة
        image_prompt = self._create_image_prompt(report)
        print(f"📝 Prompt created ({len(image_prompt)} chars)")
        
        # توليد الصورة ورفعها على S3
        generation_result = self._generate_and_upload_image(image_prompt, report_id)
        
        if not generation_result.success:
            print(f"❌ Image generation failed: {generation_result.error_message}")
            
            # ✅ تسجيل الفشل
            self._record_failure(report_id, generation_result.error_message or "Unknown error")
            
            # ✅ محاولة بـ fallback prompt أبسط
            if failure_count < 1:  # محاولة واحدة فقط بالـ fallback
                print("   🔄 Trying with simplified prompt...")
                simple_prompt = self._create_simple_prompt(report)
                generation_result = self._generate_and_upload_image(simple_prompt, report_id)
                
                if generation_result.success:
                    print("   ✅ Succeeded with simplified prompt!")
                    self._clear_failure(report_id)
            
            if not generation_result.success:
                return generation_result
        
        print(f"✅ Image generated and uploaded successfully")
        s3_url = generation_result.image_url
        
        # ✅ مسح سجل الفشل بعد النجاح
        self._clear_failure(report_id)
        
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
        limit: int = 40
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
        print(f"⏱️  Wait time between requests: {self.WAIT_BETWEEN_REQUESTS}s")
        
        stats = {
            'total_reports': len(reports),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'updated': 0
        }
        
        for i, report in enumerate(reports, 1):
            print(f"\n[{i}/{len(reports)}] Report #{report['id']}")
            
            try:
                result = self.generate_for_report(
                    report_id=report['id'],
                    force_update=force_update
                )
                
                if result.success:
                    if result.skipped:
                        stats['skipped'] += 1
                    elif force_update:
                        stats['updated'] += 1
                    else:
                        stats['success'] += 1
                else:
                    if result.skipped:
                        stats['skipped'] += 1
                    else:
                        stats['failed'] += 1
                
            except Exception as e:
                print(f"   ❌ Unexpected error: {e}")
                stats['failed'] += 1
                # ✅ الاستمرار حتى لو فشل تقرير واحد
                continue
            
            # ✅ تأخير مخفف بين الطلبات
            if i < len(reports) and not (result.skipped if result else True):
                print(f"   ⏳ Waiting {self.WAIT_BETWEEN_REQUESTS} seconds...")
                time.sleep(self.WAIT_BETWEEN_REQUESTS)
        
        print(f"\n{'='*70}")
        print(f"📊 Final Results:")
        print(f"   • Reports: {stats['total_reports']}")
        print(f"   • Success: {stats['success']}")
        print(f"   • Updated: {stats['updated']}")
        print(f"   • Skipped: {stats['skipped']}")
        print(f"   • Failed: {stats['failed']}")
        print(f"{'='*70}")
        
        return stats
    
    def _create_image_prompt(self, report: Dict) -> str:
        """Create a neutral, generic news illustration image prompt optimized for Facebook"""

        keywords = self._extract_keywords(report['title'], report['content'])
        context = ", ".join(keywords[:3])

        prompt = f"""
    Create a neutral, realistic, high-quality news illustration image optimized for Facebook sharing.

    Context (for understanding only, do NOT visualize text or symbols):
    {context}

    Image Requirements:
    - Generic and neutral visual representation
    - No text, captions, signs, or written elements
    - No political symbols, flags, or logos
    - No identifiable people or faces
    - No dramatic or emotional emphasis
    - No exaggeration or sensationalism

    Visual Style:
    - Realistic photojournalism
    - Professional news broadcast aesthetic
    - Calm, balanced composition
    - Natural lighting
    - Clean background or relevant environment
    - Documentary-style realism

    Technical Specifications:
    - Aspect ratio: 1.91:1 (Facebook optimized)
    - Horizontal orientation (landscape)
    - High resolution and quality
    - Safe zone composition (important elements centered)
    - Suitable for social media sharing
    - Suitable as a background image for news content
    - Contextual but non-specific

    Important:
    - The image must NOT depict specific events, locations, or individuals
    - The image should feel illustrative, general, and unbiased
    """

        return prompt

    
    def _create_simple_prompt(self, report: Dict) -> str:
        """✅ Prompt أبسط للـ fallback"""
        keywords = self._extract_keywords(report['title'], report['content'])
        main_topic = keywords[0] if keywords else "news"
        
        return f"""Create a simple professional news image about: {main_topic}

Style: Clean, professional, news-style
Format: Horizontal 16:9
No text, no faces, no watermarks
"""
    
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
    
    def _optimize_for_facebook(self, image: Image.Image) -> Image.Image:
        """Optimize image for Facebook specifications"""
        
        # Facebook optimal dimensions
        target_width = self.facebook_specs['width']
        target_height = self.facebook_specs['height']
        
        print(f"   📐 Optimizing for Facebook: {target_width}×{target_height}px")
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Calculate scaling to fit Facebook dimensions
        img_width, img_height = image.size
        img_ratio = img_width / img_height
        target_ratio = target_width / target_height
        
        if img_ratio > target_ratio:
            # Image is wider - fit by height
            new_height = target_height
            new_width = int(target_height * img_ratio)
        else:
            # Image is taller - fit by width
            new_width = target_width
            new_height = int(target_width / img_ratio)
        
        # Resize image
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Crop to exact Facebook dimensions (center crop)
        left = (new_width - target_width) // 2
        top = (new_height - target_height) // 2
        right = left + target_width
        bottom = top + target_height
        
        cropped = resized.crop((left, top, right, bottom))
        
        # Enhance for social media
        from PIL import ImageEnhance
        
        # Slight brightness boost
        enhancer = ImageEnhance.Brightness(cropped)
        enhanced = enhancer.enhance(1.05)
        
        # Slight contrast boost
        enhancer = ImageEnhance.Contrast(enhanced)
        enhanced = enhancer.enhance(1.1)
        
        # Slight color saturation boost
        enhancer = ImageEnhance.Color(enhanced)
        enhanced = enhancer.enhance(1.1)
        
        print(f"   ✅ Image optimized: {enhanced.size[0]}×{enhanced.size[1]}px")
        
        return enhanced
    
    def _generate_and_upload_image(
        self, 
        prompt: str, 
        report_id: int, 
        retries: int = 3
    ) -> ImageGenerationResult:
        """توليد الصورة ورفعها على S3"""
        for attempt in range(retries):
            try:
                print(f"   🎨 Generating image (attempt {attempt + 1}/{retries})...")
                
                config = GenerateContentConfig(
                    response_modalities=[Modality.TEXT, Modality.IMAGE]
                )
                
                response = self.gemini_client.models.generate_content(
                    model=self.image_model,
                    contents=[prompt],
                    config=config
                )
                
                print(f"   ✅ Response received")
                
                image_data_raw = None
                text_response = None
                
                if not hasattr(response, 'parts') or not response.parts:
                    raise ValueError("Response has no parts")
                
                print(f"   📦 Response has {len(response.parts)} parts")
                
                for i, part in enumerate(response.parts):
                    if hasattr(part, 'text') and part.text:
                        text_response = part.text
                    
                    if hasattr(part, 'inline_data') and part.inline_data:
                        if hasattr(part.inline_data, 'data') and part.inline_data.data:
                            image_data_raw = part.inline_data.data
                            print(f"   🎉 Image data found!")
                            break
                
                if not image_data_raw:
                    raise ValueError("No image data found in response parts")
                
                print(f"   ✅ Image data extracted ({len(image_data_raw):,} bytes)")
                
                # Convert to PNG
                try:
                    if image_data_raw[:8] == b'\x89PNG\r\n\x1a\n':
                        decoded_data = image_data_raw
                    else:
                        decoded_data = base64.b64decode(image_data_raw)
                    
                    temp_image = Image.open(io.BytesIO(decoded_data))
                    
                    # Optimize for Facebook
                    optimized_image = self._optimize_for_facebook(temp_image)
                    
                    byteImgIO = io.BytesIO()
                    optimized_image.save(byteImgIO, "JPEG", quality=self.facebook_specs['quality'])
                    byteImgIO.seek(0)
                    image_bytes = byteImgIO.read()
                    
                    print(f"   ✅ Optimized for Facebook ({len(image_bytes):,} bytes)")
                    
                except Exception as e:
                    raise ValueError(f"Cannot process image data: {e}")
                
                # Upload to S3
                timestamp = int(time.time())
                file_name = f"report_{report_id}_{timestamp}.jpg"
                s3_key = f"{self.s3_folder}{file_name}"
                
                print(f"   📤 Uploading to S3: {s3_key}")
                
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=image_bytes,
                    ContentType='image/jpeg'
                )
                
                s3_url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_key}"
                print(f"   ✅ Uploaded successfully: {s3_url}")
                
                return ImageGenerationResult(
                    success=True,
                    image_url=s3_url,
                    prompt_used=prompt
                )
                
            except Exception as e:
                error_msg = str(e)
                print(f"   ⚠️  Error: {error_msg[:200]}")
                
                # Rate limit handling
                if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
                    if attempt < retries - 1:
                        wait_time = 30  # ✅ مخفف من 60
                        print(f"   ⏳ Rate limit hit. Waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        return ImageGenerationResult(
                            success=False,
                            error_message="Rate limit exceeded"
                        )
                
                # "Response has no parts" - common error
                if "no parts" in error_msg.lower():
                    if attempt < retries - 1:
                        print(f"   🔄 Empty response, retrying in 10s...")
                        time.sleep(10)
                        continue
                
                if attempt < retries - 1:
                    print(f"   🔄 Retrying in 5 seconds...")
                    time.sleep(5)  # ✅ مخفف من 10
                    continue
                else:
                    return ImageGenerationResult(
                        success=False,
                        error_message=f"Generation failed: {error_msg[:200]}"
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
    
    def _fetch_reports_without_images(self, limit: int = 40) -> List[Dict]:
        """✅ جلب التقارير بدون صور (مع استثناء الفاشلة كتير)"""
        try:
            query = """
                SELECT 
                    gr.id,
                    gr.title,
                    gr.content,
                    gr.updated_at,
                    gr.created_at
                FROM generated_report gr
                WHERE gr.status = 'draft'
                    AND NOT EXISTS (
                        SELECT 1
                        FROM generated_content gc
                        WHERE gc.report_id = gr.id
                            AND gc.content_type_id = %s
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM image_generation_failures igf
                        WHERE igf.report_id = gr.id
                            AND igf.attempt_count >= %s
                    )
                ORDER BY gr.created_at DESC
                LIMIT %s
            """
            
            self.cursor.execute(query, (self.content_type_id, self.MAX_FAILURE_ATTEMPTS, limit))
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
            # Fallback to original query
            return self._fetch_reports_without_images_simple(limit)
    
    def _fetch_reports_without_images_simple(self, limit: int = 40) -> List[Dict]:
        """جلب التقارير بدون صور (بدون فلتر الفشل)"""
        try:
            query = """
                SELECT gr.id, gr.title, gr.content, gr.updated_at, gr.created_at
                FROM generated_report gr
                WHERE gr.status = 'draft'
                    AND NOT EXISTS (
                        SELECT 1 FROM generated_content gc
                        WHERE gc.report_id = gr.id AND gc.content_type_id = %s
                    )
                ORDER BY gr.created_at DESC
                LIMIT %s
            """
            self.cursor.execute(query, (self.content_type_id, limit))
            return [{'id': r[0], 'title': r[1], 'content': r[2], 'updated_at': r[3]} for r in self.cursor.fetchall()]
        except:
            return []
    
    def _fetch_recent_reports(self, limit: int = 40) -> List[Dict]:
        """جلب التقارير الأخيرة"""
        try:
            query = """
                SELECT id, title, content, updated_at, created_at
                FROM generated_report
                WHERE status = 'draft'
                ORDER BY updated_at DESC
                LIMIT %s
            """
            self.cursor.execute(query, (limit,))
            return [{'id': r[0], 'title': r[1], 'content': r[2], 'updated_at': r[3]} for r in self.cursor.fetchall()]
        except:
            return []
    
    def _get_existing_image(self, report_id: int) -> Optional[Dict]:
        """جلب الصورة الموجودة"""
        try:
            self.cursor.execute("""
                SELECT id, file_url, updated_at
                FROM generated_content
                WHERE report_id = %s AND content_type_id = %s
                LIMIT 1
            """, (report_id, self.content_type_id))
            
            row = self.cursor.fetchone()
            return {'id': row[0], 'file_url': row[1], 'updated_at': row[2]} if row else None
        except:
            return None
    
    def _save_image_record(self, report_id: int, s3_url: str, prompt: str) -> bool:
        """حفظ سجل الصورة"""
        try:
            self.cursor.execute("""
                INSERT INTO generated_content (
                    report_id, content_type_id, title, description,
                    file_url, content, status, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (report_id, self.content_type_id, 'Generated Image',
                  'AI-generated image for news report', s3_url, prompt, 'published'))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"   ❌ Error saving: {e}")
            self.conn.rollback()
            return False
    
    def _update_image_record(self, content_id: int, report_id: int, s3_url: str, prompt: str) -> bool:
        """تحديث سجل الصورة"""
        try:
            self.cursor.execute("""
                UPDATE generated_content
                SET file_url = %s, content = %s, updated_at = NOW()
                WHERE id = %s
            """, (s3_url, prompt, content_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"   ❌ Error updating: {e}")
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
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        report_id = int(sys.argv[1])
        generator = ImageGenerator()
        result = generator.generate_for_report(report_id, force_update=True)
        
        if result.success:
            print(f"\n✅ Success! Image URL: {result.image_url}")
        else:
            print(f"\n❌ Failed: {result.error_message}")
        
        generator.close()
    else:
        print("Usage: python image_generator.py <report_id>")