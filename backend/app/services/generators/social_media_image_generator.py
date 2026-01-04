#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎨 Social Media Image Generator
يولد 3 صور سوشال ميديا ويحفظهم في content_type_id = 9 كـ JSON

Structure in DB:
- content_type_id: 9 (Facebook Template)
- content: {"h-GAZA": "url", "n-NEWS": "url", "n-SPORT": "url"}
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
    مولّد صور السوشال ميديا
    
    يولد 3 صور:
    - h-GAZA (هنا غزة)
    - n-NEWS (إن نيوز)  
    - n-SPORT (إن سبورت)
    
    ويحفظهم كـ JSON في content_type_id = 9
    """
    
    # Content Type ID
    FACEBOOK_TEMPLATE_ID = 9
    
    # Templates (ordered)
    TEMPLATES = ['h-GAZA', 'n-NEWS', 'n-SPORT']
    
    # Logos
    LOGOS = {
        'h-GAZA': 'https://media-automation-bucket.s3.us-east-1.amazonaws.com/generated/assets/profile+picture.png',
        'n-NEWS': 'https://media-automation-bucket.s3.us-east-1.amazonaws.com/generated/assets/News.png',
        'n-SPORT': 'https://media-automation-bucket.s3.us-east-1.amazonaws.com/generated/assets/Sport.png'
    }
    
    def __init__(self):
        """Initialize"""
        print("\n" + "=" * 60)
        print("🎨 Social Media Image Generator")
        print("=" * 60)
        
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cursor = self.conn.cursor()
        print("✅ Database connected")
        
        self.s3_client = boto3.client('s3')
        self.bucket_name = os.getenv('S3_BUCKET_NAME', 'media-automation-bucket')
        self.s3_folder = 'generated/social-images/'
        print("✅ S3 initialized")
        
        self.output_size = (1200, 630)
        self.logo_size = (250, 250)
        
        print("=" * 60 + "\n")
    
    def generate_for_all_reports(self, force_update: bool = False, limit: int = 10) -> Dict:
        """
        🎯 Batch processing للـ Worker
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
                logo = self._download_logo(self.LOGOS[template])
                final = self._create_image(background.copy(), logo, title)
                upload = self._upload_to_s3(final, report_id, template)
                
                if upload['success']:
                    results[template] = upload['image_url']
            except Exception as e:
                print(f"   ⚠️  {template} failed: {e}")
        
        return {'success': len(results) > 0, 'images': results}
    
    def _get_reports_needing_images(self, force_update: bool, limit: int) -> List[int]:
        """Get reports"""
        try:
            if force_update:
                self.cursor.execute("""
                    SELECT id FROM generated_report 
                    WHERE status = 'published'
                    ORDER BY created_at DESC LIMIT %s
                """, (limit,))
            else:
                self.cursor.execute("""
                    SELECT gr.id FROM generated_report gr
                    WHERE gr.status = 'published'
                      AND NOT EXISTS (
                          SELECT 1 FROM generated_content gc
                          WHERE gc.report_id = gr.id
                            AND gc.content_type_id = %s
                            AND gc.status = 'completed'
                      )
                    ORDER BY gr.created_at DESC LIMIT %s
                """, (self.FACEBOOK_TEMPLATE_ID, limit))
            
            return [r[0] for r in self.cursor.fetchall()]
        except:
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
        """Get image"""
        try:
            self.cursor.execute("SELECT cluster_id FROM generated_report WHERE id = %s", (report_id,))
            c = self.cursor.fetchone()
            
            if c:
                self.cursor.execute("""
                    SELECT rn.content_img FROM raw_news rn
                    JOIN news_cluster_members ncm ON ncm.news_id = rn.id
                    WHERE ncm.cluster_id = %s
                        AND rn.content_img IS NOT NULL AND rn.content_img != ''
                    ORDER BY rn.collected_at DESC LIMIT 1
                """, (c[0],))
                
                r = self.cursor.fetchone()
                if r and r[0]:
                    return r[0]
        except:
            self.conn.rollback()
        
        try:
            self.cursor.execute("""
                SELECT file_url FROM generated_content
                WHERE report_id = %s AND content_type_id = 6
                    AND file_url IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
            """, (report_id,))
            
            r = self.cursor.fetchone()
            if r and r[0]:
                return r[0]
        except:
            self.conn.rollback()
        
        return None
    
    def _save_to_generated_content(self, report_id: int, images: Dict, force_update: bool) -> str:
        """
        Save as JSON in content field
        
        Example:
        content = '{"h-GAZA": "url1", "n-NEWS": "url2", "n-SPORT": "url3"}'
        """
        try:
            content_json = json.dumps(images, ensure_ascii=False)
            
            self.cursor.execute("""
                SELECT id FROM generated_content
                WHERE report_id = %s AND content_type_id = %s
            """, (report_id, self.FACEBOOK_TEMPLATE_ID))
            
            existing = self.cursor.fetchone()
            
            if existing and not force_update:
                return 'skipped'
            
            if existing:
                self.cursor.execute("""
                    UPDATE generated_content
                    SET content = %s, status = 'completed', updated_at = NOW()
                    WHERE id = %s
                """, (content_json, existing[0]))
                self.conn.commit()
                return 'updated'
            else:
                self.cursor.execute("""
                    INSERT INTO generated_content (
                        report_id, content_type_id, content, status, created_at, updated_at
                    ) VALUES (%s, %s, %s, 'completed', NOW(), NOW())
                """, (report_id, self.FACEBOOK_TEMPLATE_ID, content_json))
                self.conn.commit()
                return 'created'
        except Exception as e:
            print(f"   ⚠️  Save failed: {e}")
            self.conn.rollback()
            return 'failed'
    
    def _download_image(self, url: str) -> Image.Image:
        """Download"""
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert('RGB')
    
    def _download_logo(self, url: str) -> Image.Image:
        """Download logo"""
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        logo = Image.open(BytesIO(r.content))
        
        if logo.mode != 'RGBA':
            logo = logo.convert('RGBA')
        
        w, h = logo.size
        tw, th = self.logo_size
        scale = min(tw/w, th/h)
        
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
        """Add logo"""
        if logo.mode == 'RGBA':
            img.paste(logo, (30, 30), logo)
        else:
            img.paste(logo, (30, 30))
        return img
    
    def _add_title_with_box(self, img: Image.Image, title: str) -> Image.Image:
        """Add title"""
        font = self._get_font(58)
        words = title.split()
        temp = ImageDraw.Draw(Image.new('RGB', img.size))
        max_w = img.size[0] - 140
        
        lines_raw = []
        cur = []
        
        for word in words:
            test = ' '.join(cur + [word])
            reshaped = arabic_reshaper.reshape(test)
            bidi = get_display(reshaped)
            bbox = temp.textbbox((0,0), bidi, font=font)
            
            if bbox[2]-bbox[0] <= max_w:
                cur.append(word)
            else:
                if cur:
                    lines_raw.append(' '.join(cur))
                cur = [word]
        
        if cur:
            lines_raw.append(' '.join(cur))
        
        if len(lines_raw) > 3:
            lines_raw = lines_raw[:3]
            lines_raw[2] += '...'
        
        lines = [get_display(arabic_reshaper.reshape(l)) for l in lines_raw]
        
        lh = 75
        max_lw = max([temp.textbbox((0,0), l, font=font)[2]-temp.textbbox((0,0), l, font=font)[0] for l in lines])
        
        px, py = 60, 40
        bw = max_lw + px*2
        bh = len(lines)*lh + py*2
        bx = (img.size[0]-bw)//2
        by = img.size[1]-bh-50
        
        overlay = Image.new('RGBA', img.size, (0,0,0,0))
        do = ImageDraw.Draw(overlay)
        self._draw_rounded_rect(do, [bx,by,bx+bw,by+bh], 20, (0,0,0,200))
        img.paste(overlay, (0,0), overlay)
        
        draw = ImageDraw.Draw(img)
        y = by + py
        
        for line in lines:
            bbox = draw.textbbox((0,0), line, font=font)
            lw = bbox[2]-bbox[0]
            x = (img.size[0]-lw)//2
            draw.text((x+3,y+3), line, font=font, fill=(0,0,0,200))
            draw.text((x,y), line, font=font, fill='white')
            y += lh
        
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
        """Get font"""
        for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf']:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except:
                    pass
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
        rid = int(sys.argv[1])
        result = gen.generate_all(rid)
        print(f"\n✅ Result: {result}")
    else:
        stats = gen.generate_for_all_reports(limit=3)
        print(f"\n📊 Stats: {stats}")
    
    gen.close()