#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📸 Instagram Publisher - Complete Version
نشر احترافي على Instagram (Posts + Reels)

Features:
- نشر Posts (صورة + caption + hashtags + comment)
- نشر Reels (فيديو + caption + hashtags)
- تنسيق هاشتاجات احترافي بـ Gemini
- معالجة ذكية للنصوص الطويلة
- Status tracking في Database
"""

import re
import json
import time
import requests
from io import BytesIO
from typing import Dict, Optional
import google.generativeai as genai
import psycopg2


class InstagramPublisher:
    """
    ناشر Instagram احترافي
    
    يدعم:
    1. Posts: صورة + caption + hashtags + comment
    2. Reels: فيديو + caption + hashtags
    """
    
    # Content Type IDs
    INSTAGRAM_POST_CONTENT_ID = 9   # صورة/بوست
    INSTAGRAM_REEL_CONTENT_ID = 8   # فيديو/ريل
    
    def __init__(
        self,
        ig_user_id: str = None,
        fb_access_token: str = None,
        api_base_url: str = None,
        gemini_api_key: str = None
    ):
        """
        Args:
            ig_user_id: Instagram Business Account ID
            fb_access_token: Facebook Access Token
            api_base_url: Base URL للـ API
            gemini_api_key: Gemini API Key
        """
        
        import os
        
        self.IG_USER_ID = ig_user_id or os.getenv('IG_GAZA_USER_ID')
        self.FB_ACCESS_TOKEN = fb_access_token or os.getenv('FB_gaza_ACCESS_TOKEN')
        self.API_BASE_URL = (api_base_url or os.getenv('API_BASE_URL') or "http://localhost:8000").rstrip('/')
        self.GEMINI_API_KEY = gemini_api_key or os.getenv('GEMINI_API_KEY')
        
        # Validate credentials
        if not self.IG_USER_ID:
            print("❌ ERROR: IG_USER_ID not found!")
            print("   Add IG_USER_ID to .env file")
        else:
            print(f"✅ IG_USER_ID: {self.IG_USER_ID}")
        
        if not self.FB_ACCESS_TOKEN:
            print("❌ ERROR: FB_ACCESS_TOKEN not found!")
        else:
            print(f"✅ FB_ACCESS_TOKEN: {self.FB_ACCESS_TOKEN[:20]}...")
        
        # Instagram limits
        self.IG_CAPTION_MAX = 2200  # Instagram caption limit
        self.IG_COMMENT_MAX = 2200  # Instagram comment limit
        
        # Initialize Gemini
        if self.GEMINI_API_KEY:
            genai.configure(api_key=self.GEMINI_API_KEY)
            self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
            print("✅ Gemini initialized")
        else:
            self.gemini_model = None
            print("⚠️  No Gemini key")
        
        # Database connection
        try:
            # Try importing DB_CONFIG first
            try:
                from settings import DB_CONFIG
                self.conn = psycopg2.connect(**DB_CONFIG)
            except:
                # Fallback: direct connection
                db_config = {
                    'host': os.getenv('DB_HOST', 'localhost'),
                    'port': os.getenv('DB_PORT', 5432),
                    'database': os.getenv('DB_NAME', 'postgres'),
                    'user': os.getenv('DB_USER', 'postgres'),
                    'password': os.getenv('DB_PASSWORD', '')
                }
                self.conn = psycopg2.connect(**db_config)
            
            self.cursor = self.conn.cursor()
            print("✅ Database connected")
        except Exception as e:
            print(f"⚠️  Database connection failed: {e}")
            self.conn = None
            self.cursor = None
    
    # ==========================================
    # 🎯 Main Publish Functions
    # ==========================================
    
    def publish_post(self, report_id: int) -> Dict:
        """
        نشر Post على Instagram
        
        صورة + caption + hashtags + comment بالتقرير الكامل
        """
        
        print(f"\n{'='*70}")
        print(f"📸 Instagram Post Publishing - Report #{report_id}")
        print(f"{'='*70}\n")
        
        # Update status
        self._update_report_status(report_id, 'publishing')
        
        # 1. Get Instagram content
        print("1️⃣ Getting Instagram content...")
        ig_content = self._get_instagram_content(report_id)
        if not ig_content:
            self._update_report_status(report_id, 'failed')
            return {'success': False, 'message': 'Failed to get Instagram content'}
        
        # 2. Format caption
        print("2️⃣ Formatting caption...")
        caption = self._format_caption(ig_content['title'], ig_content['content'])
        print(f"\n📝 Caption: {caption[:150]}...\n")
        
        # 3. Get image
        print("3️⃣ Getting image...")
        image_url = self._get_image_url(report_id)
        if not image_url:
            self._update_report_status(report_id, 'failed')
            return {'success': False, 'message': 'Failed to get image'}
        
        # 4. Publish to Instagram
        print("4️⃣ Publishing to Instagram...")
        result = self._publish_instagram_post(image_url, caption)
        
        if not result['success']:
            self._update_report_status(report_id, 'failed')
            return result
        
        media_id = result['media_id']
        print(f"✅ Published! Media ID: {media_id}")
        
        # 5. Add full report as comment
        print("5️⃣ Adding full report as comment...")
        full_report = self._get_full_report(report_id)
        if full_report:
            comment_text = self._prepare_comment(full_report)
            self._add_comment(media_id, comment_text)
        
        # 6. Update status
        current_status = self._get_current_status(report_id)
        new_status = self._calculate_new_status(current_status, 'instagram')
        self._update_report_status(report_id, new_status)
        
        print(f"\n{'='*70}")
        print(f"✅ Instagram Post Complete!")
        print(f"{'='*70}\n")
        
        return {'success': True, 'media_id': media_id, 'type': 'post'}
    
    def publish_reel(self, report_id: int) -> Dict:
        """
        نشر Reel على Instagram
        
        فيديو + caption + hashtags
        """
        
        print(f"\n{'='*70}")
        print(f"🎬 Instagram Reel Publishing - Report #{report_id}")
        print(f"{'='*70}\n")
        
        # Update status
        self._update_report_status(report_id, 'publishing')
        
        # 1. Get Instagram reel content
        print("1️⃣ Getting Instagram reel content...")
        reel_content = self._get_reel_content(report_id)
        if not reel_content:
            self._update_report_status(report_id, 'failed')
            return {'success': False, 'message': 'Failed to get reel content'}
        
        # 2. Format caption
        print("2️⃣ Formatting caption...")
        caption = self._format_reel_caption(reel_content)
        print(f"\n📝 Caption: {caption[:150]}...\n")
        
        # 3. Get video URL
        video_url = reel_content.get('video_url')
        if not video_url:
            self._update_report_status(report_id, 'failed')
            return {'success': False, 'message': 'No video URL found'}
        
        # 4. Publish reel
        print("4️⃣ Publishing reel to Instagram...")
        result = self._publish_instagram_reel(video_url, caption)
        
        if not result['success']:
            self._update_report_status(report_id, 'failed')
            return result
        
        media_id = result['media_id']
        print(f"✅ Published! Reel ID: {media_id}")
        
        # 5. Update status
        current_status = self._get_current_status(report_id)
        new_status = self._calculate_new_status(current_status, 'instagram')
        self._update_report_status(report_id, new_status)
        
        print(f"\n{'='*70}")
        print(f"✅ Instagram Reel Complete!")
        print(f"{'='*70}\n")
        
        return {'success': True, 'media_id': media_id, 'type': 'reel'}
    
    def publish(self, report_id: int, content_type: str = 'both') -> Dict:
        """
        نشر حسب النوع
        
        Args:
            report_id: رقم التقرير
            content_type: 'post' | 'reel' | 'both'
        """
        
        if content_type == 'both':
            return self.publish_both(report_id)
        elif content_type == 'reel':
            return self.publish_reel(report_id)
        else:
            return self.publish_post(report_id)
    
    def publish_both(self, report_id: int) -> Dict:
        """
        نشر Post + Reel سوا
        
        ينشر النوعين في نفس الوقت
        """
        
        print(f"\n{'='*70}")
        print(f"📸🎬 Instagram Post + Reel Publishing - Report #{report_id}")
        print(f"{'='*70}\n")
        
        results = {
            'post': {'success': False, 'message': 'Not attempted'},
            'reel': {'success': False, 'message': 'Not attempted'},
            'success': False
        }
        
        try:
            # 1. Publish Post
            print("🔹 Publishing Post...")
            post_result = self.publish_post(report_id)
            results['post'] = post_result if post_result else {'success': False, 'message': 'Post method returned None'}
            
            if not results['post']['success']:
                print(f"❌ Post failed: {results['post'].get('message')}")
            else:
                print(f"✅ Post published: {results['post']['media_id']}\n")
            
            # 2. Publish Reel
            print("🔹 Publishing Reel...")
            reel_result = self.publish_reel(report_id)
            results['reel'] = reel_result if reel_result else {'success': False, 'message': 'Reel method returned None'}
            
            if not results['reel']['success']:
                print(f"❌ Reel failed: {results['reel'].get('message')}")
            else:
                print(f"✅ Reel published: {results['reel']['media_id']}\n")
            
            # 3. Overall success
            results['success'] = results['post']['success'] or results['reel']['success']
            
        except Exception as e:
            error_msg = f"Exception in publish_both: {str(e)}"
            print(f"❌ {error_msg}")
            results['post'] = {'success': False, 'message': error_msg}
            results['reel'] = {'success': False, 'message': error_msg}
            results['success'] = False
        
        # 4. Summary
        print(f"\n{'='*70}")
        print(f"📊 BOTH RESULTS:")
        print(f"{'='*70}")
        print(f"Post: {'✅ ' + results['post'].get('media_id', 'N/A') if results['post']['success'] else '❌ Failed'}")
        print(f"Reel: {'✅ ' + results['reel'].get('media_id', 'N/A') if results['reel']['success'] else '❌ Failed'}")
        print(f"{'='*70}\n")
        
        return results
    
    # ==========================================
    # 📊 Data Fetching
    # ==========================================
    
    def _get_instagram_content(self, report_id: int) -> Optional[Dict]:
        """جلب محتوى Instagram من social_media"""
        try:
            url = f"{self.API_BASE_URL}/api/v1/social-media/by-report/{report_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ API error: {response.status_code}")
                return None
            
            data = response.json()
            content_json = data.get('content', '{}')
            social_posts = json.loads(content_json)
            ig_data = social_posts.get('instagram', {})
            
            return {
                'title': ig_data.get('title', ''),
                'content': ig_data.get('content', '')
            }
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def _get_reel_content(self, report_id: int) -> Optional[Dict]:
        """جلب محتوى Reel"""
        
        # Try Method 1: Direct query by report
        print(f"   🔍 Method 1: Querying report {report_id} directly...")
        reel = self._get_reel_from_report(report_id)
        if reel:
            return reel
        
        # Try Method 2: Query generated_content table directly
        print(f"   🔍 Method 2: Querying generated_content...")
        reel = self._get_reel_from_db(report_id)
        if reel:
            return reel
        
        print(f"   ❌ No reel found for report {report_id}")
        return None
    
    def _get_reel_from_report(self, report_id: int) -> Optional[Dict]:
        """جلب reel من report endpoint"""
        try:
            # Query single report
            url = f"{self.API_BASE_URL}/api/v1/reports/{report_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            report = response.json()
            
            # Now get its generated content
            url = f"{self.API_BASE_URL}/api/v1/reports/{report_id}/generated-content"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            content_items = response.json()
            
            # Find reel (content_type_id = 8)
            for item in content_items:
                if item.get('content_type_id') == self.INSTAGRAM_REEL_CONTENT_ID:
                    content_str = item.get('content', '{}')
                    try:
                        content_json = json.loads(content_str) if isinstance(content_str, str) else content_str
                    except:
                        content_json = {}
                    
                    print(f"   ✅ Found reel!")
                    return {
                        'report_id': report_id,
                        'video_url': item.get('file_url'),
                        'title': item.get('title', ''),
                        'description': item.get('description', ''),
                        'content': content_json
                    }
            
            return None
            
        except Exception as e:
            print(f"   ⚠️  Method 1 error: {e}")
            return None
    
    def _get_reel_from_db(self, report_id: int) -> Optional[Dict]:
        """جلب reel من database مباشرة (fallback)"""
        
        if not self.cursor:
            return None
        
        try:
            sql = """
                SELECT id, title, description, content, file_url
                FROM generated_content
                WHERE report_id = %s 
                AND content_type_id = %s
                LIMIT 1
            """
            
            self.cursor.execute(sql, (report_id, self.INSTAGRAM_REEL_CONTENT_ID))
            result = self.cursor.fetchone()
            
            if not result:
                return None
            
            content_str = result[3] or '{}'
            try:
                content_json = json.loads(content_str) if isinstance(content_str, str) else content_str
            except:
                content_json = {}
            
            print(f"   ✅ Found reel in database!")
            return {
                'report_id': report_id,
                'video_url': result[4],
                'title': result[1] or '',
                'description': result[2] or '',
                'content': content_json
            }
            
        except Exception as e:
            print(f"   ⚠️  Method 2 error: {e}")
            return None
    
    def _get_image_url(self, report_id: int) -> Optional[str]:
        """
        جلب URL الصورة
        Priority: Generated → Original
        """
        
        # Try Generated first
        print("   🔍 Trying generated image...")
        url = self._get_generated_image_url(report_id)
        if url:
            return url
        
        # Try Original
        print("   🔍 Trying original image...")
        url = self._get_original_image_url(report_id)
        if url:
            return url
        
        print("❌ No image found")
        return None
    
    def _get_generated_image_url(self, report_id: int) -> Optional[str]:
        """Get Generated Image URL"""
        try:
            url = f"{self.API_BASE_URL}/api/v1/images/by-report/{report_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            image_url = data.get('file_url')
            
            if image_url:
                print("✅ Using Generated Image")
                return image_url
            
            return None
        except:
            return None
    
    def _get_original_image_url(self, report_id: int) -> Optional[str]:
        """Get Original Image URL"""
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
            
            if image_url:
                print("✅ Using Original Image")
                return image_url
            
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
    # 🎨 Text Formatting (Same as Facebook)
    # ==========================================
    
    def _format_caption(self, title: str, content: str) -> str:
        """تنسيق caption لـ Instagram Post مع إصلاح المسافات"""
        
        # إصلاح المسافات في النص
        print(f"   🔧 Original title: {title[:50]}...")
        title = self._fix_text_spacing(title)
        print(f"   ✅ Fixed title: {title[:50]}...")
        
        print(f"   🔧 Original content: {content[:50]}...")
        content = self._fix_text_spacing(content)
        print(f"   ✅ Fixed content: {content[:50]}...")
        
        # فصل المحتوى عن الهاشتاجات
        hashtag_start = content.find('#')
        
        if hashtag_start != -1:
            main_content = content[:hashtag_start].strip()
            hashtags = content[hashtag_start:].strip()
            hashtags = self._format_hashtags(hashtags)
            print(f"   📌 Hashtags found: {hashtags[:50]}...")
        else:
            main_content = content.strip()
            hashtags = ''
            print(f"   ⚠️  No hashtags in content")
            
            # Try to extract from title if it has hashtags
            if '#' in title:
                title_parts = title.split('#', 1)
                title = title_parts[0].strip()
                hashtags = '#' + title_parts[1].strip()
                hashtags = self._format_hashtags(hashtags)
                print(f"   📌 Hashtags from title: {hashtags[:50]}...")
        
        # لو ما في hashtags، نولدهم بـ Gemini
        if not hashtags and self.gemini_model:
            print(f"   🤖 Generating hashtags with Gemini...")
            hashtags = self._generate_hashtags(title + ' ' + main_content)
        
        # تجميع Caption
        result = []
        
        if title:
            result.append(title.strip())
        
        if main_content:
            result.append(main_content)
        
        # إشارة للتفاصيل في التعليق
        result.append("📖 التفاصيل الكاملة في التعليق الأول ⬇️")
        
        if hashtags:
            result.append(hashtags)
        
        caption = '\n\n'.join(result)
        
        # Instagram caption limit
        if len(caption) > self.IG_CAPTION_MAX:
            # Keep hashtags, truncate content
            if hashtags:
                max_content = self.IG_CAPTION_MAX - len(hashtags) - 100
                caption_without_hashtags = '\n\n'.join(result[:-1])
                caption = caption_without_hashtags[:max_content] + "...\n\n" + hashtags
            else:
                caption = caption[:self.IG_CAPTION_MAX - 10] + "..."
        
        print(f"   ✅ Caption ready ({len(caption)} chars)")
        
        return caption
    
    def _fix_text_spacing(self, text: str) -> str:
        """
        إصلاح المسافات في النص العربي باستخدام Gemini
        
        يفصل الكلمات الملتصقة ويضيف مسافات صحيحة
        """
        
        if not text or len(text.strip()) < 10:
            return text
        
        # لو في Gemini، نستخدمه
        if self.gemini_model:
            try:
                fixed = self._fix_spacing_with_gemini(text)
                if fixed and len(fixed) > len(text) * 0.8:  # Sanity check
                    return fixed
            except Exception as e:
                print(f"   ⚠️  Gemini spacing fix failed: {e}")
        
        # Fallback: basic regex fixes
        return self._basic_spacing_fix(text)
    
    def _fix_spacing_with_gemini(self, text: str) -> str:
        """استخدام Gemini لإصلاح المسافات"""
        
        prompt = f"""أنت خبير في تنسيق النصوص العربية.

