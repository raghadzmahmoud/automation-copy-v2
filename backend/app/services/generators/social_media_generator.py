#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📱 Social Media Content Generator (Enhanced)
توليد محتوى سوشيال ميديا من التقارير

✅ التحسينات:
- Parser مرن يدعم أشكال متعددة
- نجاح جزئي (2 من 3 كافي)
- Fallback parsing
- Debug logging
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
        
        if not self.content or len(self.content.strip()) < 30:
            return False, "المحتوى قصير جداً"
        
        max_length = {
            'twitter': 400,
            'facebook': 900,
            'instagram': 700,   
        }.get(self.platform.lower(), 800)
        
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
    """✅ محلل محسّن - يدعم أشكال متعددة"""
    
    # ✅ أنماط مختلفة للمنصات
    PLATFORM_PATTERNS = {
        'facebook': [
            r'\[FACEBOOK\]',
            r'\[Facebook\]',
            r'\[فيسبوك\]',
            r'##?\s*Facebook',
            r'##?\s*فيسبوك',
            r'\*\*Facebook\*\*',
            r'\*\*فيسبوك\*\*',
            r'Facebook\s*:',
            r'فيسبوك\s*:',
            r'---\s*Facebook\s*---',
            r'1\.\s*Facebook',
            r'1\.\s*فيسبوك',
        ],
        'twitter': [
            r'\[TWITTER\]',
            r'\[Twitter\]',
            r'\[تويتر\]',
            r'\[X\]',
            r'##?\s*Twitter',
            r'##?\s*تويتر',
            r'\*\*Twitter\*\*',
            r'\*\*تويتر\*\*',
            r'Twitter\s*:',
            r'تويتر\s*:',
            r'Twitter/X',
            r'---\s*Twitter\s*---',
            r'2\.\s*Twitter',
            r'2\.\s*تويتر',
        ],
        'instagram': [
            r'\[INSTAGRAM\]',
            r'\[Instagram\]',
            r'\[انستغرام\]',
            r'\[انستجرام\]',
            r'##?\s*Instagram',
            r'##?\s*انستغرام',
            r'\*\*Instagram\*\*',
            r'\*\*انستغرام\*\*',
            r'Instagram\s*:',
            r'انستغرام\s*:',
            r'---\s*Instagram\s*---',
            r'3\.\s*Instagram',
            r'3\.\s*انستغرام',
        ]
    }
    
    @staticmethod
    def parse_multi_platform(text: str, debug: bool = False) -> Optional[Dict[str, SocialMediaContent]]:
        """
        ✅ استخراج محتوى المنصات من نص واحد
        يجرب عدة طرق للاستخراج
        """
        if debug:
            print(f"   🔍 Parsing text ({len(text)} chars)...")
            print(f"   🔍 Preview: {text[:200]}...")
        
        result = {}
        
        # الطريقة 1: البحث عن كل منصة بالـ patterns
        for platform in ['facebook', 'twitter', 'instagram']:
            content_obj = SocialMediaParser._find_platform_content(text, platform, debug)
            if content_obj:
                result[platform] = content_obj
                if debug:
                    print(f"   ✅ Found {platform}")
        
        # ✅ نجاح جزئي: 2 منصات أو أكثر
        if len(result) >= 2:
            return result
        
        # الطريقة 2: Fallback - تقسيم بالأرقام
        if len(result) < 2:
            fallback_result = SocialMediaParser._parse_numbered_format(text, debug)
            if fallback_result and len(fallback_result) >= 2:
                return fallback_result
        
        # الطريقة 3: Fallback - تقسيم بالخطوط
        if len(result) < 2:
            fallback_result = SocialMediaParser._parse_by_separators(text, debug)
            if fallback_result and len(fallback_result) >= 2:
                return fallback_result
        
        if debug:
            print(f"   ❌ Only found {len(result)} platforms")
        
        return result if len(result) >= 2 else None
    
    @staticmethod
    def _find_platform_content(text: str, platform: str, debug: bool = False) -> Optional[SocialMediaContent]:
        """البحث عن محتوى منصة معينة"""
        patterns = SocialMediaParser.PLATFORM_PATTERNS.get(platform, [])
        
        # البحث عن بداية القسم
        start_pos = -1
        matched_pattern = None
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if start_pos == -1 or match.start() < start_pos:
                    start_pos = match.start()
                    matched_pattern = pattern
        
        if start_pos == -1:
            return None
        
        # البحث عن نهاية القسم (بداية المنصة التالية)
        end_pos = len(text)
        for other_platform, other_patterns in SocialMediaParser.PLATFORM_PATTERNS.items():
            if other_platform == platform:
                continue
            for pattern in other_patterns:
                match = re.search(pattern, text[start_pos + 10:], re.IGNORECASE)
                if match:
                    potential_end = start_pos + 10 + match.start()
                    if potential_end < end_pos:
                        end_pos = potential_end
        
        # استخراج النص
        section = text[start_pos:end_pos].strip()
        
        # إزالة الـ header
        section = re.sub(r'^.*?[\]\:\n]', '', section, count=1).strip()
        
        return SocialMediaParser._extract_from_section(section, platform)
    
    @staticmethod
    def _parse_numbered_format(text: str, debug: bool = False) -> Optional[Dict[str, SocialMediaContent]]:
        """✅ Fallback: تقسيم بالأرقام 1. 2. 3."""
        result = {}
        platforms = ['facebook', 'twitter', 'instagram']
        
        # البحث عن أقسام مرقمة
        sections = re.split(r'\n\s*[123]\.\s*', text)
        
        if len(sections) >= 3:
            for i, section in enumerate(sections[1:4], 0):  # تخطي القسم الأول (قبل 1.)
                if i < len(platforms):
                    content_obj = SocialMediaParser._extract_from_section(section, platforms[i])
                    if content_obj:
                        result[platforms[i]] = content_obj
        
        return result if len(result) >= 2 else None
    
    @staticmethod
    def _parse_by_separators(text: str, debug: bool = False) -> Optional[Dict[str, SocialMediaContent]]:
        """✅ Fallback: تقسيم بالفواصل ---"""
        result = {}
        platforms = ['facebook', 'twitter', 'instagram']
        
        # البحث عن فواصل
        sections = re.split(r'\n\s*[-=]{3,}\s*\n', text)
        
        if len(sections) >= 3:
            for i, section in enumerate(sections[:3]):
                if i < len(platforms):
                    content_obj = SocialMediaParser._extract_from_section(section, platforms[i])
                    if content_obj:
                        result[platforms[i]] = content_obj
        
        return result if len(result) >= 2 else None
    
    @staticmethod
    def _extract_from_section(section: str, platform: str) -> Optional[SocialMediaContent]:
        """استخراج العنوان والمحتوى من قسم واحد"""
        if not section or len(section.strip()) < 20:
            return None
        
        # ✅ أنماط متعددة للعنوان
        title_patterns = [
            r'العنوان[:\s]+(.+?)(?=المحتوى|النص|$)',
            r'Title[:\s]+(.+?)(?=Content|المحتوى|$)',
            r'\*\*العنوان\*\*[:\s]*(.+?)(?=\*\*المحتوى|المحتوى|$)',
            r'\*\*Title\*\*[:\s]*(.+?)(?=\*\*Content|Content|$)',
            r'عنوان[:\s]+(.+?)(?=محتوى|نص|$)',
            r'📌\s*(.+?)(?=\n|$)',  # emoji marker
            r'🔹\s*(.+?)(?=\n|$)',
        ]
        
        title = None
        title_end_pos = 0
        
        for pattern in title_patterns:
            match = re.search(pattern, section, re.DOTALL | re.IGNORECASE)
            if match:
                title = SocialMediaParser._clean_text(match.group(1))
                title_end_pos = match.end()
                if title and len(title) > 5 and len(title) < 200:
                    break
                else:
                    title = None
        
        # Fallback: أول سطر غير فارغ
        if not title:
            lines = [l.strip() for l in section.split('\n') if l.strip()]
            for line in lines:
                cleaned = SocialMediaParser._clean_text(line)
                # تجاهل الأسطر القصيرة جداً أو الطويلة
                if cleaned and 5 < len(cleaned) < 150:
                    # تجاهل إذا كان يبدو كـ label
                    if not re.match(r'^(العنوان|المحتوى|Title|Content|النص)[:\s]*$', cleaned, re.IGNORECASE):
                        title = cleaned
                        break
        
        # ✅ أنماط متعددة للمحتوى
        content_patterns = [
            r'المحتوى[:\s]+(.+)',
            r'Content[:\s]+(.+)',
            r'\*\*المحتوى\*\*[:\s]*(.+)',
            r'النص[:\s]+(.+)',
            r'محتوى[:\s]+(.+)',
        ]
        
        content = None
        for pattern in content_patterns:
            match = re.search(pattern, section, re.DOTALL | re.IGNORECASE)
            if match:
                content = SocialMediaParser._clean_text(match.group(1))
                if content and len(content) > 30:
                    break
                else:
                    content = None
        
        # Fallback: كل شيء بعد العنوان
        if not content and title:
            lines = [l.strip() for l in section.split('\n') if l.strip()]
            # إيجاد موقع العنوان
            title_idx = -1
            for i, line in enumerate(lines):
                if title in line or line in title:
                    title_idx = i
                    break
            
            if title_idx >= 0 and title_idx < len(lines) - 1:
                content_lines = []
                for line in lines[title_idx + 1:]:
                    # تخطي labels
                    if not re.match(r'^(المحتوى|Content|النص)[:\s]*$', line, re.IGNORECASE):
                        content_lines.append(line)
                content = '\n'.join(content_lines)
                content = SocialMediaParser._clean_text(content)
        
        # آخر Fallback: كل القسم ماعدا السطر الأول
        if not content:
            lines = [l.strip() for l in section.split('\n') if l.strip()]
            if len(lines) > 1:
                content = '\n'.join(lines[1:])
                content = SocialMediaParser._clean_text(content)
        
        if title and content and len(content) > 30:
            return SocialMediaContent(
                title=title[:200],  # تحديد طول العنوان
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
        
        # إزالة labels في بداية النص
        text = re.sub(r'^(العنوان|المحتوى|Title|Content|النص)[:\s]*', '', text, flags=re.IGNORECASE)
        
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
            'facebook': {'name': 'Facebook', 'max_length': 900, 'style': 'جذاب ومشوّق', 'hashtags': 3},
            'twitter': {'name': 'Twitter/X', 'max_length': 400, 'style': 'مختصر وقوي', 'hashtags': 2},
            'instagram': {'name': 'Instagram', 'max_length': 700, 'style': 'بصري وملهم', 'hashtags': 5}
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
        
        existing_content = self._get_existing_content(report_id)
        
        if existing_content and not force_update:
            print(f"⏭️  Content already exists (ID: {existing_content['id']})")
            return {'success': True, 'skipped': True, 'content_id': existing_content['id']}
        
        # ✅ توليد المحتوى
        all_content = self._generate_all_platforms(report)
        
        # ✅ نجاح جزئي: 2 منصات أو أكثر
        if not all_content or len(all_content) < 2:
            print(f"❌ Failed to generate content (got {len(all_content) if all_content else 0} platforms, need 2+)")
            return {'success': False, 'error': 'Generation failed'}
        
        print(f"✅ Generated content for {len(all_content)}/3 platforms")
        
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
                'platforms_count': len(all_content),
                'platforms': list(all_content.keys())
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
            'updated': 0,
            'partial': 0  # ✅ جديد: نجاح جزئي
        }
        
        for i, report in enumerate(reports, 1):
            print(f"\n[{i}/{len(reports)}] Report #{report['id']}")
            
            try:
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
                        # ✅ تتبع النجاح الجزئي
                        if result.get('platforms_count', 3) < 3:
                            total_stats['partial'] += 1
                else:
                    total_stats['failed'] += 1
                    
            except Exception as e:
                print(f"   ❌ Unexpected error: {e}")
                total_stats['failed'] += 1
                continue
        
        print(f"\n{'='*70}")
        print(f"📊 Final Results:")
        print(f"   • Reports: {total_stats['total_reports']}")
        print(f"   • Created: {total_stats['success']} ({total_stats['partial']} partial)")
        print(f"   • Updated: {total_stats['updated']}")
        print(f"   • Skipped: {total_stats['skipped']}")
        print(f"   • Failed: {total_stats['failed']}")
        print(f"{'='*70}")
        
        return total_stats
    
    def _generate_all_platforms(self, report: Dict) -> Optional[Dict[str, SocialMediaContent]]:
        """✅ توليد محتوى لـ 3 منصات من برومبت واحد"""
        
        for attempt in range(3):
            try:
                # ✅ تغيير الـ prompt في كل محاولة
                prompt = self._create_multi_platform_prompt(report, attempt=attempt)
                
                # ✅ زيادة temperature تدريجياً
                temp = 0.5 + (attempt * 0.1)  # 0.5, 0.6, 0.7
                
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config={
                        'temperature': temp,
                        'max_output_tokens': 2500
                    }
                )
                
                result_text = response.text.strip()
                
                # ✅ Debug: طباعة جزء من الرد
                print(f"   📝 Response preview (attempt {attempt + 1}, temp={temp:.1f}): {result_text[:150]}...")
                
                # استخراج المحتوى
                all_content = self.parser.parse_multi_platform(result_text, debug=(attempt >= 1))
                
                if not all_content or len(all_content) < 2:
                    print(f"   ⚠️  Could not parse ({len(all_content) if all_content else 0} platforms), attempt {attempt + 1}/3")
                    time.sleep(2)
                    continue
                
                # ✅ Validation مع تسامح
                valid_content = {}
                for platform, content in all_content.items():
                    is_valid, reason = content.is_valid()
                    if is_valid:
                        valid_content[platform] = content
                    else:
                        print(f"   ⚠️  {platform}: {reason}")
                
                # ✅ 2 منصات صالحة كافية
                if len(valid_content) >= 2:
                    print(f"   ✅ Successfully generated {len(valid_content)} platforms")
                    return valid_content
                
                print(f"   ⚠️  Only {len(valid_content)} valid platforms, attempt {attempt + 1}/3")
                time.sleep(2)
                
            except Exception as e:
                print(f"   ⚠️  Error: {str(e)[:100]}")
                time.sleep(2)
        
        print(f"   ❌ Failed after 3 attempts - trying fallback strategy")
        
        # ✅ Fallback: توليد كل منصة لوحدها
        return self._generate_platforms_individually(report)
    
    def _generate_platforms_individually(self, report: Dict) -> Optional[Dict[str, SocialMediaContent]]:
        """✅ Fallback: توليد كل منصة لوحدها"""
        print(f"   🔄 Trying individual platform generation...")
        
        all_content = {}
        platforms = ['facebook', 'twitter', 'instagram']
        
        for platform in platforms:
            content = self._generate_single_platform(report, platform)
            if content:
                is_valid, reason = content.is_valid()
                if is_valid:
                    all_content[platform] = content
                    print(f"   ✅ Generated {platform}")
                else:
                    print(f"   ⚠️  {platform}: {reason}")
            else:
                print(f"   ❌ Failed to generate {platform}")
            
            time.sleep(1)  # تجنب rate limiting
        
        if len(all_content) >= 2:
            print(f"   ✅ Fallback successful: {len(all_content)} platforms")
            return all_content
        
        print(f"   ❌ Fallback failed: only {len(all_content)} platforms")
        return None
    
    def _generate_single_platform(self, report: Dict, platform: str) -> Optional[SocialMediaContent]:
        """✅ توليد محتوى لمنصة واحدة فقط"""
        
        # تحديد المتطلبات حسب المنصة
        if platform == 'facebook':
            length = "400-700 حرف"
            style = "جذاب ومفصل"
            hashtags = "3 هاشتاقات"
        elif platform == 'twitter':
            length = "200-350 حرف"
            style = "مختصر ومباشر"
            hashtags = "2 هاشتاقات"
        else:  # instagram
            length = "400-600 حرف"
            style = "بصري وملهم"
            hashtags = "5 هاشتاقات"
        
        prompt = f"""أنت كاتب محتوى محترف لـ {platform.upper()}.

📰 التقرير:
العنوان: {report['title']}
المحتوى: {report['content'][:1200]}

اكتب منشور {platform.upper()} بالشكل التالي:

العنوان: (عنوان جذاب من 5-12 كلمة)
المحتوى: (منشور {length}، أسلوب {style}، {hashtags})

قواعد:
✅ استخدم 2-3 emojis مناسبة
✅ الهاشتاقات: ضع _ بين الكلمات (مثال: #فلسطين_الحرة)
✅ اكتب بأسلوب {style}
"""
        
        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={
                    'temperature': 0.6,
                    'max_output_tokens': 1000
                }
            )
            
            result_text = response.text.strip()
            
            # استخراج العنوان والمحتوى
            title_match = re.search(r'العنوان[:\s]+(.+?)(?=المحتوى|النص|$)', result_text, re.DOTALL | re.IGNORECASE)
            content_match = re.search(r'(?:المحتوى|النص)[:\s]+(.+?)$', result_text, re.DOTALL | re.IGNORECASE)
            
            if title_match and content_match:
                title = title_match.group(1).strip()
                content = content_match.group(1).strip()
                
                # تنظيف
                title = re.sub(r'\*\*|\n', ' ', title).strip()
                content = re.sub(r'\*\*', '', content).strip()
                
                return SocialMediaContent(
                    platform=platform,
                    title=title,
                    content=content
                )
        
        except Exception as e:
            print(f"   ⚠️  Error generating {platform}: {str(e)[:100]}")
        
        return None
    
    def _create_multi_platform_prompt(self, report: Dict, attempt: int = 0) -> str:
        """✅ برومبت محسّن وأوضح مع تنويع في المحاولات"""
        
        # ✅ تنويع الـ prompt في المحاولات المختلفة
        if attempt == 0:
            instruction = "⚠️ مهم جداً: يجب أن تكتب محتوى للمنصات الثلاث (FACEBOOK و TWITTER و INSTAGRAM) بالضبط!"
        elif attempt == 1:
            instruction = "⚠️ تحذير: يجب كتابة 3 منصات كاملة! لا تكتب منصة واحدة فقط!"
        else:
            instruction = "⚠️ هذه المحاولة الأخيرة: اكتب المنصات الثلاث كاملة وإلا سيفشل الطلب!"
        
        return f"""أنت كاتب محتوى محترف لوسائل التواصل الاجتماعي.

📰 التقرير:
العنوان: {report['title']}
المحتوى: {report['content'][:1200]}

═══════════════════════════════════════════════════════════════
{instruction}
═══════════════════════════════════════════════════════════════

يجب أن تكتب بالشكل التالي بالضبط (3 منصات كاملة):

[FACEBOOK]
العنوان: (عنوان جذاب من 5-12 كلمة)
المحتوى: (منشور من 400-700 حرف، أسلوب جذاب، 3 هاشتاقات)

[TWITTER]
العنوان: (عنوان قصير من 5-8 كلمات)
المحتوى: (منشور من 200-350 حرف، أسلوب مختصر، 2 هاشتاقات)

[INSTAGRAM]
العنوان: (عنوان ملهم من 5-10 كلمات)
المحتوى: (منشور من 400-600 حرف، أسلوب بصري، 5 هاشتاقات)

═══════════════════════════════════════════════════════════════
قواعد إلزامية:
✅ استخدم [FACEBOOK] و [TWITTER] و [INSTAGRAM] بالضبط كما هي (بالأحرف الكبيرة)
✅ كل منصة يجب أن تحتوي على "العنوان:" و "المحتوى:"
✅ استخدم 2-3 emojis مناسبة في كل منشور
✅ الهاشتاقات: ضع _ بين الكلمات (مثال: #فلسطين_الحرة)
✅ يجب كتابة المنصات الثلاث كاملة - لا تكتب منصة واحدة فقط!
═══════════════════════════════════════════════════════════════

ابدأ الآن بكتابة المنصات الثلاث:
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
                SELECT gr.id, gr.title, gr.content, gr.updated_at
                FROM generated_report gr
                WHERE gr.status = 'draft'
                    AND NOT EXISTS (
                        SELECT 1 FROM generated_content gc 
                        WHERE gc.report_id = gr.id AND gc.content_type_id = 1
                    )
                ORDER BY gr.created_at DESC
                LIMIT %s
            """
            self.cursor.execute(query, (limit,))
            return [{'id': r[0], 'title': r[1], 'content': r[2], 'updated_at': r[3]} for r in self.cursor.fetchall()]
        except Exception as e:
            print(f"   ❌ Error fetching reports: {e}")
            return []
    
    def _fetch_recent_reports(self, limit: int = 10) -> List[Dict]:
        """جلب التقارير الأخيرة"""
        try:
            query = """
                SELECT id, title, content, updated_at
                FROM generated_report WHERE status = 'draft'
                ORDER BY updated_at DESC LIMIT %s
            """
            self.cursor.execute(query, (limit,))
            return [{'id': r[0], 'title': r[1], 'content': r[2], 'updated_at': r[3]} for r in self.cursor.fetchall()]
        except:
            return []
    
    def _get_existing_content(self, report_id: int) -> Optional[Dict]:
        """جلب المحتوى الموجود"""
        try:
            self.cursor.execute("""
                SELECT id, content, updated_at
                FROM generated_content
                WHERE report_id = %s AND content_type_id = 1
                LIMIT 1
            """, (report_id,))
            row = self.cursor.fetchone()
            return {'id': row[0], 'content': row[1], 'updated_at': row[2]} if row else None
        except:
            return None
    
    def _save_combined_content(self, report_id: int, all_content: Dict[str, SocialMediaContent]) -> bool:
        """✅ حفظ المحتوى المجمّع"""
        try:
            combined_content = self._format_combined_content(all_content)
            platforms_str = ', '.join(all_content.keys())
            
            self.cursor.execute("""
                INSERT INTO generated_content (
                    report_id, content_type_id, title, description,
                    content, status, created_at, updated_at
                )
                VALUES (%s, 1, %s, %s, %s, 'draft', NOW(), NOW())
            """, (report_id, "Social Media Content", f"Posts for: {platforms_str}", combined_content))
            
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
            platforms_str = ', '.join(all_content.keys())
            
            self.cursor.execute("""
                UPDATE generated_content
                SET content = %s, description = %s, updated_at = NOW()
                WHERE id = %s
            """, (combined_content, f"Posts for: {platforms_str}", content_id))
            
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


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        report_id = int(sys.argv[1])
        generator = SocialMediaGenerator()
        result = generator.generate_for_report(report_id, force_update=True)
        print(f"\nResult: {result}")
        generator.close()
    else:
        print("Usage: python social_media_generator.py <report_id>")