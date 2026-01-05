#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📰 Report Generator Service - V2 (No JSON Parsing)
توليد التقارير الإخبارية من clusters
استخدام format نصي بسيط بدل JSON
"""

import sys
import os

# Add project root to path to resolve module-not-found errors
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import psycopg2
from google import genai

from settings import GEMINI_API_KEY, GEMINI_MODEL, DB_CONFIG


@dataclass
class ReportData:
    """بيانات التقرير المُستخرجة"""
    title: str
    content: str
    
    def is_valid(self, min_words: int = 30, max_words: int = 300) -> Tuple[bool, str]:
        """التحقق من صحة البيانات"""
        if not self.title or len(self.title.strip()) < 10:
            return False, "العنوان قصير جداً"
        
        if not self.content or len(self.content.strip()) < 30:
            return False, "المحتوى قصير جداً"
        
        word_count = len(self.content.split())
        if word_count < min_words:
            return False, f"عدد الكلمات ({word_count}) أقل من {min_words}"
        
        if word_count > max_words:
            return False, f"عدد الكلمات ({word_count}) أكثر من {max_words}"
        
        return True, "OK"


class TextParser:
    """محلل النصوص - استخراج العنوان والمحتوى"""
    
    @staticmethod
    def parse(text: str) -> Optional[ReportData]:
        """
        استخراج العنوان والمحتوى من النص
        يجرب عدة طرق للاستخراج
        """
        text = text.strip()
        
        # الطريقة 1: البحث عن markers واضحة
        result = TextParser._parse_with_markers(text)
        if result:
            return result
        
        # الطريقة 2: البحث عن أنماط عربية
        result = TextParser._parse_arabic_format(text)
        if result:
            return result
        
        # الطريقة 3: أول سطر = عنوان، الباقي = محتوى
        result = TextParser._parse_simple_split(text)
        if result:
            return result
        
        return None
    
    @staticmethod
    def _parse_with_markers(text: str) -> Optional[ReportData]:
        """البحث عن markers مثل [العنوان] و [المحتوى]"""
        patterns = [
            # Pattern 1: [العنوان] ... [المحتوى] ...
            (r'\[العنوان\][:\s]*(.+?)(?=\[المحتوى\])', r'\[المحتوى\][:\s]*(.+)'),
            # Pattern 2: **العنوان:** ... **المحتوى:** ...
            (r'\*\*العنوان\*\*[:\s]*(.+?)(?=\*\*المحتوى\*\*)', r'\*\*المحتوى\*\*[:\s]*(.+)'),
            # Pattern 3: العنوان: ... المحتوى: ...
            (r'العنوان[:\s]+(.+?)(?=المحتوى[:\s])', r'المحتوى[:\s]+(.+)'),
            # Pattern 4: TITLE: ... CONTENT: ...
            (r'(?:TITLE|Title)[:\s]+(.+?)(?=(?:CONTENT|Content)[:\s])', r'(?:CONTENT|Content)[:\s]+(.+)'),
        ]
        
        for title_pattern, content_pattern in patterns:
            title_match = re.search(title_pattern, text, re.DOTALL | re.IGNORECASE)
            content_match = re.search(content_pattern, text, re.DOTALL | re.IGNORECASE)
            
            if title_match and content_match:
                title = TextParser._clean_text(title_match.group(1))
                content = TextParser._clean_text(content_match.group(1))
                
                if title and content:
                    return ReportData(title=title, content=content)
        
        return None
    
    @staticmethod
    def _parse_arabic_format(text: str) -> Optional[ReportData]:
        """البحث عن format عربي"""
        # البحث عن سطر يبدأ بـ "عنوان" أو يحتوي على ":"
        lines = text.split('\n')
        title = None
        content_lines = []
        content_started = False
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # البحث عن العنوان
            if not title:
                # إزالة أي prefix
                cleaned = re.sub(r'^(العنوان|عنوان|Title)[:\s\-–—]*', '', line, flags=re.IGNORECASE)
                cleaned = re.sub(r'^\*+|\*+$', '', cleaned).strip()
                cleaned = re.sub(r'^#+\s*', '', cleaned).strip()
                
                if cleaned and len(cleaned) > 10:
                    title = cleaned
                    continue
            
            # بعد العنوان، نجمع المحتوى
            if title:
                # تخطي أي marker للمحتوى
                if re.match(r'^(المحتوى|محتوى|Content)[:\s]*$', line, re.IGNORECASE):
                    content_started = True
                    continue
                
                content_started = True
                # إزالة prefix المحتوى إذا وجد
                cleaned = re.sub(r'^(المحتوى|محتوى|Content)[:\s\-–—]*', '', line, flags=re.IGNORECASE)
                if cleaned:
                    content_lines.append(cleaned)
        
        if title and content_lines:
            content = '\n'.join(content_lines)
            content = TextParser._clean_text(content)
            if content:
                return ReportData(title=title, content=content)
        
        return None
    
    @staticmethod
    def _parse_simple_split(text: str) -> Optional[ReportData]:
        """أبسط طريقة: أول سطر = عنوان"""
        # إزالة markdown
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'^\s*#+ ', '', text, flags=re.MULTILINE)
        
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        if len(lines) < 2:
            return None
        
        # أول سطر غير فارغ = عنوان
        title = lines[0]
        title = re.sub(r'^\*+|\*+$', '', title).strip()
        title = re.sub(r'^[""]|[""]$', '', title).strip()
        
        # الباقي = محتوى
        content = '\n'.join(lines[1:])
        content = TextParser._clean_text(content)
        
        if title and content and len(title) > 10:
            return ReportData(title=title, content=content)
        
        return None
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """تنظيف النص"""
        if not text:
            return ""
        
        # إزالة markdown
        text = re.sub(r'\*\*|\*|__|_', '', text)
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`[^`]+`', '', text)
        
        # إزالة HTML
        text = re.sub(r'<[^>]+>', '', text)
        
        # إزالة JSON artifacts
        text = re.sub(r'[{}\[\]]', '', text)
        text = re.sub(r'"title"\s*:', '', text)
        text = re.sub(r'"content"\s*:', '', text)
        
        # تنظيف المسافات
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        
        return text.strip()


class ReportGenerator:
    """مولد التقارير الإخبارية"""
    
    def __init__(self):
        """تهيئة المولد"""
        self.conn = None
        self.cursor = None
        self.parser = TextParser()
        
        # اتصال بقاعدة البيانات
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print("✅ ReportGenerator initialized")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise
        
        # تهيئة Gemini
        try:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
            print(f"✅ Gemini client ready (Model: {GEMINI_MODEL})")
        except Exception as e:
            print(f"❌ Gemini client failed: {e}")
            raise
        
    def generate_reports_for_clusters(
        self,
        cluster_ids: List[int] = None,
        skip_existing: bool = True,
        check_updates_hours: int = 1
    ) -> Dict:
        """إنشاء تقارير لـ clusters"""
        print("\n" + "="*70)
        print("🤖 Starting Report Generation (V2 - Text Format)")
        print("="*70)

        # جلب clusters
        if cluster_ids:
            clusters = self._fetch_clusters_by_ids(cluster_ids)
        else:
            # 1️⃣ كلسترات جديدة بدون تقارير
            new_clusters = self._fetch_clusters_without_reports() if skip_existing else []

            # 2️⃣ كلسترات محدثة تحتاج إعادة توليد
            updated_clusters = self._fetch_recently_updated_clusters(check_updates_hours)

            # دمج القائمتين (بدون تكرار)
            seen_ids = set()
            clusters = []
            for c in new_clusters + updated_clusters:
                if c['id'] not in seen_ids:
                    clusters.append(c)
                    seen_ids.add(c['id'])

            print(f"   📰 New clusters: {len(new_clusters)}")
            print(f"   🔄 Updated clusters: {len(updated_clusters)}")

        if not clusters:
            print("📭 No clusters to process")
            return {'total': 0, 'success': 0, 'failed': 0}

        print(f"📋 Processing {len(clusters)} clusters...")

        stats = {'total': len(clusters), 'success': 0, 'failed': 0}

        for i, cluster in enumerate(clusters, 1):
            cluster_id = cluster['id']
            print(f"\n[{i}/{len(clusters)}] Cluster #{cluster_id}")

            gen_time = self._generate_report_for_cluster(cluster)

            if gen_time:
                stats['success'] += 1
                print(f"   ✅ Done in {gen_time:.2f}s")
            else:
                stats['failed'] += 1
                print(f"   ❌ Failed")

        print(f"\n{'='*70}")
        print(f"📊 Results: {stats['success']} success, {stats['failed']} failed")
        print(f"{'='*70}")

        return stats

    def _generate_report_for_cluster(self, cluster: Dict) -> Optional[float]:
        """إنشاء تقرير لـ cluster واحد"""
        cluster_id = cluster['id']

        news_items = self._fetch_cluster_news(cluster_id)

        if not news_items:
            print("   ⚠️  No news found")
            return None

        print(f"   📰 Found {len(news_items)} news items")

        prompt = self._get_report_prompt(cluster, news_items)

        ai_start = time.time()
        report_data = self._call_gemini(prompt)
        generation_time = time.time() - ai_start

        if not report_data:
            return None

        word_count = len(report_data.content.split())
        print(f"   📝 Generated: {word_count} words")

        success = self._save_report(
            cluster_id=cluster_id,
            title=report_data.title,
            content=report_data.content,
            source_news_count=len(news_items)
        )

        return generation_time if success else None

    def _get_report_prompt(self, cluster: Dict, news_items: List[Dict]) -> str:
        """إنشاء برومبت التقرير - بدون JSON"""
        news_texts = []
        for idx, news in enumerate(news_items, 1):
            news_texts.append(f"""
