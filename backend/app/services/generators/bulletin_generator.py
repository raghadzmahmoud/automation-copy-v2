#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📻 Bulletin Generator V4
توليد النشرة الإخبارية - نسخة محسّنة

التحسينات:
- Summary أطول وكامل (فقرة كاملة لكل خبر)
- تقسيم الأخبار حسب الأقسام (محلياً، دولياً، شؤون الأسرى...)
- Structure يتبع الأمثلة الحقيقية
- أبرز 3 عناوين بناءً على الأولويات
"""

import os
import json
import re
from datetime import datetime, timezone, date
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import psycopg2
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ============================================
# Configuration
# ============================================

DB_CONFIG = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 5432))
}

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')

# أقسام النشرة بالترتيب (الترتيب مهم - الأولوية للأخص)
BULLETIN_SECTIONS = [
    # فلسطين أولاً
    {'key': 'gaza', 'name': 'في غزة', 'keywords': ['غزة', 'القطاع', 'حماس', 'خان يونس', 'رفح', 'جباليا', 'الشجاعية', 'النصيرات', 'المغازي', 'دير البلح']},
    {'key': 'jerusalem', 'name': 'في القدس', 'keywords': ['القدس', 'الأقصى', 'المسجد الأقصى', 'باب العامود', 'سلوان', 'الشيخ جراح']},
    {'key': 'westbank', 'name': 'في الضفة الغربية', 'keywords': ['الضفة الغربية', 'نابلس', 'جنين', 'الخليل', 'رام الله', 'بيت لحم', 'طولكرم', 'قلقيلية', 'سلفيت', 'أريحا', 'طوباس']},
    {'key': 'prisoners', 'name': 'في شؤون الأسرى', 'keywords': ['أسرى', 'أسير', 'معتقل', 'سجن', 'محرر', 'النقب', 'عوفر', 'مجدو']},
    {'key': 'local', 'name': 'محلياً', 'keywords': ['السلطة الفلسطينية', 'الحكومة الفلسطينية', 'وزارة فلسطينية', 'فلسطيني', 'فلسطينية']},
    
    # دولي وعربي (الدولي قبل العربي لأن إيران/تركيا دولي)
    {'key': 'international', 'name': 'دولياً', 'keywords': ['أمريكا', 'أمريكي', 'واشنطن', 'البيت الأبيض', 'روسيا', 'روسي', 'موسكو', 'الصين', 'صيني', 'بكين', 'أوروبا', 'أوروبي', 'الاتحاد الأوروبي', 'بريطانيا', 'فرنسا', 'ألمانيا', 'الأمم المتحدة', 'مجلس الأمن', 'إيران', 'إيراني', 'طهران', 'تركيا', 'تركي', 'أنقرة', 'إسرائيل', 'إسرائيلي', 'تل أبيب', 'الكنيست', 'نتنياهو']},
    {'key': 'arab', 'name': 'عربياً', 'keywords': ['مصر', 'مصري', 'القاهرة', 'الأردن', 'أردني', 'عمان', 'السعودية', 'سعودي', 'الرياض', 'الإمارات', 'إماراتي', 'أبوظبي', 'دبي', 'قطر', 'قطري', 'الدوحة', 'لبنان', 'لبناني', 'بيروت', 'سوريا', 'سوري', 'دمشق', 'العراق', 'عراقي', 'بغداد', 'اليمن', 'يمني', 'صنعاء', 'الكويت', 'البحرين', 'عمان', 'المغرب', 'الجزائر', 'تونس', 'ليبيا', 'السودان']},
    
    # رياضة ومنوعات
    {'key': 'sports', 'name': 'رياضياً', 'keywords': ['رياضة', 'رياضي', 'كرة القدم', 'مباراة', 'دوري', 'منتخب', 'لاعب', 'مدرب', 'بطولة', 'كأس', 'أولمبياد']},
    {'key': 'other', 'name': '', 'keywords': []}
]

# أولويات العناوين البارزة
HEADLINE_PRIORITIES = [
    ('غزة', 1), ('شهيد', 1), ('شهداء', 1), ('استشهاد', 1), ('مجزرة', 1),
    ('اغتيال', 2), ('قصف', 2), ('عدوان', 2), ('غارة', 2),
    ('اقتحام', 3), ('مستوطن', 3), ('الأقصى', 3),
    ('القدس', 4), ('الضفة', 4),
    ('أسرى', 5), ('اعتقال', 5),
    ('فلسطين', 6)
]

DEFAULT_CURRENCY = {'USD': 3.65, 'JOD': 5.15, 'EUR': 3.95}


# ============================================
# Data Classes
# ============================================

@dataclass
class ReportItem:
    id: int
    title: str
    content: str
    summary: str = ""
    section: str = "other"
    priority: int = 10


@dataclass
class BulletinResult:
    success: bool
    bulletin_id: Optional[int] = None
    message: str = ""
    news_count: int = 0
    word_count: int = 0
    duration_seconds: int = 0


# ============================================
# Bulletin Generator Class
# ============================================

class BulletinGenerator:
    
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cursor = self.conn.cursor()
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        print("✅ Connected to DB and Gemini")
    
    
    def generate_bulletin(
        self,
        bulletin_type: str = "صباحية",
        report_count: int = 12,
        hours_back: int = 48,
        report_ids: List[int] = None,
        custom_weather: str = None,
        custom_currency: Dict[str, float] = None
    ) -> BulletinResult:
        """توليد نشرة إخبارية كاملة"""
        
        print("\n" + "="*70)
        print(f"📻 توليد نشرة {bulletin_type}")
        print("="*70)
        
        # 1. جلب التقارير
        print("\n📥 Step 1: جلب التقارير...")
        if report_ids:
            reports = self._fetch_reports_by_ids(report_ids)
        else:
            reports = self._fetch_recent_reports(report_count, hours_back)
        
        if len(reports) < 5:
            return BulletinResult(False, message=f"عدد التقارير غير كافٍ ({len(reports)})")
        
        print(f"   ✅ تم جلب {len(reports)} تقرير")
        
        # 2. تصنيف التقارير حسب الأقسام وحساب الأولوية
        print("\n📂 Step 2: تصنيف التقارير...")
        reports = self._classify_reports(reports)
        print(f"   ✅ تم تصنيف التقارير")
        
        # 3. إعادة كتابة كل تقرير للنشرة (فقرة كاملة)
        print("\n📝 Step 3: إعادة صياغة التقارير للنشرة...")
        reports = self._rewrite_reports_for_bulletin(reports)
        print(f"   ✅ تم إعادة صياغة {len(reports)} تقرير")
        
        # 4. اختيار أبرز 3 عناوين
        print("\n🎯 Step 4: اختيار أبرز العناوين...")
        top_headlines = self._select_top_headlines(reports)
        print(f"   ✅ العناوين البارزة:")
        for i, h in enumerate(top_headlines, 1):
            print(f"      {i}. {h['title'][:60]}...")
        
        # 5. بناء النشرة الكاملة
        print("\n📄 Step 5: بناء النشرة...")
        currency = custom_currency or DEFAULT_CURRENCY
        weather = custom_weather or self._get_default_weather()
        
        full_script, sections_data = self._build_full_bulletin(
            bulletin_type=bulletin_type,
            top_headlines=top_headlines,
            reports=reports,
            currency=currency,
            weather=weather
        )
        
        word_count = len(full_script.split())
        duration_seconds = int((word_count / 150) * 60)
        
        print(f"   ✅ النشرة جاهزة: {word_count} كلمة، {duration_seconds//60} دقيقة")
        
        # 6. حفظ في DB
        print("\n💾 Step 6: حفظ النشرة...")
        result = self._save_bulletin(
            bulletin_type=bulletin_type,
            top_headlines=top_headlines,
            reports=reports,
            sections_data=sections_data,
            full_script=full_script,
            currency=currency,
            weather=weather,
            word_count=word_count,
            duration_seconds=duration_seconds
        )
        
        if result.success:
            print(f"   ✅ تم الحفظ بـ ID: {result.bulletin_id}")
        
        return result
    
    
    # ==========================================
    # Step 1: جلب التقارير
    # ==========================================
    
    def _fetch_recent_reports(self, limit: int, hours_back: int) -> List[ReportItem]:
        query = """
            SELECT id, title, content
            FROM generated_report
            WHERE created_at >= NOW() - INTERVAL '%s hours'
              AND content IS NOT NULL
              AND LENGTH(content) > 100
            ORDER BY created_at DESC
            LIMIT %s
        """
        self.cursor.execute(query, (hours_back, limit))
        return [ReportItem(id=r[0], title=r[1], content=r[2]) for r in self.cursor.fetchall()]
    
    def _fetch_reports_by_ids(self, ids: List[int]) -> List[ReportItem]:
        query = """
            SELECT id, title, content
            FROM generated_report
            WHERE id = ANY(%s)
            ORDER BY created_at DESC
        """
        self.cursor.execute(query, (ids,))
        return [ReportItem(id=r[0], title=r[1], content=r[2]) for r in self.cursor.fetchall()]
    
    
    # ==========================================
    # Step 2: تصنيف التقارير
    # ==========================================
    
    def _classify_reports(self, reports: List[ReportItem]) -> List[ReportItem]:
        """تصنيف كل تقرير حسب القسم وحساب الأولوية"""
        
        for report in reports:
            # البحث في العنوان أولاً (أهم)
            title_lower = report.title.lower()
            content_lower = report.content.lower() if report.content else ""
            
            # تحديد القسم - الأولوية للعنوان
            report.section = "other"
            
            # البحث في العنوان أولاً
            for section in BULLETIN_SECTIONS:
                for keyword in section['keywords']:
                    if keyword in title_lower:
                        report.section = section['key']
                        break
                if report.section != "other":
                    break
            
            # إذا لم نجد في العنوان، نبحث في المحتوى
            if report.section == "other":
                for section in BULLETIN_SECTIONS:
                    for keyword in section['keywords']:
                        if keyword in content_lower:
                            report.section = section['key']
                            break
                    if report.section != "other":
                        break
            
            # حساب الأولوية - نفس المنطق
            report.priority = 10
            text = title_lower + " " + content_lower
            for keyword, priority in HEADLINE_PRIORITIES:
                if keyword in text:
                    report.priority = min(report.priority, priority)
        
        # ترتيب حسب الأولوية
        reports.sort(key=lambda x: x.priority)
        
        return reports
    
    
    # ==========================================
    # Step 3: إعادة صياغة التقارير
    # ==========================================
    
    def _rewrite_reports_for_bulletin(self, reports: List[ReportItem]) -> List[ReportItem]:
        """إعادة صياغة كل تقرير كفقرة كاملة للنشرة"""
        
        for i, report in enumerate(reports, 1):
            print(f"   [{i}/{len(reports)}] {report.title[:50]}...")
            
            prompt = f"""أعد صياغة هذا التقرير الإخباري كفقرة إذاعية كاملة للنشرة.

