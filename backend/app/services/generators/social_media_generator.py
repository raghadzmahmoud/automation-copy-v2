#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📱 Social Media Content Generator
توليد محتوى سوشيال ميديا من التقارير - JSON Format
"""

import re
import time
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import psycopg2
from google import genai

from settings import GEMINI_API_KEY, GEMINI_MODEL, DB_CONFIG


@dataclass
class SocialMediaContent:
    """محتوى سوشيال ميديا"""
    title: str
    content: str
    platform: str
    
    def is_valid(self) -> Tuple[bool, str]:
        """التحقق من الصحة"""
        if not self.title or len(self.title.strip()) < 5:
            return False, "العنوان قصير جداً"
        
        if not self.content or len(self.content.strip()) < 50:
            return False, "المحتوى قصير جداً"
        
        max_length = {
            'twitter': 350,
            'facebook': 600,
            'instagram': 400   
         }.get(self.platform.lower(), 600)
        
        if len(self.content) > max_length:
            return False, f"المحتوى طويل جداً ({len(self.content)} > {max_length})"
        
        return True, "OK"
    
    def to_dict(self) -> Dict:
        """تحويل لـ dict"""
        return {
            'title': self.title,
            'content': self.content
        }


class SocialMediaParser:
    """محلل نصوص السوشيال ميديا"""
    
    @staticmethod
    def parse(text: str, platform: str) -> Optional[SocialMediaContent]:
        """استخراج المحتوى من النص"""
        text = text.strip()
        
        result = SocialMediaParser._parse_with_markers(text, platform)
        if result:
            return result
        
        result = SocialMediaParser._parse_simple(text, platform)
        if result:
            return result
        
        return None
    
    @staticmethod
    def _parse_with_markers(text: str, platform: str) -> Optional[SocialMediaContent]:
        """البحث عن markers"""
        patterns = [
            (r'\[العنوان\][:\s]*(.+?)(?=\[المحتوى\])', r'\[المحتوى\][:\s]*(.+)'),
            (r'العنوان[:\s]+(.+?)(?=المحتوى[:\s])', r'المحتوى[:\s]+(.+)'),
            (r'Title[:\s]+(.+?)(?=Content[:\s])', r'Content[:\s]+(.+)'),
        ]
        
        for title_pattern, content_pattern in patterns:
            title_match = re.search(title_pattern, text, re.DOTALL | re.IGNORECASE)
            content_match = re.search(content_pattern, text, re.DOTALL | re.IGNORECASE)
            
            if title_match and content_match:
                title = SocialMediaParser._clean(title_match.group(1))
                content = SocialMediaParser._clean(content_match.group(1))
                
                if title and content:
                    return SocialMediaContent(
                        title=title,
                        content=content,
                        platform=platform
                    )
        
        return None
    
    @staticmethod
    def _parse_simple(text: str, platform: str) -> Optional[SocialMediaContent]:
        """استخراج بسيط"""
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        if len(lines) < 2:
            return None
        
        title = lines[0]
        title = re.sub(r'^\*+|\*+$|^#+\s*|^[""]|[""]$', '', title).strip()
        
        content = '\n'.join(lines[1:])
        content = SocialMediaParser._clean(content)
        
        if title and content and len(title) > 5:
            return SocialMediaContent(
                title=title,
                content=content,
                platform=platform
            )
        
        return None
    
    @staticmethod
    def _clean(text: str) -> str:
        """تنظيف النص"""
        if not text:
            return ""
        
        text = re.sub(r'\*\*|\*|__|_|```|`', '', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'[{}\[\]]', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        
        return text.strip()


class SocialMediaGenerator:
    """مولد محتوى السوشيال ميديا"""
    
    def __init__(self):
        """تهيئة المولد"""
        self.conn = None
        self.cursor = None
        self.parser = SocialMediaParser()
        
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print("✅ SocialMediaGenerator initialized")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise
        
        try:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
            print(f"✅ Gemini client ready (Model: {GEMINI_MODEL})")
        except Exception as e:
            print(f"❌ Gemini client failed: {e}")
            raise
        
        self.platforms = {
            'facebook': {
                'name': 'Facebook',
                'max_length': 600,
                'style': 'جذاب ومشوّق',
                'hashtags': 3
            },
            'twitter': {
                'name': 'Twitter/X',
                'max_length': 350,
                'style': 'مختصر وقوي',
                'hashtags': 2
            },
            'instagram': {
                'name': 'Instagram',
                'max_length': 500,
                'style': 'بصري وملهم',
                'hashtags': 5
            }
        }
    
    def generate_for_report(
        self,
        report_id: int,
        platforms: List[str] = None,
        force_update: bool = False
    ) -> Dict:
        """توليد محتوى سوشيال ميديا لتقرير واحد"""
        print(f"\n{'='*70}")
        print(f"📱 Generating Social Media Content for Report #{report_id}")
        print(f"{'='*70}")
        
        report = self._fetch_report(report_id)
        if not report:
            print("❌ Report not found")
            return {'success': False, 'error': 'Report not found'}
        
        print(f"📰 Report: {report['title'][:50]}...")
        
        if not platforms:
            platforms = ['facebook', 'twitter', 'instagram']
        
        existing_content = self._get_existing_content(report_id)
        
        if existing_content and not force_update:
            print(f"⏭️  Content already exists (ID: {existing_content['id']})")
            return {'success': True, 'skipped': True, 'content_id': existing_content['id']}
        
        all_content = {}
        failed_platforms = []
        
        for platform in platforms:
            if platform not in self.platforms:
                print(f"⚠️  Unknown platform: {platform}")
                continue
            
            print(f"\n📱 Platform: {self.platforms[platform]['name']}")
            
            content = self._generate_for_platform(report, platform)
            
            if content:
                all_content[platform] = content
                print(f"   ✅ Generated")
            else:
                failed_platforms.append(platform)
                print(f"   ❌ Failed")
            
            time.sleep(2)
        
        if all_content:
            if existing_content:
                success = self._update_combined_content(
                    content_id=existing_content['id'],
                    report_id=report_id,
                    all_content=all_content
                )
                action = "Updated"
            else:
                success = self._save_combined_content(
                    report_id=report_id,
                    all_content=all_content
                )
                action = "Created"
            
            if success:
                print(f"\n✅ {action} combined social media content")
                return {
                    'success': True,
                    'action': action.lower(),
                    'platforms_count': len(all_content),
                    'failed_platforms': failed_platforms
                }
            else:
                return {'success': False, 'error': f'Failed to {action.lower()}'}
        else:
            print("\n❌ No content generated")
            return {'success': False, 'error': 'No content generated'}
    
    def generate_for_all_reports(
        self,
        platforms: List[str] = None,
        force_update: bool = False,
        limit: int = 10
    ) -> Dict:
        """توليد محتوى لكل التقارير الجديدة"""
        print(f"\n{'='*70}")
        print(f"📱 Generating Social Media Content for All Reports")
        print(f"{'='*70}")
        
        if force_update:
            reports = self._fetch_recent_reports(limit)
        else:
            reports = self._fetch_reports_without_content(limit)
        
        if not reports:
            print("📭 No reports need content generation")
            return {'total_reports': 0, 'success': 0, 'failed': 0, 'skipped': 0}
        
        print(f"📋 Found {len(reports)} reports to process")
        
        total_stats = {
            'total_reports': len(reports),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'updated': 0
        }
        
        for i, report in enumerate(reports, 1):
            print(f"\n[{i}/{len(reports)}] Report #{report['id']}")
            
            result = self.generate_for_report(
                report['id'],
                platforms=platforms,
                force_update=force_update
            )
            
            if result.get('success'):
                if result.get('skipped'):
                    total_stats['skipped'] += 1
                elif result.get('action') == 'updated':
                    total_stats['updated'] += 1
                else:
                    total_stats['success'] += 1
            else:
                total_stats['failed'] += 1
        
        print(f"\n{'='*70}")
        print(f"📊 Final Results:")
        print(f"   • Reports: {total_stats['total_reports']}")
        print(f"   • Created: {total_stats['success']}")
        print(f"   • Updated: {total_stats['updated']}")
        print(f"   • Skipped: {total_stats['skipped']}")
        print(f"   • Failed: {total_stats['failed']}")
        print(f"{'='*70}")
        
        return total_stats
    
    def _generate_for_platform(self, report: Dict, platform: str) -> Optional[SocialMediaContent]:
        """توليد محتوى لمنصة واحدة"""
        platform_info = self.platforms[platform]
        prompt = self._create_prompt(report, platform_info)
        content = self._call_gemini(prompt, platform)
        return content
    
    def _create_prompt(self, report: Dict, platform_info: Dict) -> str:
        return f"""أنت كاتب محتوى محترف لوسائل التواصل الاجتماعي.

    المطلوب: اكتب منشور لـ {platform_info['name']} من التقرير التالي:

    العنوان: {report['title']}
    المحتوى: {report['content'][:1000]}...

    ═══════════════════════════════════════
    متطلبات المنشور:
    ═══════════════════════════════════════

    المنصة: {platform_info['name']}
    الأسلوب: {platform_info['style']}
    الطول: {platform_info['max_length']} حرف كحد أقصى
    الهاشتاقات: {platform_info['hashtags']} هاشتاقات مناسبة

    ═══════════════════════════════════════
    الشكل المطلوب:
    ═══════════════════════════════════════

    [العنوان]
    اكتب عنوان جذاب قصير (5-10 كلمات)

    [المحتوى]
    اكتب المنشور هنا:
    - ابدأ بجملة افتتاحية قوية تشد الانتباه
    - لخّص النقاط الرئيسية بوضوح
    - استخدم أسلوب {platform_info['style']}
    - أضف emojis مناسبة (2-3 فقط)
    - اختم بـ call-to-action
    - أضف {platform_info['hashtags']} هاشتاقات في النهاية.
    - **مهم جدًا:** ضع "_" بين كل كلمة في الهشتاق، لا تستخدم الفراغات أو الحروف المدمجة. مثال: فلسطين_المحتلة
    - كل هاشتاق يبدأ بـ #

    الطول: {platform_info['max_length']} حرف كحد أقصى

    الآن اكتب المنشور:
    """

    
    def _call_gemini(self, prompt: str, platform: str, retries: int = 3) -> Optional[SocialMediaContent]:
        """استدعاء Gemini"""
        for attempt in range(retries):
            try:
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config={
                        'temperature': 0.8,
                        'max_output_tokens': 1024
                    }
                )
                
                result_text = response.text.strip()
                content = self.parser.parse(result_text, platform)
                
                if not content:
                    print(f"   ⚠️  Could not parse, attempt {attempt + 1}/{retries}")
                    time.sleep(2)
                    continue
                
                is_valid, reason = content.is_valid()
                
                if not is_valid:
                    print(f"   ⚠️  {reason}, attempt {attempt + 1}/{retries}")
                    time.sleep(2)
                    continue
                
                return content
                
            except Exception as e:
                print(f"   ⚠️  Error: {str(e)[:100]}")
                time.sleep(2)
        
        print(f"   ❌ Failed after {retries} attempts")
        return None
    
    def _format_combined_content(self, all_content: Dict[str, SocialMediaContent]) -> str:
        """تنسيق المحتوى المجمّع كـ JSON"""
        json_content = {}
        for platform, content in all_content.items():
            json_content[platform] = content.to_dict()
        return json.dumps(json_content, ensure_ascii=False, indent=2)
    
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
    
    def _fetch_reports_without_content(self, limit: int = 10) -> List[Dict]:
        """جلب التقارير بدون محتوى سوشيال ميديا"""
        try:
            # ✅ الحل: استخدام NOT EXISTS بدل LEFT JOIN + DISTINCT
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
                            AND gc.content_type_id = 1
                    )
                ORDER BY gr.created_at DESC
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
    def _get_existing_content(self, report_id: int) -> Optional[Dict]:
        """جلب المحتوى الموجود"""
        try:
            self.cursor.execute("""
                SELECT id, content, updated_at
                FROM generated_content
                WHERE report_id = %s
                    AND content_type_id = 1
                LIMIT 1
            """, (report_id,))
            
            row = self.cursor.fetchone()
            if not row:
                return None
            
            return {'id': row[0], 'content': row[1], 'updated_at': row[2]}
        except Exception as e:
            print(f"   ❌ Error checking existing content: {e}")
            return None
    
    def _save_combined_content(self, report_id: int, all_content: Dict[str, SocialMediaContent]) -> bool:
        """حفظ المحتوى المجمّع"""
        try:
            combined_content = self._format_combined_content(all_content)
            title = "Social Media Content"
            description = f"Social media posts for {', '.join(all_content.keys())}"
            
            self.cursor.execute("""
                INSERT INTO generated_content (
                    report_id, content_type_id, title, description,
                    content, status, created_at, updated_at
                )
                VALUES (%s, 1, %s, %s, %s, 'draft', NOW(), NOW())
            """, (report_id, title, description, combined_content))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"   ❌ Error saving content: {e}")
            self.conn.rollback()
            return False
    
    def _update_combined_content(self, content_id: int, report_id: int, all_content: Dict[str, SocialMediaContent]) -> bool:
        """تحديث المحتوى المجمّع"""
        try:
            combined_content = self._format_combined_content(all_content)
            description = f"Social media posts for {', '.join(all_content.keys())}"
            
            self.cursor.execute("""
                UPDATE generated_content
                SET content = %s, description = %s, updated_at = NOW()
                WHERE id = %s
            """, (combined_content, description, content_id))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"   ❌ Error updating content: {e}")
            self.conn.rollback()
            return False
    
    def close(self):
        """إغلاق الاتصال"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
            print("✅ Database connection closed")
        except Exception as e:
            print(f"⚠️  Error closing: {e}")