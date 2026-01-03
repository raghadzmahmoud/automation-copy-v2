#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📰 Digest Generator (الموجز الإخباري)
موجز كل 10 دقائق - يتحدث بأحدث الأخبار

الموجز:
- 8-11 خبر
- عناوين فقط (جمل اسمية)
- 2-3 دقائق
- ينتهي بالعملات والطقس
- INSERT جديد فقط عند وجود أخبار جديدة
"""
import certifi, os
os.environ["SSL_CERT_FILE"] = certifi.where()
import os
import json
import re
from datetime import datetime, date
from typing import List, Dict, Optional
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

HEADLINE_PRIORITIES = [
    ('غزة', 1), ('شهيد', 1), ('شهداء', 1), ('استشهاد', 1), ('مجزرة', 1),
    ('اغتيال', 2), ('قصف', 2), ('عدوان', 2), ('غارة', 2),
    ('اقتحام', 3), ('مستوطن', 3), ('الأقصى', 3),
    ('القدس', 4), ('الضفة', 4),
    ('أسرى', 5), ('اعتقال', 5),
    ('فلسطين', 6)
]

DEFAULT_CURRENCY = {'USD': 3.65, 'JOD': 5.15, 'EUR': 3.95}


@dataclass
class ReportItem:
    id: int
    title: str
    content: str
    headline: str = ""
    priority: int = 10


@dataclass
class DigestResult:
    success: bool
    digest_id: Optional[int] = None
    message: str = ""
    news_count: int = 0
    duration_seconds: int = 0
    skipped: bool = False


class DigestGenerator:
    
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cursor = self.conn.cursor()
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        print("✅ Connected to DB and Gemini")
    
    
    def generate_digest(
        self,
        broadcast_hour: int = None,
        report_count: int = 10,
        hours_back: int = 48,
        report_ids: List[int] = None,
        custom_weather: str = None,
        custom_currency: Dict[str, float] = None
    ) -> DigestResult:
        
        # ═══════════════════════════════════════════════════════════
        # 🕐 استخدام الساعة الحالية (مثل النشرة بالضبط)
        # ═══════════════════════════════════════════════════════════
        if broadcast_hour is None:
            broadcast_hour = datetime.now().hour
        
        print("\n" + "="*60)
        print(f"📰 توليد موجز الساعة {broadcast_hour}:00")
        print("="*60)
        
        # 1. جلب التقارير
        print("\n📥 Step 1: جلب التقارير...")
        if report_ids:
            reports = self._fetch_reports_by_ids(report_ids)
        else:
            reports = self._fetch_recent_reports(report_count, hours_back)
        
        if len(reports) < 5:
            return DigestResult(False, message=f"عدد التقارير غير كافٍ ({len(reports)})")
        
        reports = reports[:min(11, len(reports))]
        print(f"   ✅ تم جلب {len(reports)} تقرير")
        
        # ═══════════════════════════════════════════════════════════
        # 🔍 فحص التغيير قبل المتابعة
        # ═══════════════════════════════════════════════════════════
        current_report_ids = sorted([r.id for r in reports])
        
        skip_result = self._check_if_should_skip(current_report_ids)
        if skip_result:
            return skip_result
        
        # 2. ترتيب
        print("\n📊 Step 2: ترتيب حسب الأولوية...")
        reports = self._prioritize_reports(reports)
        print(f"   ✅ تم الترتيب")
        
        # 3. تحويل العناوين
        print("\n✏️ Step 3: تحويل العناوين لجمل اسمية...")
        reports = self._convert_to_nominal_sentences(reports)
        print(f"   ✅ تم تحويل {len(reports)} عنوان")
        
        # 4. بناء الموجز
        print("\n📄 Step 4: بناء الموجز...")
        currency = custom_currency or DEFAULT_CURRENCY
        weather = custom_weather or self._get_default_weather()
        
        full_script = self._build_digest_script(
            broadcast_hour=broadcast_hour,
            reports=reports,
            currency=currency,
            weather=weather
        )
        
        word_count = len(full_script.split())
        duration_seconds = int((word_count / 180) * 60)
        
        print(f"   ✅ الموجز جاهز: {word_count} كلمة، {duration_seconds//60} دقيقة و {duration_seconds%60} ثانية")
        
        # 5. حفظ
        print("\n💾 Step 5: حفظ الموجز...")
        result = self._save_digest(
            broadcast_hour=broadcast_hour,
            reports=reports,
            full_script=full_script,
            currency=currency,
            weather=weather,
            duration_seconds=duration_seconds,
            report_ids=current_report_ids
        )
        
        if result.success:
            print(f"   ✅ تم الحفظ بـ ID: {result.digest_id}")
        
        return result
    
    
    def _check_if_should_skip(self, current_report_ids: List[int]) -> Optional[DigestResult]:
        """
        فحص إذا كانت الأخبار نفسها
        يقارن مع آخر موجز اليوم (بغض النظر عن الساعة)
        """
        
        try:
            # ═══════════════════════════════════════════════════════════
            # 🔍 مقارنة مع آخر موجز اليوم (أي ساعة)
            # ═══════════════════════════════════════════════════════════
            self.cursor.execute("""
                SELECT id, content->'report_ids' as report_ids, digest_hour
                FROM news_digests
                WHERE digest_date = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (date.today(),))
            
            last_digest = self.cursor.fetchone()
            
            if last_digest:
                last_report_ids = last_digest[1] if last_digest[1] else []
                
                if isinstance(last_report_ids, str):
                    last_report_ids = json.loads(last_report_ids)
                
                if sorted(last_report_ids) == current_report_ids:
                    print(f"   ⏭️ نفس الأخبار ({len(current_report_ids)} تقرير) - SKIP")
                    return DigestResult(
                        success=True,
                        digest_id=last_digest[0],
                        message=f"⏭️ SKIP - الموجز موجود (ID: {last_digest[0]})",
                        skipped=True
                    )
                else:
                    new_ids = set(current_report_ids) - set(last_report_ids)
                    print(f"   🆕 {len(new_ids)} تقرير جديد - سيتم إنشاء موجز جديد")
        
        except Exception as e:
            print(f"   ⚠️ خطأ في فحص التغيير: {e}")
        
        return None
    
    
    def _fetch_recent_reports(self, limit: int, hours_back: int) -> List[ReportItem]:
        query = """
            SELECT id, title, content
            FROM generated_report
            WHERE created_at >= NOW() - INTERVAL '%s hours'
              AND content IS NOT NULL
              AND LENGTH(title) > 10
            ORDER BY created_at DESC
            LIMIT %s
        """
        self.cursor.execute(query, (hours_back, limit + 5))
        reports = [ReportItem(id=r[0], title=r[1], content=r[2] or '') for r in self.cursor.fetchall()]
        
        reports = self._remove_duplicates(reports)
        
        return reports[:limit]
    
    def _remove_duplicates(self, reports: List[ReportItem]) -> List[ReportItem]:
        unique_reports = []
        seen_titles = []
        
        stop_words = {'في', 'من', 'على', 'إلى', 'عن', 'مع', 'أن', 'ان', 'هذا', 'هذه', 'التي', 'الذي', 'بعد', 'قبل', 'خلال', 'حول', 'ضد', 'بين'}
        
        for report in reports:
            clean_title = report.title.lower().strip()
            clean_title = re.sub(r'[^\w\s]', '', clean_title)
            
            words = [w for w in clean_title.split() if w not in stop_words and len(w) > 2]
            
            is_duplicate = False
            for seen_words in seen_titles:
                if not words or not seen_words:
                    continue
                
                common = len(set(words) & set(seen_words))
                similarity = common / min(len(words), len(seen_words))
                
                key_words = [w for w in words if len(w) > 4]
                seen_key = [w for w in seen_words if len(w) > 4]
                key_common = len(set(key_words) & set(seen_key))
                
                if similarity > 0.5 or (key_common >= 3):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_reports.append(report)
                seen_titles.append(words)
        
        return unique_reports
    
    def _fetch_reports_by_ids(self, ids: List[int]) -> List[ReportItem]:
        query = """
            SELECT id, title, content
            FROM generated_report
            WHERE id = ANY(%s)
            ORDER BY created_at DESC
        """
        self.cursor.execute(query, (ids,))
        return [ReportItem(id=r[0], title=r[1], content=r[2] or '') for r in self.cursor.fetchall()]
    
    
    def _prioritize_reports(self, reports: List[ReportItem]) -> List[ReportItem]:
        for report in reports:
            text = (report.title + " " + report.content).lower()
            report.priority = 10
            
            for keyword, priority in HEADLINE_PRIORITIES:
                if keyword in text:
                    report.priority = min(report.priority, priority)
        
        reports.sort(key=lambda x: x.priority)
        return reports
    
    
    def _convert_to_nominal_sentences(self, reports: List[ReportItem]) -> List[ReportItem]:
        titles_text = "\n".join([
            f"{i+1}. {report.title}"
            for i, report in enumerate(reports)
        ])
        
        prompt = f"""حوّل هذه العناوين الإخبارية إلى جمل اسمية قصيرة للموجز الإذاعي.

القواعد المهمة:
1. كل عنوان يبدأ بجملة اسمية (اسم أو مصدر، ليس فعل)
2. العنوان قصير جداً (10-15 كلمة كحد أقصى)
3. لا تضف معلومات جديدة
4. أزل أي أقواس أو رموز

أمثلة:
- "تصاعدت الغارات على غزة" ← "تصاعد الغارات الإسرائيلية على غزة"
- "أعلنت الوزارة عن خطة جديدة" ← "إعلان وزاري عن خطة جديدة"
- "استشهد 10 فلسطينيين في غارة" ← "استشهاد 10 فلسطينيين في غارة إسرائيلية"

العناوين:
{titles_text}

أجب بـ JSON فقط (بدون أي نص آخر):
{{"headlines": [
    {{"num": 1, "headline": "العنوان المحوّل"}},
    {{"num": 2, "headline": "العنوان المحوّل"}}
]}}"""

        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={'temperature': 0.3, 'max_output_tokens': 2000}
            )
            
            text = response.text.strip()
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                headlines = data.get('headlines', [])
                
                for item in headlines:
                    idx = item.get('num', item.get('original_num', 0)) - 1
                    if 0 <= idx < len(reports):
                        reports[idx].headline = item.get('headline', reports[idx].title)
        
        except Exception as e:
            print(f"   ⚠️ خطأ في التحويل: {e}")
        
        for report in reports:
            if not report.headline:
                report.headline = report.title
            
            report.headline = report.headline.strip()
            report.headline = re.sub(r'^\[|\]$', '', report.headline)
            report.headline = re.sub(r'^\(|\)$', '', report.headline)
            report.headline = re.sub(r'^["\'"]|["\'"]$', '', report.headline)
            report.headline = report.headline.strip()
        
        return reports
    
    
    def _build_digest_script(
        self,
        broadcast_hour: int,
        reports: List[ReportItem],
        currency: Dict[str, float],
        weather: str
    ) -> str:
        
        lines = []
        
        lines.append("موجز الأخبار من إذاعة صوت النجاح")
        lines.append("")
        
        for i, report in enumerate(reports, 1):
            lines.append(f"{report.headline}")
            lines.append("")
        
        lines.append("في أسعار العملات")
        lines.append(f"الدولار الأمريكي: {currency['USD']} شيكل")
        lines.append(f"الدينار الأردني: {currency['JOD']} شيكل")
        lines.append(f"اليورو: {currency['EUR']} شيكل")
        lines.append("")
        
        lines.append("في حالة الطقس")
        lines.append(weather)
        lines.append("")
        
        lines.append("نهاية الموجز، لمتابعة أوفى على النجاح الإخباري nn.ps")
        
        return "\n".join(lines)
    
    
    def _get_default_weather(self) -> str:
        month = datetime.now().month
        if month in [12, 1, 2]:
            return "الجو بارد وغائم جزئياً مع احتمال أمطار متفرقة."
        elif month in [6, 7, 8]:
            return "الجو حار وصاف بشكل عام."
        else:
            return "الجو معتدل وغائم جزئياً."
    
    
    def _save_digest(
        self,
        broadcast_hour: int,
        reports: List[ReportItem],
        full_script: str,
        currency: Dict,
        weather: str,
        duration_seconds: int,
        report_ids: List[int]
    ) -> DigestResult:
        
        try:
            headlines = [
                {
                    'report_id': r.id,
                    'headline': r.headline,
                    'order': i + 1
                }
                for i, r in enumerate(reports)
            ]
            
            content = {
                'headlines': headlines,
                'currency': currency,
                'weather': weather,
                'news_count': len(reports),
                'report_ids': report_ids
            }
            
            # INSERT دائماً (سجل جديد لكل تغيير)
            self.cursor.execute("""
                INSERT INTO news_digests 
                (digest_hour, digest_date, content, full_script, estimated_duration_seconds, status)
                VALUES (%s, %s, %s, %s, %s, 'ready')
                RETURNING id
            """, (
                broadcast_hour,
                date.today(),
                json.dumps(content, ensure_ascii=False),
                full_script,
                duration_seconds
            ))
            
            digest_id = self.cursor.fetchone()[0]
            
            for i, report in enumerate(reports):
                self.cursor.execute("""
                    INSERT INTO digest_reports 
                    (digest_id, report_id, display_order, headline_text)
                    VALUES (%s, %s, %s, %s)
                """, (digest_id, report.id, i + 1, report.headline))
            
            self.conn.commit()
            
            return DigestResult(
                success=True,
                digest_id=digest_id,
                message=f"✅ تم إنشاء موجز جديد (ID: {digest_id})",
                news_count=len(reports),
                duration_seconds=duration_seconds
            )
            
        except Exception as e:
            self.conn.rollback()
            return DigestResult(False, message=f"خطأ في الحفظ: {str(e)}")
    
    
    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("🔒 تم إغلاق الاتصالات")


def generate_digest(broadcast_hour: int = None, **kwargs) -> DigestResult:
    gen = DigestGenerator()
    try:
        return gen.generate_digest(broadcast_hour=broadcast_hour, **kwargs)
    finally:
        gen.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 اختبار توليد الموجز الإخباري")
    print("="*60)
    
    gen = DigestGenerator()
    
    try:
        # ═══════════════════════════════════════════════════════════
        # 🕐 استخدام الساعة الحالية تلقائياً
        # ═══════════════════════════════════════════════════════════
        result = gen.generate_digest(
            broadcast_hour=None,  # تلقائي حسب الوقت الحالي
            report_count=10,
            hours_back=72
        )
        
        print("\n" + "="*60)
        print("📊 النتيجة:")
        print("="*60)
        print(f"نجاح: {result.success}")
        print(f"ID: {result.digest_id}")
        print(f"الرسالة: {result.message}")
        print(f"SKIP: {result.skipped}")
        
    except Exception as e:
        print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
    finally:
        gen.close()
    
    print("\n✅ انتهى الاختبار!")
    