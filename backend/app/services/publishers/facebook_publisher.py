#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📘 Facebook Publisher - Enhanced Version
نشر احترافي على فيسبوك مع تحسينات ذكية

Features:
- تنسيق هاشتاجات احترافي (كلمتين → كلمة_كلمة)
- تلخيص ذكي بـ Gemini للنصوص الطويلة
- إشارة للتفاصيل في الكابشن
- معالجة الكومنتات الطويلة
"""

import re
import json
import requests
from io import BytesIO
from typing import Dict, Optional
import google.generativeai as genai
import psycopg2


class FacebookPublisher:
    """
    ناشر فيسبوك احترافي
    
    يستقبل report_id ويقوم بـ:
    1. جلب المحتوى من API
    2. تنسيق احترافي (Hashtags + Text)
    3. تلخيص ذكي للنصوص الطويلة
    4. نشر على Facebook
    5. إضافة التقرير الكامل كتعليق
    """
    
    def __init__(
        self,
        fb_access_token: str = None,
        fb_page_id: str = None,
        api_base_url: str = None,
        gemini_api_key: str = None
    ):
        """
        Args:
            fb_access_token: Facebook Access Token
            fb_page_id: Facebook Page ID
            api_base_url: Base URL للـ API
            gemini_api_key: Gemini API Key (للتلخيص)
        """
        
        # Credentials - إما من parameters أو من environment
        import os
        
        self.FB_ACCESS_TOKEN = fb_access_token or os.getenv('FB_ACCESS_TOKEN') or "EAALZAKaM7VdABQYUJyh7pWly3fGhTZBonqOVVRTcZCPST5KmUrjiZBHZCQiXwpFtGj3oi1s1T90tzoXP5HehMlVnasFy5Tzni9zn5RuJFZCZBORX5QtAR2OQ2oZAuF74XZCTDl4lI9VIcOr3uaVyVx3RGKNb9lO4rn5fXVvoAbDgq55Ac2bOxgWCQzbN1NoK4fROdEkHajBoZCX3pwdJ7e2izg"
        self.FB_PAGE_ID = fb_page_id or os.getenv('FB_PAGE_ID') or "893918783798150"
        self.API_BASE_URL = (api_base_url or os.getenv('API_BASE_URL') or "http://localhost:8000").rstrip('/')
        self.GEMINI_API_KEY = gemini_api_key or os.getenv('GEMINI_API_KEY')
        
        # Facebook limits
        self.FB_COMMENT_MAX = 8000  # Facebook comment character limit
        
        # Initialize Gemini if key provided
        if self.GEMINI_API_KEY:
            genai.configure(api_key=self.GEMINI_API_KEY)
            self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
            print("✅ Gemini initialized for smart summarization")
        else:
            self.gemini_model = None
            print("⚠️  No Gemini key - using simple truncation")
        
        # Database connection
        try:
            from settings import DB_CONFIG
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print("✅ Database connected for status tracking")
        except Exception as e:
            print(f"⚠️  Database connection failed: {e}")
            print(f"   Status updates will be skipped")
            self.conn = None
            self.cursor = None
    
    # ==========================================
    # 🎯 Main Publish Function
    # ==========================================
    
    def publish(self, report_id: int) -> Dict:
        """
        نشر على Facebook
        
        Args:
            report_id: رقم التقرير
        
        Returns:
            {'success': True/False, 'post_id': '...', 'message': '...'}
        """
        
        print(f"\n{'='*70}")
        print(f"📘 Facebook Publishing - Report #{report_id}")
        print(f"{'='*70}\n")
        
        # 0. Update status to 'publishing'
        self._update_report_status(report_id, 'publishing')
        
        # 1. Get Content
        print("1️⃣ Getting Facebook content...")
        fb_content = self._get_facebook_content(report_id)
        if not fb_content:
            self._update_report_status(report_id, 'failed')
            return {'success': False, 'message': 'Failed to get content'}
        
        # 2. Format Caption (with note about details in comment)
        print("2️⃣ Formatting caption...")
        caption = self._format_caption(fb_content['title'], fb_content['content'])
        print(f"\n📝 Caption Preview:\n{caption[:200]}...\n")
        
        # 3. Get Image
        print("3️⃣ Getting image...")
        image = self._get_image(report_id)
        if not image:
            self._update_report_status(report_id, 'failed')
            return {'success': False, 'message': 'Failed to get image'}
        
        # 4. Publish to Facebook
        print("4️⃣ Publishing to Facebook...")
        result = self._publish_photo(caption, image)
        
        if not result['success']:
            self._update_report_status(report_id, 'failed')
            return result
        
        post_id = result['post_id']
        print(f"✅ Published! Post ID: {post_id}")
        
        # 5. Add Full Report as Comment
        print("5️⃣ Adding full report as comment...")
        full_report = self._get_full_report(report_id)
        
        if full_report:
            # Smart handling for long reports
            comment_text = self._prepare_comment(full_report)
            self._add_comment(post_id, comment_text)
        
        # 6. Update status to 'facebook_published'
        self._update_report_status(report_id, 'facebook_published')
        
        print(f"\n{'='*70}")
        print(f"✅ Publishing Complete!")
        print(f"{'='*70}\n")
        
        return {'success': True, 'post_id': post_id}
    
    # ==========================================
    # 📊 Data Fetching
    # ==========================================
    
    def _get_facebook_content(self, report_id: int) -> Optional[Dict]:
        """جلب محتوى Facebook"""
        try:
            url = f"{self.API_BASE_URL}/api/v1/social-media/by-report/{report_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ API error: {response.status_code}")
                return None
            
            data = response.json()
            content_json = data.get('content', '{}')
            social_posts = json.loads(content_json)
            fb_data = social_posts.get('facebook', {})
            
            return {
                'title': fb_data.get('title', ''),
                'content': fb_data.get('content', '')
            }
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def _get_image(self, report_id: int) -> Optional[BytesIO]:
        """جلب الصورة (Generated → Original)"""
        
        # Try Generated
        img = self._get_generated_image(report_id)
        if img:
            return img
        
        # Try Original
        img = self._get_original_image(report_id)
        if img:
            return img
        
        print("❌ No image found")
        return None
    
    def _get_generated_image(self, report_id: int) -> Optional[BytesIO]:
        """Get Generated Image"""
        try:
            url = f"{self.API_BASE_URL}/api/v1/images/by-report/{report_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            image_url = data.get('file_url')
            
            if not image_url:
                return None
            
            img_response = requests.get(image_url, timeout=15)
            if img_response.status_code == 200:
                print("✅ Using Generated Image")
                return BytesIO(img_response.content)
            
            return None
        except:
            return None
    
    def _get_original_image(self, report_id: int) -> Optional[BytesIO]:
        """Get Original Image"""
        try:
            url = f"{self.API_BASE_URL}/api/v1/reports/reports/{report_id}/raw-news-images"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if isinstance(data, list) and len(data) > 0:
                image_url = data[0].get('url') or data[0].get('image_url')
            elif isinstance(data, dict):
                image_url = data.get('url') or data.get('image_url')
            else:
                return None
            
            if not image_url:
                return None
            
            img_response = requests.get(image_url, timeout=15)
            if img_response.status_code == 200:
                print("✅ Using Original Image")
                return BytesIO(img_response.content)
            
            return None
        except:
            return None
    
    def _get_full_report(self, report_id: int) -> Optional[str]:
        """جلب التقرير الكامل"""
        try:
            url = f"{self.API_BASE_URL}/api/v1/reports/{report_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            title = data.get('title', '')
            content = data.get('content', '') or data.get('body', '')
            
            if title and content:
                return f"{title}\n\n{content}"
            return content or title
        except:
            return None
    
    # ==========================================
    # 🎨 Text Formatting
    # ==========================================
    
    def _format_caption(self, title: str, content: str) -> str:
        """
        تنسيق الكابشن بشكل احترافي
        
        Structure:
        [Title]
        
        [Content]
        
        📖 التفاصيل الكاملة في التعليق الأول ⬇️
        
        #hashtags
        """
        
        # فصل المحتوى عن الهاشتاجات - محسّن
        # ابحث عن أول # في النص
        hashtag_start = content.find('#')
        
        if hashtag_start != -1:
            # في هاشتاجات
            main_content = content[:hashtag_start].strip()
            hashtags = content[hashtag_start:].strip()
            
            # تنسيق الهاشتاجات
            hashtags = self._format_hashtags(hashtags)
            
            print(f"   📌 Found hashtags: {hashtags[:50]}...")
        else:
            # ما في هاشتاجات
            main_content = content.strip()
            hashtags = ''
            print(f"   ⚠️  No hashtags found in content")
        
        # تجميع الكابشن
        result = []
        
        if title:
            result.append(title.strip())
        
        if main_content:
            result.append(main_content)
        
        # إضافة إشارة للتفاصيل
        result.append("📖 التفاصيل الكاملة في التعليق الأول ⬇️")
        
        if hashtags:
            result.append(hashtags)
        
        final = '\n\n'.join(result)
        
        print(f"   ✅ Caption ready ({len(final)} chars)")
        
        return final
    
    def _format_hashtags(self, text: str) -> str:
        """
        تنسيق الهاشتاجات باستخدام Gemini لدقة 100%
        
        يرسل الهاشتاجات لـ Gemini ليصححها بناءً على اللغة العربية
        """
        
        print(f"   🔧 Formatting hashtags with AI...")
        
        # استخراج الهاشتاجات
        hashtags = re.findall(r'#[\w\u0600-\u06FF_]+', text)
        
        if not hashtags:
            print(f"   ⚠️  No hashtags found")
            return text
        
        print(f"   📊 Found {len(hashtags)} hashtags: {', '.join(hashtags)}")
        
        # لو في Gemini، نستخدمه لتصحيح الهاشتاجات
        if self.gemini_model:
            try:
                corrected = self._correct_hashtags_with_gemini(hashtags)
                
                # استبدال الهاشتاجات القديمة بالمصححة
                result = text
                for old, new in zip(hashtags, corrected):
                    if old != new:
                        result = result.replace(old, new, 1)
                        print(f"   ✓ {old} → {new}")
                
                return result
                
            except Exception as e:
                print(f"   ⚠️  Gemini hashtag correction failed: {e}")
                # Fallback to simple method
                return self._simple_hashtag_format(text)
        else:
            # لو ما في Gemini، نستخدم الطريقة البسيطة
            return self._simple_hashtag_format(text)
    
    def _correct_hashtags_with_gemini(self, hashtags: list) -> list:
        """
        تصحيح الهاشتاجات باستخدام Gemini بدقة 100%
        """
        
        hashtags_str = '\n'.join(hashtags)
        
        prompt = f"""أنت خبير في اللغة العربية والهاشتاجات الاحترافية.

