#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📱 Social Media Content Generator - FIXED VERSION
توليد محتوى سوشيال ميديا من التقارير - JSON Format
✅ الآن: يولد 3 منشورات من برومبت واحد ويخزنهم كـ JSON
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
            'instagram': 500   
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
    """✅ محلل محسّن - يستخرج 3 منصات من رد واحد"""
    
    @staticmethod
    def parse_multi_platform(text: str) -> Optional[Dict[str, SocialMediaContent]]:
        """
        استخراج محتوى 3 منصات من نص واحد
        Returns: {'facebook': SocialMediaContent, 'twitter': ..., 'instagram': ...}
        """
        result = {}
        
        # البحث عن كل منصة
        platforms = ['facebook', 'twitter', 'instagram']
        
        for platform in platforms:
            # Pattern: [FACEBOOK] العنوان: ... المحتوى: ...
            pattern = rf'\[{platform.upper()}\](.*?)(?=\[(?:FACEBOOK|TWITTER|INSTAGRAM)\]|$)'
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            
            if match:
                section = match.group(1).strip()
                content_obj = SocialMediaParser._extract_from_section(section, platform)
                if content_obj:
                    result[platform] = content_obj
        
        # يجب أن نحصل على 3 منصات بالضبط
        if len(result) == 3:
            return result
        
        return None
    
    @staticmethod
    def _extract_from_section(section: str, platform: str) -> Optional[SocialMediaContent]:
        """استخراج العنوان والمحتوى من قسم واحد"""
        
        # البحث عن العنوان
        title_patterns = [
            r'العنوان[:\s]+(.+?)(?=المحتوى|$)',
            r'Title[:\s]+(.+?)(?=Content|المحتوى|$)',
            r'\*\*العنوان\*\*[:\s]+(.+?)(?=\*\*المحتوى|المحتوى|$)',
        ]
        
        title = None
        for pattern in title_patterns:
            match = re.search(pattern, section, re.DOTALL | re.IGNORECASE)
            if match:
                title = SocialMediaParser._clean_text(match.group(1))
                if title and len(title) > 5:
                    break
        
        if not title:
            # Fallback: أول سطر
            lines = [l.strip() for l in section.split('\n') if l.strip()]
            if lines:
                title = SocialMediaParser._clean_text(lines[0])
        
        # البحث عن المحتوى
        content_patterns = [
            r'المحتوى[:\s]+(.+)',
            r'Content[:\s]+(.+)',
            r'\*\*المحتوى\*\*[:\s]+(.+)',
        ]
        
        content = None
        for pattern in content_patterns:
            match = re.search(pattern, section, re.DOTALL | re.IGNORECASE)
            if match:
                content = SocialMediaParser._clean_text(match.group(1))
                if content and len(content) > 50:
                    break
        
        if not content:
            # Fallback: كل شيء بعد العنوان
            lines = [l.strip() for l in section.split('\n') if l.strip()]
            if len(lines) > 1:
                content = '\n'.join(lines[1:])
                content = SocialMediaParser._clean_text(content)
        
        if title and content:
            return SocialMediaContent(
                title=title,
                content=content,
                platform=platform
            )
        
        return None
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """تنظيف النص"""
        if not text:
            return ""
        
        # إزالة markdown
        text = re.sub(r'\*\*|\*|__|_|```|`', '', text)
        
        # إزالة HTML
        text = re.sub(r'<[^>]+>', '', text)
        
        # إزالة JSON artifacts
        text = re.sub(r'[{}\[\]]', '', text)
        
        # تنظيف المسافات
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
        """✅ توليد محتوى سوشيال ميديا لتقرير واحد"""
        print(f"\n{'='*70}")
        print(f"📱 Generating Social Media Content for Report #{report_id}")
        print(f"{'='*70}")
        
        report = self._fetch_report(report_id)
        if not report:
            print("❌ Report not found")
            return {'success': False, 'error': 'Report not found'}
        
        print(f"📰 Report: {report['title'][:50]}...")
        
        # فحص إذا في محتوى موجود
        existing_content = self._get_existing_content(report_id)
        
        if existing_content and not force_update:
            print(f"⏭️  Content already exists (ID: {existing_content['id']})")
            return {'success': True, 'skipped': True, 'content_id': existing_content['id']}
        
        # ✅ توليد المحتوى (برومبت واحد → 3 منشورات)
        all_content = self._generate_all_platforms(report)
        
        if not all_content or len(all_content) != 3:
            print("❌ Failed to generate content for all platforms")
            return {'success': False, 'error': 'Generation failed'}
        
        print(f"✅ Generated content for {len(all_content)} platforms")
        
        # الحفظ
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
                'platforms_count': len(all_content)
            }
        else:
            return {'success': False, 'error': f'Failed to {action.lower()}'}
    
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
    
    def _generate_all_platforms(self, report: Dict) -> Optional[Dict[str, SocialMediaContent]]:
        """✅ توليد محتوى لـ 3 منصات من برومبت واحد"""
        prompt = self._create_multi_platform_prompt(report)
        
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config={
                        'temperature': 0.8,
                        'max_output_tokens': 2048
                    }
                )
                
                result_text = response.text.strip()
                
                # استخراج المحتوى
                all_content = self.parser.parse_multi_platform(result_text)
                
                if not all_content:
                    print(f"   ⚠️  Could not parse, attempt {attempt + 1}/3")
                    time.sleep(2)
                    continue
                
                # التحقق من الصحة
                all_valid = True
                for platform, content in all_content.items():
                    is_valid, reason = content.is_valid()
                    if not is_valid:
                        print(f"   ⚠️  {platform}: {reason}")
                        all_valid = False
                
                if not all_valid:
                    print(f"   ⚠️  Validation failed, attempt {attempt + 1}/3")
                    time.sleep(2)
                    continue
                
                return all_content
                
            except Exception as e:
                print(f"   ⚠️  Error: {str(e)[:100]}")
                time.sleep(2)
        
        print(f"   ❌ Failed after 3 attempts")
        return None
    
    def _create_multi_platform_prompt(self, report: Dict) -> str:
        """✅ برومبت محسّن - يطلب 3 منشورات بوضوح"""
        
        return f"""أنت كاتب محتوى محترف لوسائل التواصل الاجتماعي.

📰 التقرير:
العنوان: {report['title']}
المحتوى: {report['content'][:1000]}...

═══════════════════════════════════════
المطلوب: اكتب 3 منشورات منفصلة
═══════════════════════════════════════

**قواعد مهمة:**
- كل منشور له عنوان + محتوى
- استخدم emojis مناسبة (2-3 فقط)
- أضف هاشتاقات في النهاية
- **مهم جداً:** ضع "_" بين كل كلمة في الهشتاق (مثال: #فلسطين_المحتلة)
- كل هاشتاق يبدأ بـ #

═══════════════════════════════════════
الشكل المطلوب بالضبط:
═══════════════════════════════════════

[FACEBOOK]
العنوان: عنوان جذاب (5-10 كلمات)
المحتوى: 
منشور Facebook هنا (400-600 حرف)
- أسلوب جذاب ومشوّق
- جملة افتتاحية قوية
- 3 هاشتاقات

[TWITTER]
العنوان: عنوان قصير (5-8 كلمات)
المحتوى:
منشور Twitter هنا (250-350 حرف)
- أسلوب مختصر وقوي
- 2 هاشتاقات

[INSTAGRAM]
العنوان: عنوان ملهم (5-10 كلمات)
المحتوى:
منشور Instagram هنا (350-500 حرف)
- أسلوب بصري وملهم
- 5 هاشتاقات

═══════════════════════════════════════
الآن اكتب المنشورات الثلاثة:
"""
    
    def _format_combined_content(self, all_content: Dict[str, SocialMediaContent]) -> str:
        """✅ تنسيق المحتوى المجمّع كـ JSON"""
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
        """✅ حفظ المحتوى المجمّع"""
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
        """✅ تحديث المحتوى المجمّع"""
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