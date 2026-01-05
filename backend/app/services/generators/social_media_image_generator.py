#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎨 Social Media Image Generator
يولد صورتين سوشال ميديا ويحفظهم في content_type_id = 9 كـ JSON

Structure in DB:
- content_type_id: 9 (Facebook Template)
- content: {"h-GAZA": "url", "DOT": "url"}
"""

import os
import json
import requests
from io import BytesIO
from typing import Dict, Optional, List
import psycopg2

from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import arabic_reshaper
from bidi.algorithm import get_display
import boto3

from settings import DB_CONFIG


class SocialImageGenerator:
    """
    🎨 مولّد صور فيسبوك المحسن
    
    المواصفات المثالية لفيسبوك:
    - الأبعاد: 1200 × 630 بكسل
    - النسبة: 1.91:1 (الموصى بها رسمياً)
    - المنطقة الآمنة: النص في المنتصف، الشعار بهامش 20px
    - الجودة: عالية مع ضغط مناسب
    
    يولد صورتين:
    - h-GAZA (هنا غزة)
    - DOT (دوت)
    
    ويحفظهم كـ JSON في content_type_id = 9
    """
    
    # Content Type ID
    FACEBOOK_TEMPLATE_ID = 9
    
    # Templates (ordered) - فقط DOT و h-GAZA
    TEMPLATES = ['h-GAZA', 'DOT']  # عطلنا n-NEWS و n-SPORT
    
    # Logos
    LOGOS = {
        'h-GAZA': 'https://media-automation-bucket.s3.us-east-1.amazonaws.com/generated/assets/profile+picture.png',
        # 'n-NEWS': 'https://media-automation-bucket.s3.us-east-1.amazonaws.com/generated/assets/News.png',  # معطل
        # 'n-SPORT': 'https://media-automation-bucket.s3.us-east-1.amazonaws.com/generated/assets/Sport.png',  # معطل
        'DOT': 'https://media-automation-bucket.s3.us-east-1.amazonaws.com/generated/assets/Screenshot+2026-01-04+112600.png'
    }
    
    def __init__(self):
        """Initialize with Facebook-optimized settings"""
        print("\n" + "=" * 60)
        print("🎨 Social Media Image Generator")
        print("📐 Facebook Optimized: 1200×630px (1.91:1)")
        print("=" * 60)
        
        # إعداد اتصال قاعدة البيانات مع UTF-8 صريح ومحسن
        db_config = DB_CONFIG.copy()
        
        # إضافة UTF-8 encoding مع إعدادات محسنة
        db_config['options'] = '-c client_encoding=utf8 -c standard_conforming_strings=on -c escape_string_warning=off'
        
        # إنشاء الاتصال مع معالجة أخطاء الترميز
        try:
            self.conn = psycopg2.connect(**db_config)
            
            # تأكيد UTF-8 encoding بشكل صريح
            self.conn.set_client_encoding('UTF8')
            
            # تعيين connection encoding مع إعدادات إضافية
            with self.conn.cursor() as temp_cursor:
                temp_cursor.execute("SET client_encoding TO 'UTF8'")
                temp_cursor.execute("SET standard_conforming_strings = on")
                temp_cursor.execute("SET escape_string_warning = off")
                temp_cursor.execute("SET bytea_output = 'escape'")  # لمعالجة البيانات الثنائية
                self.conn.commit()
            
            print("✅ Database connected with enhanced UTF-8 encoding")
            
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            # محاولة اتصال بديلة بدون options
            try:
                self.conn = psycopg2.connect(**DB_CONFIG)
                self.conn.set_client_encoding('UTF8')
                print("✅ Database connected with fallback UTF-8 encoding")
            except Exception as e2:
                print(f"❌ Fallback connection also failed: {e2}")
                raise
        
        self.cursor = self.conn.cursor()
        
        self.s3_client = boto3.client('s3')
        self.bucket_name = os.getenv('S3_BUCKET_NAME', 'media-automation-bucket')
        self.s3_folder = 'generated/social-images/'
        print("✅ S3 initialized")
        
        # Facebook Image settings - المقاس المثالي لفيسبوك
        # النسبة: 1.91:1 (الموصى بها رسمياً من فيسبوك)
        # المقاس: 1200 × 630 بكسل (مثالي للـ Feed)
        self.output_size = (1200, 630)
        
        # Validate Facebook specs
        self._validate_facebook_specs()
        
        # Logo sizes - أحجام موحدة للشعارات
        self.logo_sizes = {
            'h-GAZA': (160, 160),    # حجم أصغر قليلاً للتوازن
            'DOT': (160, 160)        # حجم موحد
        }
        
        print("=" * 60 + "\n")
    
    def _validate_facebook_specs(self):
        """Validate that settings meet Facebook specifications"""
        width, height = self.output_size
        ratio = width / height
        
        # Facebook optimal specs
        fb_width, fb_height = 1200, 630
        fb_ratio = fb_width / fb_height
        
        print(f"📐 Validating Facebook Specs:")
        print(f"   Current: {width}×{height}px ({ratio:.2f}:1)")
        print(f"   Facebook: {fb_width}×{fb_height}px ({fb_ratio:.2f}:1)")
        
        if width == fb_width and height == fb_height:
            print("   ✅ Perfect match!")
        else:
            print("   ⚠️  Dimensions adjusted for Facebook")
            self.output_size = (fb_width, fb_height)
        
        if abs(ratio - fb_ratio) < 0.01:
            print("   ✅ Aspect ratio optimal for Facebook")
        else:
            print("   ⚠️  Aspect ratio adjusted")
    
    def generate_for_all_reports(self, force_update: bool = False, limit: int = 10) -> Dict:
        """
        🎯 Batch processing للـ Worker
        يولد صور فيسبوك للتقارير المنشورة (published)
        
        الأولوية للصور:
        1. Generated Image (content_type_id = 6) - الصورة المولدة
        2. Raw News Image - صورة من الأخبار الخام
        """
        
        print(f"\n{'='*70}")
        print(f"🎨 Batch Generation")
        print(f"   Limit: {limit}, Force: {force_update}")
        print(f"{'='*70}\n")
        
        stats = {'total_reports': 0, 'success': 0, 'updated': 0, 'skipped': 0, 'failed': 0}
        
        try:
            reports = self._get_reports_needing_images(force_update, limit)
            stats['total_reports'] = len(reports)
            
            if not reports:
                print("✅ No reports need images")
                return stats
            
            print(f"📊 Processing {len(reports)} reports\n")
            
            for i, report_id in enumerate(reports, 1):
                print(f"[{i}/{len(reports)}] Report #{report_id}...")
                
                try:
                    result = self.generate_all(report_id)
                    
                    if result['success']:
                        saved = self._save_to_generated_content(
                            report_id, result['images'], force_update
                        )
                        
                        if saved == 'created':
                            stats['success'] += 1
                        elif saved == 'updated':
                            stats['updated'] += 1
                        elif saved == 'skipped':
                            stats['skipped'] += 1
                        
                        print(f"   ✅ {len(result['images'])} images")
                    else:
                        stats['failed'] += 1
                        print(f"   ❌ {result.get('error')}")
                except Exception as e:
                    stats['failed'] += 1
                    print(f"   ❌ {e}")
            
            print(f"\n{'='*70}")
            print(f"📊 SUMMARY: {stats}")
            print(f"{'='*70}\n")
            
        except Exception as e:
            print(f"❌ Fatal: {e}")
        
        return stats
    
    def generate_all(self, report_id: int) -> Dict:
        """Generate 3 images for one report"""
        
        title = self._get_report_title(report_id)
        if not title:
            return {'success': False, 'error': 'No title'}
        
        bg_url = self._get_background_image(report_id)
        if not bg_url:
            return {'success': False, 'error': 'No image'}
        
        try:
            background = self._download_image(bg_url)
        except:
            return {'success': False, 'error': 'Download failed'}
        
        results = {}
        
        for template in self.TEMPLATES:
            try:
                logo = self._download_logo(self.LOGOS[template], template)  # Pass template name
                final = self._create_image(background.copy(), logo, title)
                upload = self._upload_to_s3(final, report_id, template)
                
                if upload['success']:
                    results[template] = upload['image_url']
            except Exception as e:
                print(f"   ⚠️  {template} failed: {e}")
        
        return {'success': len(results) > 0, 'images': results}
    
    def _get_reports_needing_images(self, force_update: bool, limit: int) -> List[int]:
        """Get all reports that need Facebook images (any status)"""
        try:
            if force_update:
                # Force update: get latest reports regardless of existing Facebook images
                self.cursor.execute("""
                    SELECT id FROM generated_report 
                    ORDER BY id DESC LIMIT %s
                """, (limit,))
            else:
                # Normal mode: get reports without Facebook images
                self.cursor.execute("""
                    SELECT r.id FROM generated_report r
                    LEFT JOIN generated_content gc 
                        ON gc.report_id = r.id 
                        AND gc.content_type_id = %s
                    WHERE gc.id IS NULL
                    ORDER BY r.id DESC LIMIT %s
                """, (self.FACEBOOK_TEMPLATE_ID, limit))
            
            return [r[0] for r in self.cursor.fetchall()]
        except Exception as e:
            print(f"   ⚠️  Error getting reports: {e}")
            self.conn.rollback()
            return []
    
    def _get_report_title(self, report_id: int) -> Optional[str]:
        """Get title"""
        try:
            self.cursor.execute("SELECT title FROM generated_report WHERE id = %s", (report_id,))
            r = self.cursor.fetchone()
            return r[0] if r else None
        except:
            return None
    
    def _get_background_image(self, report_id: int) -> Optional[str]:
        """
        Get background image with priority:
        1. Generated image (content_type_id = 6) - الأولوية للصورة المولدة
        2. Raw news image from cluster - إذا ما في مولدة، نأخذ من الأخبار
        """
        
        # Priority 1: Generated image (content_type_id = 6)
        try:
            self.cursor.execute("""
                SELECT file_url FROM generated_content
                WHERE report_id = %s AND content_type_id = 6
                    AND file_url IS NOT NULL AND file_url != ''
                ORDER BY created_at DESC LIMIT 1
            """, (report_id,))
            
            result = self.cursor.fetchone()
            if result and result[0]:
                print(f"   📸 Using generated image: {result[0][:50]}...")
                return result[0]
        except Exception as e:
            print(f"   ⚠️  Error getting generated image: {e}")
            self.conn.rollback()
        
        # Priority 2: Raw news image from cluster
        try:
            self.cursor.execute("SELECT cluster_id FROM generated_report WHERE id = %s", (report_id,))
            cluster_result = self.cursor.fetchone()
            
            if cluster_result and cluster_result[0]:
                self.cursor.execute("""
                    SELECT rn.content_img FROM raw_news rn
                    JOIN news_cluster_members ncm ON ncm.news_id = rn.id
                    WHERE ncm.cluster_id = %s
                        AND rn.content_img IS NOT NULL AND rn.content_img != ''
                    ORDER BY rn.collected_at DESC LIMIT 1
                """, (cluster_result[0],))
                
                result = self.cursor.fetchone()
                if result and result[0]:
                    print(f"   📸 Using raw news image: {result[0][:50]}...")
                    return result[0]
        except Exception as e:
            print(f"   ⚠️  Error getting raw news image: {e}")
            self.conn.rollback()
        
        print(f"   ❌ No background image found for report {report_id}")
        return None
    
    def _save_to_generated_content(self, report_id: int, images: Dict, force_update: bool) -> str:
        """
        Save as JSON in content field with enhanced UTF-8 encoding handling
        
        Example:
        content = '{"h-GAZA": "url1", "DOT": "url2"}'
        """
        try:
            # التأكد من أن النصوص بترميز UTF-8 صحيح
            content_json = json.dumps(images, ensure_ascii=False, indent=None)
            
            # التأكد من أن الاتصال يستخدم UTF-8 مع إعدادات محسنة
            self.cursor.execute("SET client_encoding TO 'UTF8'")
            self.cursor.execute("SET standard_conforming_strings = on")
            
            self.cursor.execute("""
                SELECT id FROM generated_content
                WHERE report_id = %s AND content_type_id = %s
            """, (report_id, self.FACEBOOK_TEMPLATE_ID))
            
            existing = self.cursor.fetchone()
            
            if existing:
                # Always update if exists (removed force_update check)
                self.cursor.execute("""
                    UPDATE generated_content
                    SET content = %s, status = 'completed', updated_at = NOW()
                    WHERE id = %s
                """, (content_json, existing[0]))
                self.conn.commit()
                return 'updated'
            else:
                # Insert new
                self.cursor.execute("""
                    INSERT INTO generated_content (
                        report_id, content_type_id, content, status, created_at, updated_at
                    ) VALUES (%s, %s, %s, 'completed', NOW(), NOW())
                """, (report_id, self.FACEBOOK_TEMPLATE_ID, content_json))
                self.conn.commit()
                return 'created'
                
        except Exception as e:
            error_msg = str(e)
            print(f"   ⚠️  Save failed: {error_msg}")
            print(f"   🔍 Error type: {type(e).__name__}")
            
            if "codec" in error_msg.lower() or "encoding" in error_msg.lower():
                print(f"   💡 Encoding issue detected - trying enhanced fallback approaches...")
                
                # محاولة 1: إعادة إنشاء الاتصال مع UTF-8 صريح
                try:
                    print(f"   🔄 Attempt 1: Reconnecting with explicit UTF-8...")
                    
                    # إغلاق الاتصال الحالي
                    if self.cursor:
                        self.cursor.close()
                    if self.conn:
                        self.conn.close()
                    
                    # إعادة إنشاء الاتصال
                    db_config = DB_CONFIG.copy()
                    db_config['options'] = '-c client_encoding=utf8 -c standard_conforming_strings=on'
                    
                    self.conn = psycopg2.connect(**db_config)
                    self.conn.set_client_encoding('UTF8')
                    self.cursor = self.conn.cursor()
                    
                    # إعادة المحاولة
                    self.cursor.execute("SET client_encoding TO 'UTF8'")
                    
                    if existing:
                        self.cursor.execute("""
                            UPDATE generated_content
                            SET content = %s, status = 'completed', updated_at = NOW()
                            WHERE id = %s
                        """, (content_json, existing[0]))
                        self.conn.commit()
                        print(f"   ✅ Success with reconnection!")
                        return 'updated'
                    else:
                        self.cursor.execute("""
                            INSERT INTO generated_content (
                                report_id, content_type_id, content, status, created_at, updated_at
                            ) VALUES (%s, %s, %s, 'completed', NOW(), NOW())
                        """, (report_id, self.FACEBOOK_TEMPLATE_ID, content_json))
                        self.conn.commit()
                        print(f"   ✅ Success with reconnection!")
                        return 'created'
                        
                except Exception as e2:
                    print(f"   ❌ Reconnection approach failed: {e2}")
                
                # محاولة 2: تحويل إلى bytes ثم string
                try:
                    print(f"   🔄 Attempt 2: Bytes conversion...")
                    content_bytes = content_json.encode('utf-8')
                    content_str = content_bytes.decode('utf-8')
                    
                    if existing:
                        self.cursor.execute("""
                            UPDATE generated_content
                            SET content = %s, status = 'completed', updated_at = NOW()
                            WHERE id = %s
                        """, (content_str, existing[0]))
                        self.conn.commit()
                        print(f"   ✅ Success with bytes conversion!")
                        return 'updated'
                    else:
                        self.cursor.execute("""
                            INSERT INTO generated_content (
                                report_id, content_type_id, content, status, created_at, updated_at
                            ) VALUES (%s, %s, %s, 'completed', NOW(), NOW())
                        """, (report_id, self.FACEBOOK_TEMPLATE_ID, content_str))
                        self.conn.commit()
                        print(f"   ✅ Success with bytes conversion!")
                        return 'created'
                        
                except Exception as e3:
                    print(f"   ❌ Bytes conversion failed: {e3}")
                
                # محاولة 3: ASCII encoding كحل أخير
                try:
                    print(f"   🔄 Attempt 3: ASCII fallback...")
                    content_ascii = json.dumps(images, ensure_ascii=True, indent=None)
                    
                    if existing:
                        self.cursor.execute("""
                            UPDATE generated_content
                            SET content = %s, status = 'completed', updated_at = NOW()
                            WHERE id = %s
                        """, (content_ascii, existing[0]))
                        self.conn.commit()
                        print(f"   ⚠️  Saved with ASCII encoding (Unicode escaped)")
                        return 'updated'
                    else:
                        self.cursor.execute("""
                            INSERT INTO generated_content (
                                report_id, content_type_id, content, status, created_at, updated_at
                            ) VALUES (%s, %s, %s, 'completed', NOW(), NOW())
                        """, (report_id, self.FACEBOOK_TEMPLATE_ID, content_ascii))
                        self.conn.commit()
                        print(f"   ⚠️  Saved with ASCII encoding (Unicode escaped)")
                        return 'created'
                        
                except Exception as e4:
                    print(f"   ❌ ASCII fallback also failed: {e4}")
            
            # إذا فشل كل شيء
            print(f"   ❌ All encoding approaches failed")
            self.conn.rollback()
            return 'failed'
    
    def _download_image(self, url: str) -> Image.Image:
        """Download"""
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert('RGB')
    
    def _download_logo(self, url: str, template: str) -> Image.Image:
        """Download logo with template-specific size"""
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        logo = Image.open(BytesIO(r.content))
        
        if logo.mode != 'RGBA':
            logo = logo.convert('RGBA')
        
        # Get size for this template
        target_w, target_h = self.logo_sizes.get(template, (180, 180))
        
        w, h = logo.size
        scale = min(target_w/w, target_h/h)
        
        return logo.resize((int(w*scale), int(h*scale)), Image.Resampling.LANCZOS)
    
    def _create_image(self, bg: Image.Image, logo: Image.Image, title: str) -> Image.Image:
        """Create"""
        bg = self._resize_to_fit(bg)
        bg = self._enhance_image(bg)
        bg = self._add_logo(bg, logo)
        bg = self._add_title_with_box(bg, title)
        return bg
    
    def _resize_to_fit(self, img: Image.Image) -> Image.Image:
        """Resize"""
        w, h = self.output_size
        iw, ih = img.size
        scale = max(w/iw, h/ih)
        nw, nh = int(iw*scale), int(ih*scale)
        img = img.resize((nw, nh), Image.Resampling.LANCZOS)
        l = (nw-w)//2
        t = (nh-h)//2
        return img.crop((l, t, l+w, t+h))
    
    def _enhance_image(self, img: Image.Image) -> Image.Image:
        """Enhance"""
        img = ImageEnhance.Brightness(img).enhance(1.1)
        img = ImageEnhance.Contrast(img).enhance(1.15)
        img = ImageEnhance.Color(img).enhance(1.2)
        return img
    
    def _add_logo(self, img: Image.Image, logo: Image.Image) -> Image.Image:
        """Add logo in safe zone for Facebook"""
        # المنطقة الآمنة لفيسبوك - بعيداً عن الحواف
        safe_margin = 20  # هامش آمن من الحواف
        x = safe_margin
        y = safe_margin
        
        if logo.mode == 'RGBA':
            img.paste(logo, (x, y), logo)
        else:
            img.paste(logo, (x, y))
        return img
    
    def _add_title_with_box(self, img: Image.Image, title: str) -> Image.Image:
        """Add title with proper Arabic RTL support and enhanced font handling"""
        
        # استخدام الخط العربي المناسب
        font = self._get_arabic_font(64)  # خط عربي محسن
        
        # معالجة النص العربي بشكل صحيح
        # تنظيف النص من المسافات الزائدة والأحرف الخاصة
        title = title.strip()
        
        print(f"   🔤 Original text: '{title}'")
        
        # ✅ الحل الصحيح: تقسيم النص أولاً ثم معالجة كل سطر
        temp = ImageDraw.Draw(Image.new('RGB', img.size))
        max_w = img.size[0] - 140
        
        # 1️⃣ تقسيم النص الخام (بدون معالجة عربية) إلى كلمات
        raw_title = title.strip()
        words = raw_title.split()
        
        # 2️⃣ تكوين الأسطر بناءً على العرض (بدون معالجة عربية)
        lines_raw = []
        cur = []
        
        for word in words:
            test_line = ' '.join(cur + [word])
            
            try:
                # قياس عرض النص (استخدام النص الخام للقياس)
                bbox = temp.textbbox((0, 0), test_line, font=font)
                text_width = bbox[2] - bbox[0]
                
            except Exception as e:
                print(f"   ⚠️  Text measurement error: {e}")
                # تقدير تقريبي للعرض
                text_width = len(test_line) * 20
            
            if text_width <= max_w:
                cur.append(word)
            else:
                if cur:
                    lines_raw.append(' '.join(cur))
                cur = [word]
        
        if cur:
            lines_raw.append(' '.join(cur))
        
        # تحديد عدد الأسطر المسموح (3 كحد أقصى)
        if len(lines_raw) > 3:
            lines_raw = lines_raw[:3]
            if len(lines_raw[2]) > 50:  # إذا كان السطر الأخير طويل
                lines_raw[2] = lines_raw[2][:47] + '...'
        
        # 3️⃣ الخطوة الأهم: معالجة العربية لكل سطر قبل الرسم
        lines = []
        for line in lines_raw:
            # تحقق إذا السطر يحتوي على عربي
            if any('\u0600' <= c <= '\u06FF' for c in line):
                try:
                    # معالجة العربية لهذا السطر فقط
                    reshaped = arabic_reshaper.reshape(line)
                    bidi_line = get_display(reshaped)
                    lines.append(bidi_line)
                    print(f"   🔄 Arabic line processed: '{line}' → '{bidi_line}'")
                except Exception as e:
                    print(f"   ⚠️  Arabic processing error for line '{line}': {e}")
                    lines.append(line)  # fallback للنص العادي
            else:
                # نص إنجليزي - لا يحتاج معالجة
                lines.append(line)
                print(f"   ✅ English line (no processing): '{line}'")
        
        print(f"   📝 Final lines for drawing:")
        for i, line in enumerate(lines):
            print(f"      Line {i+1}: '{line}'")
        
        # إعدادات النص المحسنة لفيسبوك
        lh = 75  # المسافة بين الأسطر
        
        # حساب أقصى عرض للأسطر
        max_lw = 0
        for line in lines:
            try:
                bbox = temp.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
                max_lw = max(max_lw, line_width)
            except:
                max_lw = max(max_lw, 400)  # قيمة افتراضية
        
        # Padding محسن للمنطقة الآمنة في فيسبوك
        px, py = 60, 40  # padding مناسب
        bw = max_lw + px * 2
        bh = len(lines) * lh + py * 2
        
        # وضعية النص في المنطقة الآمنة (وسط الصورة)
        bx = (img.size[0] - bw) // 2
        by = (img.size[1] - bh) // 2  # في المنتصف تماماً للأمان
        
        # خلفية النص مع شفافية مناسبة
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        do = ImageDraw.Draw(overlay)
        self._draw_rounded_rect(do, [bx, by, bx + bw, by + bh], 20, (0, 0, 0, 200))  # شفافية مناسبة
        img.paste(overlay, (0, 0), overlay)
        
        draw = ImageDraw.Draw(img)
        y = by + py
        
        # رسم كل سطر (النص معالج مسبقاً بشكل صحيح)
        for line in lines:
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                lw = bbox[2] - bbox[0]
                
                # محاذاة النص في المنتصف (مناسب للعربية والإنجليزية)
                x = (img.size[0] - lw) // 2
                
                # Shadow أوضح
                draw.text((x + 4, y + 4), line, font=font, fill=(0, 0, 0, 220))
                # النص الأساسي
                draw.text((x, y), line, font=font, fill='white')
                
                print(f"   ✅ Drew line at ({x}, {y}): '{line}'")
                y += lh
                
            except Exception as e:
                print(f"   ⚠️  Error drawing line '{line}': {e}")
                # محاولة رسم بسيطة كـ fallback
                try:
                    x = (img.size[0] - 200) // 2  # تقدير تقريبي
                    draw.text((x + 4, y + 4), line, font=font, fill=(0, 0, 0, 220))
                    draw.text((x, y), line, font=font, fill='white')
                    y += lh
                except:
                    print(f"   ❌ Complete failure drawing line: {line}")
        
        return img
                
                # محاذاة النص في المنتصف (مناسب للعربية والإنجليزية)
                x = (img.size[0] - lw) // 2
                
                # Shadow أوضح
                draw.text((x + 4, y + 4), line, font=font, fill=(0, 0, 0, 220))
                # النص الأساسي
                draw.text((x, y), line, font=font, fill='white')
                
                print(f"   ✅ Drew line at ({x}, {y}): '{line}'")
                y += lh
                
            except Exception as e:
                print(f"   ⚠️  Error drawing line '{line}': {e}")
                # محاولة رسم بسيطة كـ fallback
                try:
                    x = (img.size[0] - 200) // 2  # تقدير تقريبي
                    draw.text((x + 4, y + 4), line, font=font, fill=(0, 0, 0, 220))
                    draw.text((x, y), line, font=font, fill='white')
                    y += lh
                except:
                    print(f"   ❌ Complete failure drawing line: {line}")
        
        return img
    
    def _draw_rounded_rect(self, d, c, r, f):
        """Rounded rect"""
        x1,y1,x2,y2=c
        d.rectangle([x1+r,y1,x2-r,y2],fill=f)
        d.rectangle([x1,y1+r,x2,y2-r],fill=f)
        d.ellipse([x1,y1,x1+r*2,y1+r*2],fill=f)
        d.ellipse([x2-r*2,y1,x2,y1+r*2],fill=f)
        d.ellipse([x1,y2-r*2,x1+r*2,y2],fill=f)
        d.ellipse([x2-r*2,y2-r*2,x2,y2],fill=f)
    
    def _get_font(self, size=58):
        """Get font - fallback method"""
        for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf']:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except:
                    pass
        return ImageFont.load_default()
    
    def _get_arabic_font(self, size=64):
        """Get Arabic font with Render-optimized fallback chain"""
        
        # قائمة الخطوط بالأولوية (محسنة لـ Render)
        font_paths = [
            # الخط العربي المحلي (أولوية عالية لـ Render)
            'fonts/NotoSansArabic-Regular.ttf',
            './fonts/NotoSansArabic-Regular.ttf',
            'backend/fonts/NotoSansArabic-Regular.ttf',
            './backend/fonts/NotoSansArabic-Regular.ttf',
            
            # خطوط النظام العربية (Linux - Render containers)
            '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf',
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            
            # Ubuntu/Debian fonts (common on Render)
            '/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf',
            '/usr/share/fonts/truetype/ubuntu/Ubuntu-Regular.ttf',
            
            # خطوط النظام العربية (Windows - للتطوير المحلي)
            'C:/Windows/Fonts/arial.ttf',
            'C:/Windows/Fonts/arialbd.ttf',
            'C:/Windows/Fonts/tahoma.ttf',
            'C:/Windows/Fonts/tahomabd.ttf',
            
            # خطوط النظام العربية (macOS - للتطوير المحلي)
            '/System/Library/Fonts/Arial.ttf',
            '/System/Library/Fonts/Helvetica.ttc',
        ]
        
        # محاولة تحميل الخطوط بالترتيب
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, size)
                    print(f"   ✅ Using Arabic font: {os.path.basename(font_path)}")
                    return font
                except Exception as e:
                    print(f"   ⚠️  Failed to load {font_path}: {e}")
                    continue
        
        # محاولة تثبيت الخطوط على Render
        try:
            print(f"   🔄 Attempting to install fonts for Render deployment...")
            import subprocess
            
            # محاولة تثبيت خطوط Noto على Ubuntu (Render containers)
            try:
                subprocess.run(['apt-get', 'update'], check=False, capture_output=True, timeout=30)
                subprocess.run(['apt-get', 'install', '-y', 'fonts-noto'], check=False, capture_output=True, timeout=60)
                print(f"   ✅ Attempted to install Noto fonts on Render")
                
                # محاولة تحميل الخط بعد التثبيت
                noto_path = '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf'
                if os.path.exists(noto_path):
                    font = ImageFont.truetype(noto_path, size)
                    print(f"   ✅ Successfully loaded installed Noto font")
                    return font
                    
            except Exception as e:
                print(f"   ⚠️  Font installation failed: {e}")
                
        except Exception as e:
            print(f"   ⚠️  Could not attempt font installation: {e}")
        
        # محاولة تحميل الخط من الإنترنت (Render fallback)
        try:
            print(f"   🌐 Downloading Arabic font for Render...")
            import requests
            import tempfile
            
            # تحميل خط Noto Sans Arabic من Google Fonts
            font_url = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansArabic/NotoSansArabic-Regular.ttf"
            
            response = requests.get(font_url, timeout=30)
            response.raise_for_status()
            
            # حفظ في ملف مؤقت
            temp_font_path = tempfile.mktemp(suffix='.ttf')
            with open(temp_font_path, 'wb') as f:
                f.write(response.content)
            
            font = ImageFont.truetype(temp_font_path, size)
            print(f"   ✅ Downloaded and loaded Arabic font from Google Fonts")
            return font
            
        except Exception as e:
            print(f"   ⚠️  Font download failed: {e}")
        
        # إذا فشل كل شيء، استخدم الخط الافتراضي
        print(f"   ⚠️  Using default font - Arabic may not render correctly on Render")
        print(f"   💡 Consider bundling fonts in your Render deployment")
        try:
            return ImageFont.load_default()
        except:
            # آخر محاولة - إنشاء خط بسيط
            return ImageFont.load_default()
    
    def _upload_to_s3(self, img: Image.Image, report_id: int, template: str) -> Dict:
        """Upload"""
        try:
            buf = BytesIO()
            img.save(buf, format='JPEG', quality=95)
            buf.seek(0)
            
            import time
            fn = f"{template}_{report_id}_{int(time.time())}.jpg"
            key = f"{self.s3_folder}{template}/{fn}"
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=buf.getvalue(),
                ContentType='image/jpeg'
            )
            
            return {'success': True, 'image_url': f"https://{self.bucket_name}.s3.amazonaws.com/{key}"}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def close(self):
        """Close"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
        except:
            pass


if __name__ == "__main__":
    gen = SocialImageGenerator()
    
    import sys
    if len(sys.argv) > 1:
        # Single report with database save
        rid = int(sys.argv[1])
        result = gen.generate_all(rid)
        
        if result['success']:
            print(f"\n✅ Generated {len(result['images'])} images")
            
            # Save to database
            saved = gen._save_to_generated_content(rid, result['images'], False)
            
            if saved == 'created':
                print(f"✅ Saved to database (content_type_id = 9)")
            elif saved == 'updated':
                print(f"✅ Updated in database")
            elif saved == 'skipped':
                print(f"⚠️  Already exists in database")
            else:
                print(f"❌ Failed to save to database")
            
            print(f"\n📊 Images:")
            for name, url in result['images'].items():
                print(f"  {name}: {url}")
        else:
            print(f"\n❌ Failed: {result.get('error')}")
    else:
        # Batch mode
        stats = gen.generate_for_all_reports(limit=3)
        print(f"\n📊 Stats: {stats}")
    
    gen.close()