مهمتك: تصحيح الهاشتاجات التالية لتكون احترافية ومقروءة.

القواعد:
1. إذا الهاشتاج كلمتين أو أكثر ملتصقتين → افصلهم بـ _
2. احترف بالتقسيم حسب المعنى واللغة العربية الصحيحة
3. حافظ على # في البداية
4. لا تغير المعنى أو تضيف كلمات جديدة
5. أرجع نفس عدد الهاشتاجات بنفس الترتيب

مثال:
المدخل: #قواتحفظالسلام
المخرج: #قوات_حفظ_السلام

المدخل: #انتهاكصارخ  
المخرج: #انتهاك_صارخ

الهاشتاجات للتصحيح:
{hashtags_str}

أرجع الهاشتاجات المصححة فقط (كل هاشتاج في سطر) بدون أي شرح أو كلام إضافي:"""
        
        response = self.gemini_model.generate_content(prompt)
        corrected_text = response.text.strip()
        
        # تنظيف النتيجة
        corrected = []
        for line in corrected_text.split('\n'):
            line = line.strip()
            if line and line.startswith('#'):
                corrected.append(line)
        
        # تأكد أن العدد مطابق
        if len(corrected) != len(hashtags):
            print(f"   ⚠️  Gemini returned {len(corrected)} hashtags, expected {len(hashtags)}")
            return hashtags  # أرجع الأصلي
        
        print(f"   ✅ Gemini corrected {len(corrected)} hashtags")
        return corrected
    
    def _simple_hashtag_format(self, text: str) -> str:
        """
        طريقة بسيطة لتنسيق الهاشتاجات (fallback)
        """
        
        # فصل الهاشتاجات الملتصقة
        while re.search(r'(#[\w\u0600-\u06FF_]+)(#)', text):
            text = re.sub(r'(#[\w\u0600-\u06FF_]+)(#)', r'\1 \2', text)
        
        # معالجة كل هاشتاج
        hashtags = re.findall(r'#[\w\u0600-\u06FF_]+', text)
        
        for old_tag in hashtags:
            tag_text = old_tag[1:]
            
            if len(tag_text) <= 8:
                continue
            
            new_tag_text = self._split_arabic_words(tag_text)
            
            if new_tag_text != tag_text:
                new_tag = '#' + new_tag_text
                text = text.replace(old_tag, new_tag, 1)
        
        return text
    
    def _split_arabic_words(self, text: str) -> str:
        """
        فصل الكلمات العربية الملتصقة بذكاء
        
        استراتيجية:
        - التعرف على "ال" التعريف
        - التعرف على حروف بداية الكلمات الشائعة
        - التقسيم الذكي
        """
        
        if len(text) <= 8:
            return text
        
        result = text
        
        # Pattern 1: "ال" في الوسط
        # مثلاً: "مهرجانالمؤسس" → "مهرجان_المؤسس"
        if 'ال' in text[2:]:  # ليس في البداية
            result = re.sub(r'([^\s])ال([^\s])', r'\1_ال\2', result)
        
        # Pattern 2: الكلمات الطويلة جداً (+15 حرف)
        # نقسمها عند المنتصف تقريباً
        if len(result) > 15 and '_' not in result:
            mid = len(result) // 2
            
            # نبحث عن أفضل مكان للتقسيم بالقرب من المنتصف
            # حروف تكون عادة بداية كلمة
            split_chars = ['ا', 'م', 'ب', 'ل', 'و', 'ف', 'ع', 'ت', 'ن', 'ي', 'ر', 'س', 'ش']
            
            best_split = mid
            for i in range(mid - 2, min(mid + 3, len(result))):
                if i > 3 and i < len(result) - 3 and result[i] in split_chars:
                    best_split = i
                    break
            
            if best_split > 3 and best_split < len(result) - 3:
                result = result[:best_split] + '_' + result[best_split:]
        
        return result
    
    def _prepare_comment(self, full_report: str) -> str:
        """
        تحضير الكومنت بطريقة ذكية
        
        دائماً يفحص النهاية للتأكد من عدم وجود قطع
        """
        
        print(f"   📄 Report length: {len(full_report)} chars")
        
        # إضافة header احترافي
        header = "📰 التفاصيل الكاملة للخبر\n" + "─" * 40 + "\n\n"
        full_text = header + full_report
        
        print(f"   📄 With header: {len(full_text)} chars")
        print(f"   📏 Limit: {self.FB_COMMENT_MAX} chars")
        
        # دائماً نفحص النهاية (حتى لو النص قصير)
        print(f"   🔍 Checking for incomplete ending...")
        
        # فحص آخر 50 حرف - لو ما في نقطة أو علامة ترقيم معناها مقطوع
        last_50 = full_report[-50:]
        has_proper_ending = any(char in last_50 for char in ['.', '؟', '!', '。'])
        
        # لو النص طويل جداً، لازم نقصه
        if len(full_text) > self.FB_COMMENT_MAX:
            print(f"   ⚠️  Report too long ({len(full_text)} chars) - Processing...")
            
            # لو في Gemini: تلخيص ذكي
            if self.gemini_model:
                print(f"   🤖 Using Gemini for summarization...")
                return self._summarize_with_gemini(full_report)
            
            # لو ما في Gemini: قص ذكي
            print(f"   ✂️ Using smart truncate...")
            return self._smart_truncate(full_text)
        
        # النص قصير بس نفحص النهاية
        elif not has_proper_ending:
            print(f"   ⚠️  Incomplete ending detected!")
            
            # استخدام Gemini لإصلاح النهاية
            if self.gemini_model:
                print(f"   🤖 Using Gemini to fix ending...")
                fixed_report = self._fix_report_ending_only(full_report)
                return header + fixed_report
            else:
                # Fallback بسيط
                print(f"   ✂️ Using simple fix...")
                fixed_report = self._simple_ending_fix_minimal(full_report)
                return header + fixed_report
        else:
            # النص قصير ونهايته سليمة
            print(f"   ✅ Report is complete and fits in comment")
            return full_text
    
    def _summarize_with_gemini(self, text: str) -> str:
        """
        تلخيص ذكي باستخدام Gemini
        
        يحافظ على:
        - جميع التفاصيل المهمة
        - السياق الكامل
        - الأرقام والإحصائيات
        - الأسماء والأماكن
        """
        
        print(f"🤖 Starting Gemini summarization...")
        print(f"   Original length: {len(text)} chars")
        
        try:
            prompt = f"""أنت محرر صحفي محترف. لديك تقرير إخباري طويل يجب اختصاره ليناسب تعليق فيسبوك (أقل من 7500 حرف).