المهمة: أصلح المسافات في هذا النص. الكلمات ملتصقة ببعضها ومحتاجة مسافات.

القواعد:
1. ضع مسافة بين كل كلمتين
2. ضع مسافة قبل وبعد علامات الترقيم
3. لا تغير أي كلمة أو حرف - فقط أضف مسافات
4. احترم الأرقام والإيموجي - لا تغيرهم
5. أرجع النص المصلح فقط بدون أي شرح أو مقدمات

النص الأصلي:
{text}

النص المصلح (فقط النص، بدون مقدمات):"""
        
        response = self.gemini_model.generate_content(prompt)
        fixed_text = response.text.strip()
        
        # تنظيف أي مقدمات
        unwanted_starts = ['النص المصلح:', 'إليك النص:', 'هنا النص:', 'التصحيح:']
        for prefix in unwanted_starts:
            if fixed_text.startswith(prefix):
                fixed_text = fixed_text[len(prefix):].strip()
                break
        
        # إزالة أي backticks
        fixed_text = fixed_text.replace('```', '').strip()
        
        return fixed_text
    
    def _basic_spacing_fix(self, text: str) -> str:
        """إصلاح بسيط للمسافات (fallback)"""
        
        import re
        
        # إضافة مسافة قبل علامات الترقيم العربية
        text = re.sub(r'([^\s])([؟،؛])', r'\1 \2', text)
        
        # إضافة مسافة بعد علامات الترقيم
        text = re.sub(r'([؟،؛:\.!])([^\s])', r'\1 \2', text)
        
        # إضافة مسافة بين كلمة عربية ورقم
        text = re.sub(r'([\u0600-\u06FF])(\d)', r'\1 \2', text)
        text = re.sub(r'(\d)([\u0600-\u06FF])', r'\1 \2', text)
        
        # إضافة مسافة بين كلمة عربية وحرف إنجليزي
        text = re.sub(r'([\u0600-\u06FF])([a-zA-Z])', r'\1 \2', text)
        text = re.sub(r'([a-zA-Z])([\u0600-\u06FF])', r'\1 \2', text)
        
        # تنظيف المسافات المتعددة
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _generate_hashtags(self, text: str) -> str:
        """
        توليد hashtags مناسبة للمحتوى باستخدام Gemini
        """
        
        try:
            # نأخذ أول 500 حرف من المحتوى للسياق
            context = text[:500] if len(text) > 500 else text
            
            prompt = f"""أنت خبير في السوشيال ميديا والهاشتاجات.

