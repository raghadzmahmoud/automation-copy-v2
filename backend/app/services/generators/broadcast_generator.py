#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📻 Unified Broadcast Generator V2
═══════════════════════════════════════════════════════════════
نظام موحد لتوليد النشرات والموجزات - هنا غزة

المبدأ:
- X = كل كم ساعة (period_hours)
- Y = كم مدة السكريبت (target_duration_minutes)
- صباحي (6:00 - 17:59) / مسائي (18:00 - 5:59)

الإعدادات من جدول: broadcast_configs
═══════════════════════════════════════════════════════════════
"""
import certifi, os
os.environ["SSL_CERT_FILE"] = certifi.where()
import os
import json
import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal

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

# أولويات العناوين
HEADLINE_PRIORITIES = [
    ('غزة', 1), ('شهيد', 1), ('شهداء', 1), ('استشهاد', 1), ('مجزرة', 1),
    ('اغتيال', 2), ('قصف', 2), ('عدوان', 2), ('غارة', 2),
    ('اقتحام', 3), ('مستوطن', 3), ('الأقصى', 3),
    ('القدس', 4), ('الضفة', 4),
    ('أسرى', 5), ('اعتقال', 5),
    ('فلسطين', 6)
]

# أقسام الأخبار
NEWS_SECTIONS = [
    {'key': 'gaza', 'name': 'في غزة', 'keywords': ['غزة', 'القطاع', 'حماس', 'خان يونس', 'رفح', 'جباليا']},
    {'key': 'jerusalem', 'name': 'في القدس', 'keywords': ['القدس', 'الأقصى', 'المسجد الأقصى']},
    {'key': 'westbank', 'name': 'في الضفة الغربية', 'keywords': ['الضفة', 'نابلس', 'جنين', 'الخليل', 'رام الله']},
    {'key': 'prisoners', 'name': 'في شؤون الأسرى', 'keywords': ['أسرى', 'أسير', 'معتقل', 'سجن']},
    {'key': 'local', 'name': 'محلياً', 'keywords': ['السلطة الفلسطينية', 'فلسطيني']},
    {'key': 'international', 'name': 'دولياً', 'keywords': ['أمريكا', 'روسيا', 'الصين', 'أوروبا', 'إسرائيل']},
    {'key': 'arab', 'name': 'عربياً', 'keywords': ['مصر', 'الأردن', 'السعودية', 'الإمارات', 'قطر', 'لبنان']},
]

DEFAULT_CURRENCY = {'USD': 3.65, 'JOD': 5.15, 'EUR': 3.95}


# ============================================
# Data Classes
# ============================================

@dataclass
class BroadcastConfig:
    """إعدادات البث من الداتابيس"""
    id: int
    name: str
    code: str
    broadcasts_per_day: int
    period_hours: float
    target_duration_minutes: float
    target_word_count: int
    news_count: int
    hours_back: int
    greeting_morning: str
    greeting_evening: str
    morning_start_hour: int
    evening_start_hour: int
    outro_text: str
    content_style: str  # 'headlines' or 'detailed'
    include_currency: bool
    include_weather: bool
    target_table: str


@dataclass
class ReportItem:
    """خبر/تقرير"""
    id: int
    title: str
    content: str
    summary: str = ""
    headline: str = ""
    section: str = "other"
    priority: int = 10


@dataclass
class BroadcastResult:
    """نتيجة التوليد"""
    success: bool
    broadcast_id: Optional[int] = None
    config_code: str = ""
    message: str = ""
    news_count: int = 0
    word_count: int = 0
    duration_seconds: int = 0
    skipped: bool = False
    is_morning: bool = True  # صباحي أو مسائي


# ============================================
# Main Generator Class
# ============================================

class BroadcastGenerator:
    """
    مولد البث الموحد - هنا غزة
    يقرأ الإعدادات من broadcast_configs ويولد حسب النوع
    """
    
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cursor = self.conn.cursor()
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        print("✅ BroadcastGenerator initialized")
    
    
    def _is_morning(self, config: BroadcastConfig) -> bool:
        """
        تحديد إذا كان الوقت صباحي أو مسائي
        صباحي: من morning_start_hour إلى evening_start_hour
        مسائي: من evening_start_hour إلى morning_start_hour
        """
        current_hour = datetime.now().hour
        return config.morning_start_hour <= current_hour < config.evening_start_hour
    
    
    # ════════════════════════════════════════════════════════════
    # 📖 قراءة الإعدادات
    # ════════════════════════════════════════════════════════════
    
    def get_config(self, code: str) -> Optional[BroadcastConfig]:
        """جلب إعدادات بث معين من الداتابيس"""
        try:
            self.cursor.execute("""
                SELECT 
                    id, name, code, broadcasts_per_day, period_hours,
                    target_duration_minutes, 
                    COALESCE(target_word_count, CAST(target_duration_minutes * 150 AS INTEGER)),
                    news_count, hours_back,
                    greeting_morning, greeting_evening,
                    morning_start_hour, evening_start_hour,
                    outro_text, content_style,
                    include_currency, include_weather,
                    target_table
                FROM broadcast_configs
                WHERE code = %s AND is_active = true
            """, (code,))
            
            row = self.cursor.fetchone()
            if not row:
                print(f"❌ Config not found: {code}")
                return None
            
            return BroadcastConfig(
                id=row[0],
                name=row[1],
                code=row[2],
                broadcasts_per_day=row[3],
                period_hours=float(row[4]) if row[4] else 24/row[3],
                target_duration_minutes=float(row[5]),
                target_word_count=row[6] or int(float(row[5]) * 150),
                news_count=row[7],
                hours_back=row[8],
                greeting_morning=row[9],
                greeting_evening=row[10],
                morning_start_hour=row[11],
                evening_start_hour=row[12],
                outro_text=row[13],
                content_style=row[14],
                include_currency=row[15],
                include_weather=row[16],
                target_table=row[17]
            )
            
        except Exception as e:
            print(f"❌ Error fetching config: {e}")
            return None
    
    
    def get_all_active_configs(self) -> List[BroadcastConfig]:
        """جلب كل الإعدادات النشطة"""
        configs = []
        try:
            self.cursor.execute("""
                SELECT code FROM broadcast_configs WHERE is_active = true
            """)
            for row in self.cursor.fetchall():
                config = self.get_config(row[0])
                if config:
                    configs.append(config)
        except Exception as e:
            print(f"❌ Error fetching configs: {e}")
        return configs
    
    
    # ════════════════════════════════════════════════════════════
    # 🎯 التوليد الرئيسي
    # ════════════════════════════════════════════════════════════
    
    def generate(self, config_code: str) -> BroadcastResult:
        """
        توليد بث حسب الكود
        
        Args:
            config_code: كود الإعدادات ('digest', 'bulletin', etc.)
        """
        print("\n" + "="*70)
        print(f"📻 Generating: {config_code}")
        print("="*70)
        
        # 1. جلب الإعدادات
        config = self.get_config(config_code)
        if not config:
            return BroadcastResult(
                success=False,
                config_code=config_code,
                message=f"Config not found: {config_code}"
            )
        
        # تحديد صباحي/مسائي
        is_morning = self._is_morning(config)
        time_period = "صباحي" if is_morning else "مسائي"
        
        print(f"⚙️ Config: {config.name}")
        print(f"   • كل {config.period_hours} ساعات")
        print(f"   • مدة {config.target_duration_minutes} دقيقة")
        print(f"   • نوع: {config.content_style}")
        print(f"   • 🕐 الفترة: {time_period}")
        
        # 2. جلب الأخبار
        print(f"\n📥 جلب {config.news_count} خبر من آخر {config.hours_back} ساعة...")
        reports = self._fetch_reports(config.news_count, config.hours_back)
        
        if len(reports) < 3:
            return BroadcastResult(
                success=False,
                config_code=config_code,
                message=f"عدد الأخبار غير كافٍ ({len(reports)})",
                is_morning=is_morning
            )
        
        print(f"   ✅ تم جلب {len(reports)} خبر")
        
        # 3. فحص التكرار
        current_report_ids = sorted([r.id for r in reports])
        skip_result = self._check_if_should_skip(config, current_report_ids, is_morning)
        if skip_result:
            return skip_result
        
        # 4. ترتيب وتصنيف
        print(f"\n📊 ترتيب وتصنيف الأخبار...")
        reports = self._prioritize_and_classify(reports)
        
        # 5. معالجة حسب النوع
        if config.content_style == 'headlines':
            # موجز: عناوين قصيرة فقط
            print(f"\n✏️ تحويل العناوين لجمل اسمية...")
            reports = self._convert_to_headlines(reports)
        else:
            # نشرة: إعادة صياغة مفصلة
            print(f"\n📝 إعادة صياغة الأخبار...")
            reports = self._rewrite_for_broadcast(reports, config)
        
        # 6. بناء السكريبت
        print(f"\n📄 بناء السكريبت...")
        script = self._build_script(config, reports, is_morning)
        
        word_count = len(script.split())
        duration_seconds = int((word_count / 150) * 60)
        
        print(f"   ✅ {word_count} كلمة ≈ {duration_seconds//60}:{duration_seconds%60:02d} دقيقة")
        
        # 7. حفظ
        print(f"\n💾 حفظ في {config.target_table}...")
        result = self._save_broadcast(config, reports, script, current_report_ids, is_morning)
        
        return result
    
    
    # ════════════════════════════════════════════════════════════
    # 📰 جلب الأخبار
    # ════════════════════════════════════════════════════════════
    
    def _fetch_reports(self, limit: int, hours_back: int) -> List[ReportItem]:
        """جلب التقارير الأخيرة"""
        try:
            self.cursor.execute("""
                SELECT id, title, content
                FROM generated_report
                WHERE created_at >= NOW() - INTERVAL '%s hours'
                  AND content IS NOT NULL
                  AND LENGTH(content) > 100
                ORDER BY created_at DESC
                LIMIT %s
            """, (hours_back, limit + 5))
            
            reports = [
                ReportItem(id=r[0], title=r[1], content=r[2] or '')
                for r in self.cursor.fetchall()
            ]
            
            # إزالة التكرار
            return self._remove_duplicates(reports)[:limit]
            
        except Exception as e:
            print(f"❌ Error fetching reports: {e}")
            return []
    
    
    def _remove_duplicates(self, reports: List[ReportItem]) -> List[ReportItem]:
        """إزالة الأخبار المكررة"""
        unique = []
        seen_titles = []
        stop_words = {'في', 'من', 'على', 'إلى', 'عن', 'مع', 'أن', 'هذا', 'هذه'}
        
        for report in reports:
            clean = re.sub(r'[^\w\s]', '', report.title.lower())
            words = [w for w in clean.split() if w not in stop_words and len(w) > 2]
            
            is_dup = False
            for seen in seen_titles:
                if not words or not seen:
                    continue
                common = len(set(words) & set(seen))
                if common / min(len(words), len(seen)) > 0.5:
                    is_dup = True
                    break
            
            if not is_dup:
                unique.append(report)
                seen_titles.append(words)
        
        return unique
    
    
    # ════════════════════════════════════════════════════════════
    # 🔍 فحص التكرار
    # ════════════════════════════════════════════════════════════
    
    def _check_if_should_skip(
        self, 
        config: BroadcastConfig, 
        current_report_ids: List[int],
        is_morning: bool
    ) -> Optional[BroadcastResult]:
        """فحص إذا كانت نفس الأخبار"""
        try:
            if config.target_table == 'news_digests':
                self.cursor.execute("""
                    SELECT id, content->'report_ids' as report_ids
                    FROM news_digests
                    WHERE digest_date = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (date.today(),))
            else:
                self.cursor.execute("""
                    SELECT id, content->'report_ids' as report_ids
                    FROM news_bulletins
                    WHERE broadcast_date = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (date.today(),))
            
            last = self.cursor.fetchone()
            
            if last:
                last_ids = last[1] if last[1] else []
                if isinstance(last_ids, str):
                    last_ids = json.loads(last_ids)
                
                if sorted(last_ids) == current_report_ids:
                    print(f"   ⏭️ نفس الأخبار - SKIP")
                    return BroadcastResult(
                        success=True,
                        broadcast_id=last[0],
                        config_code=config.code,
                        message="SKIP - نفس الأخبار",
                        skipped=True,
                        is_morning=is_morning
                    )
                else:
                    new_count = len(set(current_report_ids) - set(last_ids))
                    print(f"   🆕 {new_count} خبر جديد")
                    
        except Exception as e:
            print(f"   ⚠️ خطأ في فحص التكرار: {e}")
        
        return None
    
    
    # ════════════════════════════════════════════════════════════
    # 📊 الترتيب والتصنيف
    # ════════════════════════════════════════════════════════════
    
    def _prioritize_and_classify(self, reports: List[ReportItem]) -> List[ReportItem]:
        """ترتيب وتصنيف الأخبار"""
        for report in reports:
            text = (report.title + " " + report.content).lower()
            
            # الأولوية
            report.priority = 10
            for keyword, priority in HEADLINE_PRIORITIES:
                if keyword in text:
                    report.priority = min(report.priority, priority)
            
            # القسم
            report.section = "other"
            for section in NEWS_SECTIONS:
                for keyword in section['keywords']:
                    if keyword in text:
                        report.section = section['key']
                        break
                if report.section != "other":
                    break
        
        reports.sort(key=lambda x: x.priority)
        return reports
    
    
    # ════════════════════════════════════════════════════════════
    # ✏️ تحويل العناوين (للموجز)
    # ════════════════════════════════════════════════════════════
    
    def _convert_to_headlines(self, reports: List[ReportItem]) -> List[ReportItem]:
        """تحويل العناوين لجمل اسمية قصيرة"""
        
        for i, report in enumerate(reports):
            print(f"   [{i+1}/{len(reports)}] تحويل: {report.title[:40]}...")
            
            prompt = f"""حوّل هذا العنوان الإخباري إلى جملة اسمية قصيرة للموجز الإذاعي.

العنوان الأصلي: {report.title}

القواعد:
1. ابدأ بجملة اسمية (اسم أو مصدر، ليس فعل)
2. قصير جداً (10-15 كلمة كحد أقصى)
3. لا تضف معلومات جديدة
4. أزل أي أقواس أو رموز

أمثلة:
- "استشهد 10 فلسطينيين في غارة" ← "استشهاد 10 فلسطينيين في غارة إسرائيلية"
- "أعلنت الوزارة عن خطة جديدة" ← "إعلان وزاري عن خطة جديدة"
- "تصاعدت الغارات على غزة" ← "تصاعد الغارات الإسرائيلية على غزة"

أعطني العنوان المحوّل فقط بدون أي شرح:"""

            try:
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config={'temperature': 0.2, 'max_output_tokens': 100}
                )
                
                headline = response.text.strip()
                # تنظيف
                headline = re.sub(r'^["\'"]|["\'"]$', '', headline)
                headline = re.sub(r'^\[|\]$', '', headline)
                headline = re.sub(r'^\(|\)$', '', headline)
                headline = headline.strip()
                
                if headline and len(headline) > 10:
                    report.headline = headline
                else:
                    report.headline = report.title
                    
            except Exception as e:
                print(f"      ⚠️ خطأ: {e}")
                report.headline = report.title
        
        return reports
    
    
    # ════════════════════════════════════════════════════════════
    # 📝 إعادة الصياغة (للنشرة)
    # ════════════════════════════════════════════════════════════
    
    def _rewrite_for_broadcast(
        self, 
        reports: List[ReportItem], 
        config: BroadcastConfig
    ) -> List[ReportItem]:
        """إعادة صياغة الأخبار للنشرة المفصلة"""
        
        for i, report in enumerate(reports, 1):
            print(f"   [{i}/{len(reports)}] {report.title[:40]}...")
            
            prompt = f"""أعد صياغة هذا الخبر كفقرة إذاعية.

العنوان: {report.title}
المحتوى: {report.content}

التعليمات:
1. فقرة واحدة متماسكة (4-8 جمل)
2. لغة عربية فصحى واضحة
3. ابدأ بالمعلومة الأهم
4. حافظ على الأرقام والأسماء
5. لا تضف معلومات

الفقرة:"""

            try:
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config={'temperature': 0.3, 'max_output_tokens': 1000}
                )
                report.summary = response.text.strip()
                report.summary = re.sub(r'^#+\s*', '', report.summary)
                report.summary = re.sub(r'\*\*|\*', '', report.summary)
                
            except Exception as e:
                print(f"      ⚠️ خطأ: {e}")
                report.summary = report.content[:500]
        
        return reports
    
    
    # ════════════════════════════════════════════════════════════
    # 📄 بناء السكريبت - هنا غزة (صباحي/مسائي)
    # ════════════════════════════════════════════════════════════
    
    def _build_script(
        self, 
        config: BroadcastConfig, 
        reports: List[ReportItem],
        is_morning: bool
    ) -> str:
        """بناء السكريبت النهائي مع تحديد صباحي/مسائي"""
        lines = []
        
        # التحية حسب الوقت (صباحي/مسائي)
        if is_morning:
            greeting = config.greeting_morning
        else:
            greeting = config.greeting_evening
        
        if config.content_style == 'headlines':
            # ═══════════════════════════════════════════════════════
            # 📰 موجز: عناوين مع فقرات قصيرة
            # ═══════════════════════════════════════════════════════
            
            # المقدمة
            lines.append(greeting)
            lines.append("")
            
            # الأخبار (كل خبر بفقرة قصيرة)
            for report in reports:
                headline = report.headline or report.title
                summary = self._get_short_summary(report.content)
                
                lines.append(headline)
                if summary:
                    lines.append(summary)
                lines.append("")
        
        else:
            # ═══════════════════════════════════════════════════════
            # 📻 نشرة: مفصلة مع عناوين بارزة
            # ═══════════════════════════════════════════════════════
            
            # المقدمة
            lines.append(greeting)
            lines.append("")
            
            # أبرز 3 عناوين
            top_3 = reports[:3]
            for r in top_3:
                lines.append(f"• {r.title}")
            lines.append("")
            
            # الانتقال للتفاصيل
            lines.append("أهلاً بكم إلى التفاصيل")
            lines.append("")
            
            # الأخبار مفصلة
            for report in reports:
                lines.append(f"({report.title})")
                lines.append(report.summary or report.content[:500])
                lines.append("")
        
        # العملات
        if config.include_currency:
            lines.append("في أسعار العملات")
            lines.append(f"الدولار: {DEFAULT_CURRENCY['USD']} شيكل")
            lines.append(f"الدينار: {DEFAULT_CURRENCY['JOD']} شيكل")
            lines.append(f"اليورو: {DEFAULT_CURRENCY['EUR']} شيكل")
            lines.append("")
        
        # الطقس
        if config.include_weather:
            lines.append("في حالة الطقس")
            lines.append(self._get_weather())
            lines.append("")
        
        # الخاتمة (إذا موجودة)
        if config.outro_text and config.outro_text.strip():
            lines.append(config.outro_text)
        
        return "\n".join(lines)
    
    
    def _get_short_summary(self, content: str, max_sentences: int = 2) -> str:
        """استخراج فقرة قصيرة من المحتوى"""
        if not content:
            return ""
        
        content = content.strip()
        sentences = re.split(r'[.،؟!]\s*', content)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        
        if not sentences:
            return ""
        
        result = '. '.join(sentences[:max_sentences])
        if result and not result.endswith(('.', '؟', '!')):
            result += '.'
        
        return result
    
    
    def _get_weather(self) -> str:
        """حالة الطقس الافتراضية"""
        month = datetime.now().month
        if month in [12, 1, 2]:
            return "الجو بارد وغائم جزئياً مع احتمال أمطار."
        elif month in [6, 7, 8]:
            return "الجو حار وصاف بشكل عام."
        return "الجو معتدل وغائم جزئياً."
    
    
    # ════════════════════════════════════════════════════════════
    # 💾 الحفظ
    # ════════════════════════════════════════════════════════════
    
    def _save_broadcast(
        self,
        config: BroadcastConfig,
        reports: List[ReportItem],
        script: str,
        report_ids: List[int],
        is_morning: bool
    ) -> BroadcastResult:
        """حفظ البث في الجدول المناسب"""
        
        try:
            word_count = len(script.split())
            duration = int((word_count / 150) * 60)
            
            content = {
                'config_code': config.code,
                'config_name': config.name,
                'news_count': len(reports),
                'word_count': word_count,
                'report_ids': report_ids,
                'is_morning': is_morning,
                'time_period': 'صباحي' if is_morning else 'مسائي',
                'headlines': [
                    {'report_id': r.id, 'title': r.title, 'headline': r.headline or r.title}
                    for r in reports
                ]
            }
            
            current_hour = datetime.now().hour
            
            if config.target_table == 'news_digests':
                self.cursor.execute("""
                    INSERT INTO news_digests 
                    (digest_hour, digest_date, content, full_script, estimated_duration_seconds, status)
                    VALUES (%s, %s, %s, %s, %s, 'ready')
                    RETURNING id
                """, (
                    current_hour,
                    date.today(),
                    json.dumps(content, ensure_ascii=False),
                    script,
                    duration
                ))
            else:
                # نشرة صباحية أو مسائية
                bulletin_type = "صباحية" if is_morning else "مسائية"
                self.cursor.execute("""
                    INSERT INTO news_bulletins 
                    (bulletin_type, broadcast_date, content, full_script, estimated_duration_seconds, status)
                    VALUES (%s, %s, %s, %s, %s, 'ready')
                    RETURNING id
                """, (
                    bulletin_type,
                    date.today(),
                    json.dumps(content, ensure_ascii=False),
                    script,
                    duration
                ))
            
            broadcast_id = self.cursor.fetchone()[0]
            self.conn.commit()
            
            time_period = "صباحي" if is_morning else "مسائي"
            print(f"   ✅ تم الحفظ (ID: {broadcast_id}) - {time_period}")
            
            return BroadcastResult(
                success=True,
                broadcast_id=broadcast_id,
                config_code=config.code,
                message=f"✅ تم التوليد (ID: {broadcast_id}) - {time_period}",
                news_count=len(reports),
                word_count=word_count,
                duration_seconds=duration,
                is_morning=is_morning
            )
            
        except Exception as e:
            self.conn.rollback()
            print(f"   ❌ خطأ في الحفظ: {e}")
            return BroadcastResult(
                success=False,
                config_code=config.code,
                message=f"خطأ في الحفظ: {str(e)}",
                is_morning=is_morning
            )
    
    
    # ════════════════════════════════════════════════════════════
    # 🔄 تشغيل الكل
    # ════════════════════════════════════════════════════════════
    
    def generate_all_due(self) -> Dict[str, BroadcastResult]:
        """توليد كل البثات المستحقة"""
        results = {}
        configs = self.get_all_active_configs()
        
        print(f"\n{'='*70}")
        print(f"🔄 Checking {len(configs)} broadcast configs...")
        print(f"{'='*70}")
        
        for config in configs:
            if self._is_due(config):
                print(f"\n⏰ {config.name} مستحق - بدء التوليد...")
                results[config.code] = self.generate(config.code)
            else:
                print(f"⏭️ {config.name} - ليس بعد")
        
        return results
    
    
    def _is_due(self, config: BroadcastConfig) -> bool:
        """فحص إذا حان وقت التوليد"""
        try:
            if config.target_table == 'news_digests':
                self.cursor.execute("""
                    SELECT created_at FROM news_digests
                    WHERE digest_date = %s
                    ORDER BY created_at DESC LIMIT 1
                """, (date.today(),))
            else:
                self.cursor.execute("""
                    SELECT created_at FROM news_bulletins
                    WHERE broadcast_date = %s
                    ORDER BY created_at DESC LIMIT 1
                """, (date.today(),))
            
            last = self.cursor.fetchone()
            
            if not last:
                return True
            
            hours_since = (datetime.now() - last[0].replace(tzinfo=None)).total_seconds() / 3600
            return hours_since >= config.period_hours
            
        except Exception as e:
            print(f"⚠️ Error checking due: {e}")
            return True
    
    
    def close(self):
        """إغلاق الاتصالات"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("🔒 Connection closed")


# ============================================
# 🧪 Test
# ============================================

if __name__ == "__main__":
    import sys
    
    print("\n" + "="*70)
    print("🧪 Testing BroadcastGenerator - هنا غزة")
    print("="*70)
    
    gen = BroadcastGenerator()
    
    try:
        # عرض الإعدادات
        print("\n📋 Active Configs:")
        for cfg in gen.get_all_active_configs():
            print(f"   • {cfg.name} ({cfg.code})")
            print(f"     - كل {cfg.period_hours} ساعات")
            print(f"     - مدة {cfg.target_duration_minutes} دقيقة")
            print(f"     - نوع: {cfg.content_style}")
        
        # تحديد ماذا نختبر
        test_type = sys.argv[1] if len(sys.argv) > 1 else 'both'
        
        if test_type in ['digest', 'both']:
            print("\n" + "-"*70)
            print("🧪 Testing Digest Generation...")
            print("-"*70)
            
            result = gen.generate('digest')
            
            print(f"\n📊 Digest Result:")
            print(f"   Success: {result.success}")
            print(f"   ID: {result.broadcast_id}")
            print(f"   Skipped: {result.skipped}")
            print(f"   Is Morning: {result.is_morning}")
            print(f"   Message: {result.message}")
        
        if test_type in ['bulletin', 'both']:
            print("\n" + "-"*70)
            print("🧪 Testing Bulletin Generation...")
            print("-"*70)
            
            result = gen.generate('bulletin')
            
            print(f"\n📊 Bulletin Result:")
            print(f"   Success: {result.success}")
            print(f"   ID: {result.broadcast_id}")
            print(f"   Skipped: {result.skipped}")
            print(f"   Is Morning: {result.is_morning}")
            print(f"   Message: {result.message}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        gen.close()
    
    print("\n✅ Test completed!")