[خبر {idx}]
العنوان: {news['title']}
المحتوى: {news['content'][:800]}...
المصدر: {news.get('source_name', 'غير معروف')}
""")

        combined_news = "\n---\n".join(news_texts)

        category = cluster.get('category_name', 'أخبار')
        tags = cluster.get('tags', [])
        tags_str = "، ".join(tags[:8]) if tags else ""

        # ✅ Prompt بسيط بدون JSON
        prompt = f"""أنت صحفي فلسطيني محترف. اكتب تقريراً إخبارياً من الأخبار التالية:

{combined_news}

التصنيف: {category}
الكلمات المفتاحية: {tags_str}

═══════════════════════════════════════
المطلوب: اكتب تقريراً بالشكل التالي بالضبط:
═══════════════════════════════════════

[العنوان]
اكتب عنوان جذاب من 10-15 كلمة

[المحتوى]
اكتب التقرير هنا ( 30 ل 90 كلمة تقريباً)
- ابدأ بفقرة تجيب على: من، ماذا، متى، أين، لماذا
- 3-5 فقرات منظمة
- لغة صحفية احترافية
- عربية فصحى واضحة
- لا تذكر "حسب المصادر" أو أسماء المصادر
- لا تخترع معلومات

═══════════════════════════════════════
مثال على الشكل المطلوب:
═══════════════════════════════════════