متطلبات التلخيص:
1. احتفظ بجميع التفاصيل المهمة والأرقام والإحصائيات
2. احتفظ بالأسماء والأماكن والتواريخ
3. احتفظ بالسياق الكامل للخبر
4. اكتب بأسلوب صحفي احترافي مباشر
5. لا تضف معلومات من عندك
6. الناتج يجب أن يكون أقل من 7500 حرف
7. لا تكتب مقدمات مثل "إليك التلخيص" - ابدأ مباشرة بالمحتوى

التقرير الأصلي:
{text}

التلخيص الاحترافي (مباشرة):"""
            
            print(f"   Sending to Gemini...")
            response = self.gemini_model.generate_content(prompt)
            summary = response.text.strip()
            
            print(f"   Received from Gemini: {len(summary)} chars")
            
            # إزالة أي مقدمات غير مرغوبة
            unwanted_prefixes = [
                'إليك التلخيص',
                'التلخيص:',
                'ملخص:',
                'هنا التلخيص',
                'التقرير الملخص'
            ]
            
            for prefix in unwanted_prefixes:
                if summary.startswith(prefix):
                    summary = summary[len(prefix):].strip()
                    summary = summary.lstrip(':').strip()
            
            # إضافة header
            header = "📰 التفاصيل الكاملة للخبر\n" + "─" * 40 + "\n\n"
            result = header + summary
            
            # تأكد من الطول
            if len(result) > self.FB_COMMENT_MAX:
                print(f"   ⚠️  Gemini output too long, truncating...")
                excess = len(result) - (self.FB_COMMENT_MAX - 150)
                summary = summary[:-excess]
                result = header + summary
                result += "\n\n... (للمزيد، تابع موقعنا)"
            
            print(f"✅ Gemini summary complete: {len(result)} chars")
            return result
        
        except Exception as e:
            print(f"❌ Gemini error: {type(e).__name__}: {str(e)}")
            print(f"   Falling back to smart truncate...")
            
            # إضافة header قبل الإرسال للـ truncate
            full_with_header = "📰 التفاصيل الكاملة للخبر\n" + "─" * 40 + "\n\n" + text
            return self._smart_truncate(full_with_header)
    
    def _smart_truncate(self, text: str) -> str:
        """
        قص ذكي مع إصلاح الجمل المقطوعة باستخدام Gemini
        """
        
        max_length = self.FB_COMMENT_MAX - 200  # مساحة للخاتمة
        
        if len(text) <= max_length:
            return text
        
        print(f"   ✂️ Truncating from {len(text)} to ~{max_length} chars...")
        
        # قص عند آخر نقطة أو علامة ترقيم
        truncated = text[:max_length]
        
        # ابحث عن آخر نقطة/علامة ترقيم
        last_period = truncated.rfind('.')
        last_newline = truncated.rfind('\n')
        last_question = truncated.rfind('؟')
        last_exclamation = truncated.rfind('!')
        
        cut_point = max(last_period, last_newline, last_question, last_exclamation)
        
        if cut_point > max_length * 0.7:
            result = text[:cut_point + 1]
        else:
            # قص عند آخر مسافة
            last_space = truncated.rfind(' ')
            if last_space > max_length * 0.7:
                result = text[:last_space]
            else:
                result = truncated
        
        # استخدام Gemini لإصلاح النهاية لو مقطوعة
        if self.gemini_model:
            result = self._fix_incomplete_ending(result)
        else:
            # إضافة footer بسيط
            result += "\n\n" + "─" * 40
            result += "\n📎 للمزيد من التفاصيل الكاملة، تابع موقعنا"
        
        print(f"   ✅ Final length: {len(result)} chars")
        return result
    
    def _fix_report_ending_only(self, text: str) -> str:
        """
        إصلاح نهاية التقرير فقط (بدون قص)
        
        يستخدم Gemini لإكمال أو استبدال الجملة الأخيرة المقطوعة
        """
        
        try:
            # آخر 200 حرف للسياق
            ending = text[-200:] if len(text) > 200 else text
            
            prompt = f"""أنت محرر صحفي. لديك تقرير إخباري نهايته قد تكون مقطوعة.