المهمة: ولّد 5-8 هاشتاجات عربية مناسبة لهذا المحتوى.

القواعد:
1. الهاشتاجات يجب أن تكون ذات صلة بالمحتوى
2. استخدم كلمات شائعة ومطلوبة في البحث
3. الهاشتاجات يجب أن تكون قصيرة (كلمة-3 كلمات)
4. افصل الكلمات بـ _ للقراءة
5. أرجع الهاشتاجات فقط (كل واحد في سطر)

المحتوى:
{context}

الهاشتاجات (فقط الهاشتاجات، بدون شرح):"""
            
            response = self.gemini_model.generate_content(prompt)
            hashtags_text = response.text.strip()
            
            # استخراج الهاشتاجات
            hashtags = []
            for line in hashtags_text.split('\n'):
                line = line.strip()
                if line.startswith('#'):
                    hashtags.append(line)
            
            # لو ما رجع hashtags، نستخدم fallback
            if not hashtags:
                return ""
            
            result = ' '.join(hashtags[:8])  # أقصى 8 هاشتاجات
            print(f"   ✅ Generated {len(hashtags)} hashtags")
            
            return result
            
        except Exception as e:
            print(f"   ⚠️  Hashtag generation failed: {e}")
            return ""
    
    def _format_reel_caption(self, reel_content: Dict) -> str:
        """
        تنسيق caption لـ Instagram Reel
        
        يستخدم عنوان ومحتوى Instagram
        """
        
        # Method 1: استخدام Instagram content من social_media
        report_id = reel_content.get('report_id')
        if report_id:
            ig_content = self._get_instagram_content(report_id)
            if ig_content:
                title = ig_content.get('title', '')
                content = ig_content.get('content', '')
                
                # إصلاح المسافات
                title = self._fix_text_spacing(title)
                content = self._fix_text_spacing(content)
                
                # استخراج الهاشتاجات
                hashtag_start = content.find('#')
                if hashtag_start != -1:
                    main_content = content[:hashtag_start].strip()
                    hashtags = content[hashtag_start:].strip()
                    hashtags = self._format_hashtags(hashtags)
                else:
                    main_content = content.strip()
                    hashtags = ''
                
                # لو ما في hashtags، نولدهم
                if not hashtags and self.gemini_model:
                    print(f"   🤖 Generating hashtags for reel...")
                    hashtags = self._generate_hashtags(title + ' ' + main_content)
                
                # تجميع Caption
                result = []
                if title:
                    result.append(title)
                if main_content:
                    # نأخذ أول 200 حرف من المحتوى للـ reel
                    short_content = main_content[:200] + '...' if len(main_content) > 200 else main_content
                    result.append(short_content)
                if hashtags:
                    result.append(hashtags)
                
                caption = '\n\n'.join(result)
                
                # Instagram Reel caption limit
                if len(caption) > self.IG_CAPTION_MAX:
                    caption = caption[:self.IG_CAPTION_MAX - 50] + "..."
                
                return caption
        
        # Method 2: Fallback - استخدام reel_content نفسه
        title = reel_content.get('title', '')
        description = reel_content.get('description', '')
        content = reel_content.get('content', {})
        
        # إصلاح المسافات
        title = self._fix_text_spacing(title)
        description = self._fix_text_spacing(description)
        
        # محاولة استخراج caption و hashtags من content
        if isinstance(content, dict):
            caption_text = content.get('caption', description)
            hashtags_text = content.get('hashtags', '')
        else:
            caption_text = description
            hashtags_text = ''
        
        caption_text = self._fix_text_spacing(caption_text)
        
        # تنسيق الهاشتاجات
        if hashtags_text and self.gemini_model:
            hashtags_text = self._format_hashtags(hashtags_text)
        
        # لو ما في hashtags، نولدهم
        if not hashtags_text and self.gemini_model:
            print(f"   🤖 Generating hashtags for reel...")
            hashtags_text = self._generate_hashtags(title + ' ' + caption_text)
        
        # تجميع
        result = []
        
        if title:
            result.append(title)
        
        if caption_text:
            short_caption = caption_text[:200] + '...' if len(caption_text) > 200 else caption_text
            result.append(short_caption)
        
        if hashtags_text:
            result.append(hashtags_text)
        
        caption = '\n\n'.join(result)
        
        # Instagram Reel caption limit
        if len(caption) > self.IG_CAPTION_MAX:
            caption = caption[:self.IG_CAPTION_MAX - 50] + "..."
        
        return caption
    
    def _format_hashtags(self, text: str) -> str:
        """تنسيق هاشتاجات بـ Gemini (نفس Facebook)"""
        
        print(f"   🔧 Formatting hashtags...")
        
        hashtags = re.findall(r'#[\w\u0600-\u06FF_]+', text)
        
        if not hashtags:
            return text
        
        if self.gemini_model:
            try:
                corrected = self._correct_hashtags_with_gemini(hashtags)
                result = text
                for old, new in zip(hashtags, corrected):
                    if old != new:
                        result = result.replace(old, new, 1)
                        print(f"   ✓ {old} → {new}")
                return result
            except:
                return text
        else:
            return text
    
    def _correct_hashtags_with_gemini(self, hashtags: list) -> list:
        """تصحيح هاشتاجات بـ Gemini"""
        
        hashtags_str = '\n'.join(hashtags)
        
        prompt = f"""أنت خبير في الهاشتاجات العربية.