[العنوان]
غارات إسرائيلية على غزة توقع عشرات الشهداء وسط تصاعد العمليات العسكرية

[المحتوى]
شنت قوات الاحتلال الإسرائيلي سلسلة من الغارات الجوية على قطاع غزة...

═══════════════════════════════════════
الآن اكتب التقرير:
"""

        return prompt

    def _call_gemini(self, prompt: str, min_words: int = 30, max_words: int = 300, retries: int = 3) -> Optional[ReportData]:
        """استدعاء Gemini واستخراج البيانات"""
        for attempt in range(retries):
            try:
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config={
                        'temperature': 0.7,
                        'max_output_tokens': 2048
                    }
                )

                result_text = response.text.strip()

                # استخراج البيانات باستخدام الـ parser
                report_data = self.parser.parse(result_text)

                if not report_data:
                    print(f"   ⚠️  Could not parse response, attempt {attempt + 1}/{retries}")
                    print(f"   🔎 Preview: {result_text[:200]}...")
                    time.sleep(2)
                    continue

                # التحقق من الصحة
                is_valid, reason = report_data.is_valid(min_words, max_words)

                if not is_valid:
                    print(f"   ⚠️  {reason}, attempt {attempt + 1}/{retries}")
                    time.sleep(2)
                    continue

                return report_data

            except Exception as e:
                print(f"   ⚠️  Error: {str(e)[:100]}, attempt {attempt + 1}/{retries}")
                time.sleep(2)

                if attempt == retries - 1:
                    print(f"   ❌ Generation failed after {retries} attempts")
                    return None

        return None

    def _fetch_recently_updated_clusters(self, hours: int = 1) -> List[Dict]:
        """
        جلب الكلسترات التي تم تحديثها خلال آخر X ساعة
        والتي لديها تقارير قديمة (التقرير أقدم من تحديث الكلستر)
        """
        query = """
            SELECT 
                nc.id, nc.description, nc.tags, nc.category_id,
                c.name as category_name, nc.news_count, nc.created_at
            FROM news_clusters nc
            LEFT JOIN categories c ON nc.category_id = c.id
            INNER JOIN generated_report gr ON nc.id = gr.cluster_id
            WHERE nc.updated_at >= NOW() - INTERVAL '%s hours'
              AND nc.updated_at > gr.updated_at
            ORDER BY nc.updated_at DESC
            LIMIT 50;
        """
        self.cursor.execute(query, (hours,))
        return self._parse_clusters(self.cursor.fetchall())

    def _fetch_clusters_without_reports(self) -> List[Dict]:
        """جلب الكلسترات التي ليس لها تقارير"""
        query = """
            SELECT 
                nc.id, nc.description, nc.tags, nc.category_id,
                c.name as category_name, nc.news_count, nc.created_at
            FROM news_clusters nc
            LEFT JOIN categories c ON nc.category_id = c.id
            LEFT JOIN generated_report gr ON nc.id = gr.cluster_id
            WHERE gr.id IS NULL
            ORDER BY nc.created_at DESC
            LIMIT 100;
        """
        self.cursor.execute(query)
        return self._parse_clusters(self.cursor.fetchall())

    def _fetch_clusters_by_ids(self, cluster_ids: List[int]) -> List[Dict]:
        """جلب الكلسترات بواسطة IDs"""
        if not cluster_ids:
            return []
        query = """
            SELECT 
                nc.id, nc.description, nc.tags, nc.category_id,
                c.name as category_name, nc.news_count, nc.created_at
            FROM news_clusters nc
            LEFT JOIN categories c ON nc.category_id = c.id
            WHERE nc.id = ANY(%s)
        """
        self.cursor.execute(query, (cluster_ids,))
        return self._parse_clusters(self.cursor.fetchall())

    def _fetch_cluster_news(self, cluster_id: int) -> List[Dict]:
        """جلب أخبار cluster معين"""
        query = """
            SELECT 
                rn.id, rn.title, rn.content_text as content, s.name as source_name
            FROM raw_news rn
            JOIN news_cluster_members ncm ON rn.id = ncm.news_id
            LEFT JOIN sources s ON rn.source_id = s.id
            WHERE ncm.cluster_id = %s
            ORDER BY rn.published_at DESC
            LIMIT 20;
        """
        self.cursor.execute(query, (cluster_id,))
        columns = [desc[0] for desc in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def _parse_clusters(self, rows: List[Tuple]) -> List[Dict]:
        """تحويل نتائج query الكلسترات إلى dict"""
        columns = [desc[0] for desc in self.cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def _save_report(self, cluster_id: int, title: str, content: str, source_news_count: int) -> bool:
        """حفظ التقرير في قاعدة البيانات"""
        try:
            query = """
                INSERT INTO generated_report (cluster_id, title, content, source_news_count, status, published_at, created_at, updated_at)
                VALUES (%s, %s, %s, %s, 'draft', NOW(), NOW(), NOW())
                ON CONFLICT (cluster_id) DO UPDATE SET
                    title = EXCLUDED.title, content = EXCLUDED.content, source_news_count = EXCLUDED.source_news_count,
                    status = 'draft', updated_at = NOW();
            """
            self.cursor.execute(query, (cluster_id, title, content, source_news_count))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"   ❌ Error saving report: {e}")
            self.conn.rollback()
            return False


# ═══════════════════════════════════════════════════════════════
# للاختبار
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # اختبار الـ Parser
    test_texts = [
        """