مهمتك:
1. افحص آخر جملة في النص
2. إذا كانت مقطوعة (كلمة ناقصة، جملة غير مكتملة) → احذف الجملة المقطوعة واستبدلها بجملة ختامية كاملة ومناسبة
3. إذا كانت مكتملة → لا تغير شيئاً

مثال على جملة مقطوعة:
"...العاملة على الحدود الل"  ← مقطوع!
التصحيح: احذف "العاملة على الحدود الل" واكتب "ويتطلب هذا الحادث تحقيقاً دولياً فورياً."

القواعد:
- احذف الجملة المقطوعة بالكامل
- اكتب جملة ختامية جديدة كاملة (15-20 كلمة)
- الجملة الجديدة يجب أن تنهي التقرير بشكل طبيعي
- لا تضيف معلومات جديدة غير موجودة في السياق
- أرجع آخر 150-200 حرف فقط بعد الإصلاح (بدون مقدمات أو شروحات)

آخر 200 حرف من التقرير:
{ending}

الإصلاح (آخر 150-200 حرف فقط):"""
            
            response = self.gemini_model.generate_content(prompt)
            fixed_ending = response.text.strip()
            
            # تنظيف من أي مقدمات
            for prefix in ['الإصلاح:', 'التصحيح:', 'النص:', 'إليك', 'هنا']:
                if fixed_ending.startswith(prefix):
                    fixed_ending = fixed_ending.split('\n', 1)[-1].strip()
            
            # استبدال آخر 200 حرف
            replace_len = min(200, len(text))
            result = text[:-replace_len] + fixed_ending
            
            print(f"   ✅ Gemini fixed ending")
            return result
            
        except Exception as e:
            print(f"   ⚠️  Gemini fix failed: {e}")
            return self._simple_ending_fix_minimal(text)
    
    def _simple_ending_fix_minimal(self, text: str) -> str:
        """
        إصلاح بسيط للنهاية - يحذف آخر جملة مقطوعة
        """
        
        # ابحث عن آخر نقطة أو علامة ترقيم
        last_period = text.rfind('.')
        last_question = text.rfind('؟')
        last_exclamation = text.rfind('!')
        
        last_complete = max(last_period, last_question, last_exclamation)
        
        if last_complete > len(text) * 0.7:  # على الأقل 70% من النص
            # قص عند آخر جملة كاملة
            result = text[:last_complete + 1]
            print(f"   ✅ Removed incomplete ending")
            return result
        else:
            # النص كله تقريباً بدون نقاط - نضيف نقطة فقط
            result = text.rstrip() + '.'
            print(f"   ✅ Added period")
            return result
    
    def _fix_incomplete_ending(self, text: str) -> str:
        """
        إصلاح النهايات المقطوعة باستخدام Gemini
        
        يحذف الجمل المقطوعة ويضيف ختام احترافي
        """
        
        try:
            print(f"   🔧 Checking for incomplete ending...")
            
            # آخر 300 حرف للسياق
            ending_context = text[-300:] if len(text) > 300 else text
            
            prompt = f"""أنت محرر صحفي محترف. لديك نص إخباري قد يكون مقطوعاً في النهاية.