افصل الكلمات الملتصقة بـ _

مثال:
#قواتحفظالسلام → #قوات_حفظ_السلام
#انتهاكصارخ → #انتهاك_صارخ

الهاشتاجات:
{hashtags_str}

النتيجة (هاشتاج في كل سطر):"""
        
        response = self.gemini_model.generate_content(prompt)
        corrected_text = response.text.strip()
        
        corrected = []
        for line in corrected_text.split('\n'):
            line = line.strip()
            if line and line.startswith('#'):
                corrected.append(line)
        
        if len(corrected) != len(hashtags):
            return hashtags
        
        return corrected
    
    def _prepare_comment(self, full_report: str) -> str:
        """تحضير Comment (نفس Facebook بس مع Instagram limits)"""
        
        header = "📰 التفاصيل الكاملة\n" + "─" * 30 + "\n\n"
        full_text = header + full_report
        
        # Instagram comment limit (2200)
        if len(full_text) > self.IG_COMMENT_MAX:
            # قص ذكي
            max_len = self.IG_COMMENT_MAX - 100
            truncated = full_text[:max_len]
            
            last_period = truncated.rfind('.')
            if last_period > max_len * 0.7:
                full_text = full_text[:last_period + 1]
            else:
                full_text = truncated
            
            full_text += "\n\n📎 للمزيد، تابع موقعنا"
        
        return full_text
    
    # ==========================================
    # 📤 Instagram API
    # ==========================================
    
    def _publish_instagram_post(self, image_url: str, caption: str) -> Dict:
        """نشر Post على Instagram"""
        
        try:
            # Step 1: Create container
            print("   📦 Creating media container...")
            container_id = self._create_image_container(image_url, caption)
            
            if not container_id:
                return {'success': False, 'message': 'Failed to create container'}
            
            # Step 2: Publish
            print("   🚀 Publishing container...")
            media_id = self._publish_container(container_id)
            
            if not media_id:
                return {'success': False, 'message': 'Failed to publish'}
            
            return {'success': True, 'media_id': media_id}
            
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def _publish_instagram_reel(self, video_url: str, caption: str) -> Dict:
        """نشر Reel على Instagram - IMPROVED VERSION"""
        
        try:
            # Step 1: Create container
            print("   📦 Creating reel container...")
            container_id = self._create_reel_container(video_url, caption)
            
            if not container_id:
                return {'success': False, 'message': 'Failed to create reel container'}
            
            print(f"   ✅ Container created: {container_id}")
            
            # Step 2: Wait for processing - CRITICAL STEP
            print("   ⏳ Waiting for video processing...")
            processing_success = self._wait_for_container_ready(container_id)
            
            if not processing_success:
                return {
                    'success': False, 
                    'message': 'Video processing failed or timed out. Container not ready for publishing.'
                }
            
            print("   ✅ Video processing completed successfully!")
            
            # Step 3: Publish ONLY after processing is FINISHED
            print("   🚀 Publishing container...")
            media_id = self._publish_container(container_id)
            
            if not media_id:
                return {'success': False, 'message': 'Failed to publish reel - Media ID not available'}
            
            print(f"   ✅ Reel published successfully! Media ID: {media_id}")
            return {'success': True, 'media_id': media_id}
            
        except Exception as e:
            error_msg = f"Exception during reel publishing: {str(e)}"
            print(f"   ❌ {error_msg}")
            return {'success': False, 'message': error_msg}
    
    def _create_image_container(self, image_url: str, caption: str) -> Optional[str]:
        """Create image container"""
        
        url = f"https://graph.facebook.com/v18.0/{self.IG_USER_ID}/media"
        
        payload = {
            'image_url': image_url,
            'caption': caption,
            'access_token': self.FB_ACCESS_TOKEN
        }
        
        print(f"   📍 Container URL: {url}")
        print(f"   🖼️ Image URL: {image_url[:50]}...")
        
        try:
            response = requests.post(url, data=payload, timeout=30)
            result = response.json()
            
            print(f"   📦 API Response: {result}")
            
            if 'id' in result:
                print(f"   ✅ Container created: {result['id']}")
                return result['id']
            else:
                error = result.get('error', {})
                error_msg = error.get('message', 'Unknown')
                error_code = error.get('code', 'N/A')
                error_type = error.get('type', 'N/A')
                
                print(f"   ❌ Container error:")
                print(f"      Message: {error_msg}")
                print(f"      Code: {error_code}")
                print(f"      Type: {error_type}")
                
                return None
                
        except Exception as e:
            print(f"   ❌ Container exception: {e}")
            return None
    
    def _create_reel_container(self, video_url: str, caption: str) -> Optional[str]:
        """Create reel container - IMPROVED VERSION"""
        
        url = f"https://graph.facebook.com/v18.0/{self.IG_USER_ID}/media"
        
        payload = {
            'media_type': 'REELS',
            'video_url': video_url,
            'caption': caption,
            'share_to_feed': True,
            'access_token': self.FB_ACCESS_TOKEN
        }
        
        print(f"   📍 Container URL: {url}")
        print(f"   🎬 Video URL: {video_url[:50]}...")
        print(f"   📝 Caption: {caption[:100]}...")
        
        try:
            response = requests.post(url, data=payload, timeout=30)
            result = response.json()
            
            print(f"   📦 API Response: {result}")
            
            if 'id' in result:
                container_id = result['id']
                print(f"   ✅ Container created: {container_id}")
                return container_id
            else:
                error = result.get('error', {})
                error_msg = error.get('message', 'Unknown')
                error_code = error.get('code', 'N/A')
                error_type = error.get('type', 'N/A')
                
                print(f"   ❌ Container creation failed:")
                print(f"      Message: {error_msg}")
                print(f"      Code: {error_code}")
                print(f"      Type: {error_type}")
                
                return None
                
        except Exception as e:
            print(f"   ❌ Container creation exception: {e}")
            return None
    
    def _wait_for_container_ready(self, container_id: str, max_wait: int = 120) -> bool:
        """Wait for container processing - FIXED VERSION"""
        
        url = f"https://graph.facebook.com/v18.0/{container_id}"
        params = {
            'fields': 'status_code',
            'access_token': self.FB_ACCESS_TOKEN
        }
        
        start_time = time.time()
        check_count = 0
        
        print(f"   ⏳ Waiting for video processing to complete...")
        print(f"   📍 Container ID: {container_id}")
        
        while time.time() - start_time < max_wait:
            check_count += 1
            
            try:
                response = requests.get(url, params=params, timeout=15)
                result = response.json()
                
                print(f"   📦 API Response: {result}")
                
                status = result.get('status_code')
                
                if status == 'FINISHED':
                    print(f"   ✅ Video processing FINISHED after {check_count} checks ({int(time.time() - start_time)}s)")
                    return True
                elif status == 'ERROR':
                    print(f"   ❌ Processing ERROR detected")
                    error_msg = result.get('error', {}).get('message', 'Unknown processing error')
                    print(f"   ❌ Error details: {error_msg}")
                    return False
                elif status in ['IN_PROGRESS', 'PROCESSING']:
                    elapsed = int(time.time() - start_time)
                    print(f"   ⏳ Status: {status} (check #{check_count}, {elapsed}s elapsed)")
                else:
                    print(f"   ⚠️  Unknown status: {status}")
                
                # Wait longer between checks to avoid rate limiting
                time.sleep(8)
                
            except Exception as e:
                print(f"   ⚠️  Status check error: {e}")
                time.sleep(8)
        
        elapsed = int(time.time() - start_time)
        print(f"   ⏰ TIMEOUT after {elapsed}s - Video processing did not complete")
        print(f"   ❌ Last known status was not FINISHED")
        return False
    
    def _publish_container(self, container_id: str) -> Optional[str]:
        """Publish container - IMPROVED VERSION"""
        
        url = f"https://graph.facebook.com/v18.0/{self.IG_USER_ID}/media_publish"
        
        payload = {
            'creation_id': container_id,
            'access_token': self.FB_ACCESS_TOKEN
        }
        
        print(f"   📍 Publish URL: {url}")
        print(f"   🆔 Container ID: {container_id}")
        
        try:
            response = requests.post(url, data=payload, timeout=30)
            result = response.json()
            
            print(f"   📦 Publish Response: {result}")
            
            if 'id' in result:
                media_id = result['id']
                print(f"   ✅ Successfully published! Media ID: {media_id}")
                return media_id
            else:
                error = result.get('error', {})
                error_msg = error.get('message', 'Unknown')
                error_code = error.get('code', 'N/A')
                error_type = error.get('type', 'N/A')
                
                print(f"   ❌ Publish failed:")
                print(f"      Message: {error_msg}")
                print(f"      Code: {error_code}")
                print(f"      Type: {error_type}")
                
                # Special handling for "Media ID is not available" error
                if 'Media ID is not available' in error_msg or 'not available' in error_msg.lower():
                    print(f"   🔍 This error usually means the video is still processing!")
                    print(f"   💡 The container status should have been FINISHED before publishing")
                
                return None
                
        except Exception as e:
            print(f"   ❌ Publish exception: {e}")
            return None
    
    def _add_comment(self, media_id: str, text: str):
        """Add comment to post"""
        
        url = f"https://graph.facebook.com/v18.0/{media_id}/comments"
        
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
    # 📊 Database Status Updates
    # ==========================================
    
    def _get_current_status(self, report_id: int) -> str:
        """Get current report status"""
        
        if not self.cursor:
            return 'draft'
        
        try:
            sql = "SELECT status FROM generated_report WHERE id = %s"
            self.cursor.execute(sql, (report_id,))
            result = self.cursor.fetchone()
            return result[0] if result else 'draft'
        except:
            return 'draft'
    
    def _calculate_new_status(self, current_status: str, platform: str) -> str:
        """Calculate new status after publishing"""
        
        if current_status == 'facebook_published' and platform == 'instagram':
            return 'facebook_instagram_published'
        elif current_status == 'instagram_published' and platform == 'facebook':
            return 'facebook_instagram_published'
        elif platform == 'instagram':
            return 'instagram_published'
        else:
            return 'published'
    
    def _update_report_status(self, report_id: int, new_status: str):
        """Update report status"""
        
        if not self.conn or not self.cursor:
            print(f"   ⚠️  Database not connected")
            return
        
        try:
            sql = """
                UPDATE generated_report 
                SET status = %s, 
                    updated_at = NOW()
            """
            params = [new_status]
            
            if 'published' in new_status.lower():
                sql += ", published_at = NOW()"
            
            sql += " WHERE id = %s"
            params.append(report_id)
            
            self.cursor.execute(sql, params)
            self.conn.commit()
            
            print(f"   📊 Status: {new_status}")
            
        except Exception as e:
            print(f"   ⚠️  Status update failed: {e}")
            self.conn.rollback()


# ==========================================
# 🧪 Testing
# ==========================================

if __name__ == '__main__':
    import sys
    import os
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except:
        pass
    
    publisher = InstagramPublisher()
    
    if len(sys.argv) > 1:
        report_id = int(sys.argv[1])
        content_type = sys.argv[2] if len(sys.argv) > 2 else 'both'
    else:
        report_id = int(input("Enter report_id: "))
        content_type = input("Type (post/reel/both) [both]: ").strip() or 'both'
    
    result = publisher.publish(report_id, content_type)
    
    print(f"\n{'='*70}")
    print(f"📊 FINAL RESULT:")
    print(f"{'='*70}")
    
    if content_type == 'both':
        print(f"Overall Success: {result['success']}")
        print(f"Post: {'✅' if result['post']['success'] else '❌'} {result['post'].get('media_id', result['post'].get('message'))}")
        print(f"Reel: {'✅' if result['reel']['success'] else '❌'} {result['reel'].get('media_id', result['reel'].get('message'))}")
    else:
        print(f"Success: {result['success']}")
        if result.get('media_id'):
            print(f"Media ID: {result['media_id']}")
            print(f"Type: {result.get('type', 'unknown')}")
        if result.get('message'):
            print(f"Message: {result['message']}")
    
    print(f"{'='*70}\n")