[العنوان]
غارات إسرائيلية مكثفة على قطاع غزة توقع عشرات الشهداء

[المحتوى]
شنت قوات الاحتلال الإسرائيلي فجر اليوم سلسلة من الغارات الجوية العنيفة على مناطق متفرقة من قطاع غزة، ما أسفر عن استشهاد عشرات المواطنين وإصابة العشرات الآخرين.

وقد استهدفت الغارات مناطق سكنية في مدينة غزة وخان يونس ورفح، حيث دمرت عدداً من المنازل والمباني السكنية. وأفادت المصادر الطبية بوصول أعداد كبيرة من الشهداء والجرحى إلى المستشفيات.

وفي السياق ذاته، أعلنت فصائل المقاومة الفلسطينية عن استمرارها في التصدي للعدوان الإسرائيلي، مؤكدة جهوزيتها للدفاع عن الشعب الفلسطيني.
        """,
        """
العنوان: تصاعد التوتر في الضفة الغربية
المحتوى: شهدت مدن الضفة الغربية اليوم تصاعداً في المواجهات...
        """,
        """
**عنوان التقرير**
أحداث متسارعة في المنطقة

هذا هو نص المحتوى الكامل للتقرير الذي يتحدث عن الأحداث...
        """
    ]
    
    parser = TextParser()
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n{'='*50}")
        print(f"Test {i}:")
        result = parser.parse(text)
        if result:
            print(f"✅ Title: {result.title[:50]}...")
            print(f"✅ Content: {result.content[:100]}...")
            valid, reason = result.is_valid()
            print(f"✅ Valid: {valid} - {reason}")
        else:
            print("❌ Failed to parse")