مهمتك:
1. افحص آخر جملة في النص بدقة
2. إذا كانت مقطوعة (كلمة غير مكتملة، جملة ناقصة، أو نهاية مفاجئة) → احذفها تماماً
3. اكتب جملة ختامية واحدة احترافية (15-20 كلمة) تلخص الموضوع أو تنهيه بشكل طبيعي
4. الجملة الختامية يجب أن تكون مرتبطة بالسياق ولكن مستقلة (لا تكمل الجملة المقطوعة)

أمثلة:

مثال 1 - نص مقطوع:
"...العاملة على الحدود الل"
التصحيح: احذف "العاملة على الحدود الل" → أضف "ويشكل هذا الحادث انتهاكاً خطيراً للقانون الدولي ويتطلب تحقيقاً فورياً."

مثال 2 - نص مكتمل:
"...وتثير هذه الحوادث تساؤلات جدية."
التصحيح: لا حذف → أضف فقط "وتدعو المجتمع الدولي للتدخل العاجل لحماية قوات حفظ السلام."

القواعد المهمة:
- لا تكمل الجملة المقطوعة - احذفها واكتب جملة جديدة
- الجملة الجديدة يجب أن تكون ختامية وواضحة
- لا تضيف معلومات جديدة غير موجودة في السياق
- أرجع فقط النص المصلح (آخر 200-250 حرف تقريباً بعد الإصلاح)