العنوان: {report.title}

التقرير الأصلي:
{report.content}

التعليمات المهمة:
1. اكتب فقرة واحدة كاملة ومتماسكة (6-10 جمل على الأقل)
2. يجب أن تكون الفقرة كاملة وغير مقطوعة - تأكد من إنهاء كل جملة بشكل صحيح
3. ابدأ بالمعلومة الأهم ثم التفاصيل
4. استخدم لغة عربية فصحى واضحة للقراءة الإذاعية
5. حافظ على جميع الأرقام والأسماء والتواريخ الموجودة في التقرير
6. لا تضف معلومات غير موجودة في التقرير الأصلي
7. اجعل الفقرة مناسبة للقراءة الصوتية (بدون اختصارات أو رموز أو نجوم)
8. لا تكتب عنواناً، فقط الفقرة
9. تأكد من أن الفقرة مكتملة ولا تنتهي بكلمة ناقصة

الفقرة الإذاعية الكاملة:"""

            try:
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config={'temperature': 0.3, 'max_output_tokens': 3000}
                )
                report.summary = response.text.strip()
                
                # تنظيف
                report.summary = re.sub(r'^#+\s*', '', report.summary)
                report.summary = re.sub(r'\*\*|\*', '', report.summary)
                report.summary = re.sub(r'^الفقرة الإذاعية:?\s*', '', report.summary)
                report.summary = re.sub(r'^الفقرة:?\s*', '', report.summary)
                
                # التأكد من اكتمال النص (لا ينتهي بحرف ناقص)
                if report.summary and not report.summary.rstrip().endswith(('.', '؟', '!', '،')):
                    # إذا كان مقطوعاً، نحاول إكماله أو نضيف نقطة
                    last_period = max(
                        report.summary.rfind('.'),
                        report.summary.rfind('؟'),
                        report.summary.rfind('!')
                    )
                    if last_period > len(report.summary) * 0.7:  # إذا كان آخر 30% فقط ناقص
                        report.summary = report.summary[:last_period + 1]
                    else:
                        report.summary = report.summary.rstrip() + '.'
                
            except Exception as e:
                print(f"      ⚠️ خطأ: {e}")
                report.summary = report.content[:800]
            
            # تحديث في DB
            self._update_report_summary(report.id, report.summary)
        
        return reports
    
    def _update_report_summary(self, report_id: int, summary: str):
        try:
            self.cursor.execute(
                "UPDATE generated_report SET bulletin_summary = %s WHERE id = %s",
                (summary, report_id)
            )
            self.conn.commit()
        except:
            self.conn.rollback()
    
    
    # ==========================================
    # Step 4: اختيار أبرز العناوين
    # ==========================================
    
    def _select_top_headlines(self, reports: List[ReportItem]) -> List[Dict]:
        """اختيار أبرز 3 عناوين بناءً على الأولوية"""
        
        # التقارير مرتبة مسبقاً بالأولوية
        top_3 = reports[:3]
        
        return [
            {'report_id': r.id, 'title': r.title, 'rank': i+1, 'priority': r.priority}
            for i, r in enumerate(top_3)
        ]
    
    
    # ==========================================
    # Step 5: بناء النشرة الكاملة
    # ==========================================
    
    def _build_full_bulletin(
        self,
        bulletin_type: str,
        top_headlines: List[Dict],
        reports: List[ReportItem],
        currency: Dict[str, float],
        weather: str
    ) -> Tuple[str, Dict]:
        """بناء النص الكامل للنشرة بـ structure صحيح"""
        
        today = datetime.now()
        date_ar = self._format_date_arabic(today)
        
        lines = []
        sections_data = {}
        
        # ═══════════════════════════════════════
        # الترويسة
        # ═══════════════════════════════════════
        lines.append(f"نشرة أخبار {bulletin_type}")
        lines.append("")
        
        # ═══════════════════════════════════════
        # الافتتاحية + أبرز العناوين
        # ═══════════════════════════════════════
        lines.append(f"أهلاً بكم مستمعينا الكرام في نشرة إخبارية مفصلة ليوم {date_ar}، نستهلها بأبرز العناوين:")
        lines.append("")
        
        for h in top_headlines:
            lines.append(f"• {h['title']}")
        
        lines.append("")
        lines.append("أهلاً بكم إلى التفاصيل")
        lines.append("")
        
        # ═══════════════════════════════════════
        # الأخبار مقسمة حسب الأقسام
        # ═══════════════════════════════════════
        
        # تجميع التقارير حسب القسم
        reports_by_section = {}
        for report in reports:
            if report.section not in reports_by_section:
                reports_by_section[report.section] = []
            reports_by_section[report.section].append(report)
        
        # كتابة كل قسم
        section_order = ['gaza', 'westbank', 'jerusalem', 'prisoners', 'local', 'arab', 'international', 'sports', 'other']
        
        for section_key in section_order:
            if section_key not in reports_by_section:
                continue
            
            section_reports = reports_by_section[section_key]
            section_info = next((s for s in BULLETIN_SECTIONS if s['key'] == section_key), None)
            
            # عنوان القسم (إذا كان له اسم)
            if section_info and section_info['name']:
                lines.append(section_info['name'])
                lines.append("")
            
            # أخبار القسم
            sections_data[section_key] = []
            for report in section_reports:
                lines.append(f"({report.title})")
                lines.append(report.summary)
                lines.append("")
                
                sections_data[section_key].append({
                    'report_id': report.id,
                    'title': report.title
                })
        
        # ═══════════════════════════════════════
        # أسعار العملات
        # ═══════════════════════════════════════
        lines.append("في أسعار العملات")
        lines.append(f"الدولار الأمريكي: {currency['USD']} شيكل")
        lines.append(f"الدينار الأردني: {currency['JOD']} شيكل")
        lines.append(f"اليورو: {currency['EUR']} شيكل")
        lines.append("")
        
        # ═══════════════════════════════════════
        # حالة الطقس
        # ═══════════════════════════════════════
        lines.append("في حالة الطقس")
        lines.append(weather)
        lines.append("")
        
        # ═══════════════════════════════════════
        # إعادة أبرز العناوين
        # ═══════════════════════════════════════
        lines.append("نعود ونذكركم بأبرز عناوين نشرتنا:")
        for h in top_headlines:
            lines.append(f"• {h['title']}")
        
        lines.append("")
        lines.append("كانت هذه نشرتنا الإخبارية، دمتم بخير وفي أمان الله.")
        
        return "\n".join(lines), sections_data
    
    
    def _format_date_arabic(self, dt: datetime) -> str:
        days = ['الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
        months = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
                  'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
        return f"{days[dt.weekday()]} {dt.day} {months[dt.month-1]} {dt.year}"
    
    
    def _get_default_weather(self) -> str:
        month = datetime.now().month
        if month in [12, 1, 2]:
            return "يكون الجو بارداً إلى شديد البرودة، غائماً جزئياً مع احتمال سقوط أمطار متفرقة على بعض المناطق، والرياح شمالية غربية معتدلة السرعة."
        elif month in [6, 7, 8]:
            return "يكون الجو حاراً إلى شديد الحرارة، صافياً بشكل عام، ويطرأ ارتفاع على درجات الحرارة لتصبح أعلى من معدلها السنوي."
        else:
            return "يكون الجو معتدلاً في المناطق الجبلية، دافئاً في بقية المناطق، غائماً جزئياً إلى صاف."
    
    
    # ==========================================
    # Step 6: حفظ النشرة
    # ==========================================
    
    def _save_bulletin(
        self,
        bulletin_type: str,
        top_headlines: List[Dict],
        reports: List[ReportItem],
        sections_data: Dict,
        full_script: str,
        currency: Dict,
        weather: str,
        word_count: int,
        duration_seconds: int
    ) -> BulletinResult:
        
        try:
            # تجهيز news_items
            news_items = [
                {
                    'report_id': r.id,
                    'title': r.title,
                    'summary': r.summary,
                    'section': r.section,
                    'priority': r.priority,
                    'order': i + 1
                }
                for i, r in enumerate(reports)
            ]
            
            content = {
                'top_headlines': top_headlines,
                'news_items': news_items,
                'sections': sections_data,
                'currency': currency,
                'weather': weather,
                'news_count': len(reports),
                'word_count': word_count
            }
            
            # إدراج أو تحديث النشرة (UPSERT)
            self.cursor.execute("""
                INSERT INTO news_bulletins 
                (bulletin_type, broadcast_date, content, full_script, estimated_duration_seconds, status)
                VALUES (%s, %s, %s, %s, %s, 'ready')
                ON CONFLICT (broadcast_date, bulletin_type) 
                DO UPDATE SET 
                    content = EXCLUDED.content,
                    full_script = EXCLUDED.full_script,
                    estimated_duration_seconds = EXCLUDED.estimated_duration_seconds,
                    status = EXCLUDED.status,
                    updated_at = NOW()
                RETURNING id
            """, (
                bulletin_type,
                date.today(),
                json.dumps(content, ensure_ascii=False),
                full_script,
                duration_seconds
            ))
            
            bulletin_id = self.cursor.fetchone()[0]
            
            # حذف الروابط القديمة
            self.cursor.execute(
                "DELETE FROM bulletin_reports WHERE bulletin_id = %s",
                (bulletin_id,)
            )
            
            # ربط التقارير
            for i, report in enumerate(reports):
                is_headline = any(h['report_id'] == report.id for h in top_headlines)
                headline_rank = None
                if is_headline:
                    for h in top_headlines:
                        if h['report_id'] == report.id:
                            headline_rank = h['rank']
                            break
                
                self.cursor.execute("""
                    INSERT INTO bulletin_reports 
                    (bulletin_id, report_id, is_top_headline, headline_rank, display_order)
                    VALUES (%s, %s, %s, %s, %s)
                """, (bulletin_id, report.id, is_headline, headline_rank, i + 1))
            
            self.conn.commit()
            
            return BulletinResult(
                success=True,
                bulletin_id=bulletin_id,
                message=f"تم إنشاء النشرة بنجاح (ID: {bulletin_id})",
                news_count=len(reports),
                word_count=word_count,
                duration_seconds=duration_seconds
            )
            
        except Exception as e:
            self.conn.rollback()
            return BulletinResult(False, message=f"خطأ في الحفظ: {str(e)}")
    
    
    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("🔒 تم إغلاق الاتصالات")


# ============================================
# Standalone Function
# ============================================

def generate_bulletin(bulletin_type: str = "صباحية", **kwargs) -> BulletinResult:
    gen = BulletinGenerator()
    try:
        return gen.generate_bulletin(bulletin_type=bulletin_type, **kwargs)
    finally:
        gen.close()


# ============================================
# Test
# ============================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🧪 اختبار توليد النشرة V4")
    print("="*70)
    
    gen = BulletinGenerator()
    
    try:
        result = gen.generate_bulletin(
            bulletin_type="صباحية",
            report_count=12,
            hours_back=72
        )
        
        print("\n" + "="*70)
        print("📊 النتيجة:")
        print("="*70)
        print(f"نجاح: {result.success}")
        print(f"ID: {result.bulletin_id}")
        print(f"الرسالة: {result.message}")
        print(f"عدد الأخبار: {result.news_count}")
        print(f"عدد الكلمات: {result.word_count}")
        print(f"المدة: {result.duration_seconds // 60} دقيقة و {result.duration_seconds % 60} ثانية")
        
        if result.success and result.bulletin_id:
            gen.cursor.execute(
                "SELECT full_script FROM news_bulletins WHERE id = %s",
                (result.bulletin_id,)
            )
            row = gen.cursor.fetchone()
            if row:
                print("\n" + "="*70)
                print("📜 النشرة الكاملة:")
                print("="*70)
                print(row[0])
        
    except Exception as e:
        print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
    finally:
        gen.close()
    
    print("\n✅ انتهى الاختبار!")