النص (آخر 300 حرف):
{ending_context}

النص المصلح (أرجع آخر 200-250 حرف فقط مع الجملة الختامية الجديدة):"""
            
            response = self.gemini_model.generate_content(prompt)
            fixed_ending = response.text.strip()
            
            # حساب كم حرف نستبدل
            # نأخذ أطول من 200 أو 300 حسب طول النص الأصلي
            replace_length = min(300, len(text) // 2)
            
            # استبدال النهاية
            result = text[:-replace_length] + fixed_ending
            
            # تنظيف - إزالة أي تكرار أو مقدمات من Gemini
            unwanted_prefixes = ['النص المصلح:', 'التصحيح:', 'إليك', 'هنا']
            for prefix in unwanted_prefixes:
                if prefix in result[-300:]:
                    # ابحث عن السطر الأول بعد المقدمة
                    idx = result.rfind(prefix)
                    if idx != -1:
                        next_line = result[idx:].find('\n')
                        if next_line != -1:
                            result = result[:idx] + result[idx + next_line + 1:]
            
            # إضافة footer
            result += "\n\n" + "─" * 40
            result += "\n📎 للمزيد من التفاصيل، تابع موقعنا"
            
            print(f"   ✅ Gemini fixed incomplete ending")
            return result
            
        except Exception as e:
            print(f"   ⚠️  Gemini ending fix failed: {e}")
            # Fallback - حذف آخر جملة غير مكتملة يدوياً
            return self._simple_ending_fix(text)
    
    # ==========================================
    # 📤 Facebook API
    # ==========================================
    
    def _publish_photo(self, message: str, image: BytesIO) -> Dict:
        """نشر صورة على Facebook"""
        
        url = f"https://graph.facebook.com/v18.0/{self.FB_PAGE_ID}/photos"
        
        payload = {
            'message': message,
            'access_token': self.FB_ACCESS_TOKEN
        }
        
        files = {
            'source': ('news.jpg', image, 'image/jpeg')
        }
        
        try:
            response = requests.post(url, data=payload, files=files, timeout=30)
            result = response.json()
            
            if 'id' in result:
                return {'success': True, 'post_id': result['id']}
            else:
                error = result.get('error', {}).get('message', 'Unknown')
                return {'success': False, 'message': f'Facebook error: {error}'}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def _add_comment(self, post_id: str, text: str):
        """إضافة تعليق"""
        
        url = f"https://graph.facebook.com/v18.0/{post_id}/comments"
        
        payload = {
            'message': text,
            'access_token': self.FB_ACCESS_TOKEN
        }
        
        try:
            response = requests.post(url, data=payload, timeout=15)
            result = response.json()
            
            if 'id' in result:
                print(f"✅ Comment added (ID: {result['id']})")
            else:
                error = result.get('error', {}).get('message', 'Unknown')
                print(f"⚠️  Comment failed: {error}")
        except Exception as e:
            print(f"⚠️  Comment failed: {e}")


# ==========================================
# 🧪 Testing
# ==========================================

if __name__ == '__main__':
    import sys
    import os
    
    # Load from .env if exists
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except:
        pass
    
    publisher = FacebookPublisher()
    
    if len(sys.argv) > 1:
        report_id = int(sys.argv[1])
    else:
        report_id = int(input("Enter report_id: "))
    
    result = publisher.publish(report_id)
    
    print(f"\n{'='*70}")
    print(f"📊 FINAL RESULT:")
    print(f"{'='*70}")
    print(f"Success: {result['success']}")
    if result.get('post_id'):
        print(f"Post ID: {result['post_id']}")
    if result.get('message'):
        print(f"Message: {result['message']}")
    print(f"{'='*70}\n")
    
    def _simple_ending_fix(self, text: str) -> str:
        """
        طريقة بسيطة لإصلاح النهايات المقطوعة (fallback)
        """
        
        # ابحث عن آخر نقطة أو علامة ترقيم كاملة
        last_period = text.rfind('.')
        last_question = text.rfind('؟')
        last_exclamation = text.rfind('!')
        
        # اختر أبعد نقطة
        last_complete = max(last_period, last_question, last_exclamation)
        
        if last_complete > len(text) * 0.8:
            result = text[:last_complete + 1]
        else:
            result = text[:-50].rstrip() + '.'
        
        result += "\n\n" + "─" * 40
        result += "\n📎 للمزيد من التفاصيل، تابع موقعنا"
        
        print(f"   ✅ Simple ending fix applied")
        return result

    
    # ==========================================
    # 📊 Database Status Updates
    # ==========================================
    
    def _update_report_status(self, report_id: int, new_status: str):
        """
        تحديث حالة التقرير في الـ Database
        
        Args:
            report_id: ID التقرير
            new_status: الحالة الجديدة
                - 'publishing': تحت المعالجة
                - 'facebook_published': نشر على Facebook
                - 'facebook_instagram_published': نشر على FB + IG
                - 'published': نشر كامل
                - 'failed': فشل النشر
        """
        
        if not self.conn or not self.cursor:
            print(f"   ⚠️  Database not connected - skipping status update")
            return
        
        try:
            # Update status and timestamp
            sql = """
                UPDATE generated_report 
                SET status = %s, 
                    updated_at = NOW()
            """
            params = [new_status]
            
            # إذا النشر نجح، نحدث published_at
            if 'published' in new_status.lower():
                sql += ", published_at = NOW()"
            
            sql += " WHERE id = %s"
            params.append(report_id)
            
            self.cursor.execute(sql, params)
            self.conn.commit()
            
            print(f"   📊 Status updated: {new_status}")
            
        except Exception as e:
            print(f"   ⚠️  Status update failed: {e}")
            self.conn.rollback()