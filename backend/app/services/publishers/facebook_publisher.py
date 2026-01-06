#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📘 Facebook Publisher - SMART Multi-Page Version
ينشر على h-GAZA و DOT بصور مختلفة + فيديوهات (Reels)

Features:
- نشر Posts (صورة + caption + hashtags + comment)
- نشر Videos/Reels (فيديو + caption + hashtags)

Priority:
1. Facebook Template (h-GAZA/DOT from content_type_id=9)
2. Original Image
3. Generated Image
"""

import re
import json
import time
import requests
from io import BytesIO
from typing import Dict, Optional
import google.generativeai as genai
import psycopg2


class FacebookPublisher:
    
    # Content Type IDs
    FACEBOOK_POST_CONTENT_ID = 9    # صورة/بوست
    FACEBOOK_REEL_CONTENT_ID = 8    # فيديو/ريل
    
    def __init__(
        self,
        fb_gaza_access_token: str = None,
        fb_gaza_page_id: str = None,
        fb_dot_access_token: str = None,
        fb_dot_page_id: str = None,
        api_base_url: str = None,
        gemini_api_key: str = None
    ):
        import os
        
        # h-GAZA Credentials
        self.FB_GAZA_ACCESS_TOKEN = fb_gaza_access_token or os.getenv('FB_GAZA_ACCESS_TOKEN') or os.getenv('FB_ACCESS_TOKEN')
        self.FB_GAZA_PAGE_ID = fb_gaza_page_id or os.getenv('FB_GAZA_PAGE_ID') or os.getenv('FB_PAGE_ID') 
        
        # DOT Credentials
        self.FB_DOT_ACCESS_TOKEN = fb_dot_access_token or os.getenv('FB_DOT_ACCESS_TOKEN') or self.FB_GAZA_ACCESS_TOKEN
        self.FB_DOT_PAGE_ID = fb_dot_page_id or os.getenv('FB_DOT_PAGE_ID') or ""
        
        self.API_BASE_URL = (api_base_url or os.getenv('API_BASE_URL') or "http://localhost:8000").rstrip('/')
        self.GEMINI_API_KEY = gemini_api_key or os.getenv('GEMINI_API_KEY')
        
        self.FB_COMMENT_MAX = 8000
        
        # Gemini
        if self.GEMINI_API_KEY:
            genai.configure(api_key=self.GEMINI_API_KEY)
            self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
            print("✅ Gemini initialized")
        else:
            self.gemini_model = None
        
        # Database
        try:
            try:
                from settings import DB_CONFIG
                self.conn = psycopg2.connect(**DB_CONFIG)
            except:
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
            print(f"⚠️  Database error: {e}")
            self.conn = None
            self.cursor = None
    
    def publish(self, report_id: int, content_type: str = 'both') -> Dict:
        """
        نشر ذكي على h-GAZA و DOT
        
        Args:
            report_id: رقم التقرير
            content_type: 'post' | 'video' | 'both'
        """
        
        if content_type == 'both':
            return self.publish_both(report_id)
        elif content_type == 'video':
            return self.publish_video(report_id)
        else:
            return self.publish_post(report_id)
    
    def publish_post(self, report_id: int) -> Dict:
        """نشر Post (صورة) على h-GAZA و DOT"""
        
        print(f"\n{'='*70}")
        print(f"📘 Facebook POST Publishing - Report #{report_id}")
        print(f"{'='*70}\n")
        
        self._update_report_status(report_id, 'publishing')
        
        # 1. Get templates
        print("1️⃣ Getting Facebook templates...")
        templates = self._get_facebook_templates(report_id)
        print(f"   📦 Templates: {list(templates.keys()) if templates else 'None'}")
        
        # 2. Get content
        print("\n2️⃣ Getting Facebook content...")
        fb_content = self._get_facebook_content(report_id)
        if not fb_content:
            self._update_report_status(report_id, 'failed')
            return {'success': False, 'message': 'Failed to get content'}
        
        # 3. Format caption
        print("3️⃣ Formatting caption...")
        caption = self._format_caption(fb_content['title'], fb_content['content'])
        
        # 4. Get full report
        print("4️⃣ Getting full report...")
        full_report = self._get_full_report(report_id)
        comment_text = self._prepare_comment(full_report) if full_report else None
        
        # 5. Publish to pages
        results = []
        
        # h-GAZA
        if templates.get('h-GAZA') or True:  # Always try h-GAZA
            print(f"\n{'─'*70}")
            print(f"📤 Publishing to h-GAZA...")
            print(f"{'─'*70}")
            
            image = self._get_image_for_page(report_id, 'h-GAZA', templates.get('h-GAZA'))
            if image:
                result = self._publish_to_page(
                    self.FB_GAZA_PAGE_ID,
                    self.FB_GAZA_ACCESS_TOKEN,
                    'h-GAZA',
                    caption,
                    image,
                    comment_text
                )
                if result['success']:
                    results.append(result)
            else:
                print("   ❌ No image for h-GAZA")
        
        # DOT
        if self.FB_DOT_PAGE_ID and (templates.get('DOT') or True):
            print(f"\n{'─'*70}")
            print(f"📤 Publishing to DOT...")
            print(f"{'─'*70}")
            
            image = self._get_image_for_page(report_id, 'DOT', templates.get('DOT'))
            if image:
                result = self._publish_to_page(
                    self.FB_DOT_PAGE_ID,
                    self.FB_DOT_ACCESS_TOKEN,
                    'DOT',
                    caption,
                    image,
                    comment_text
                )
                if result['success']:
                    results.append(result)
            else:
                print("   ❌ No image for DOT")
        
        # Final status
        if results:
            self._update_report_status(report_id, 'facebook_published')
            
            print(f"\n{'='*70}")
            print(f"✅ POST Publishing Complete!")
            print(f"{'='*70}")
            for r in results:
                print(f"   {r['page']}: {r['post_id']}")
            print(f"{'='*70}\n")
            
            return {'success': True, 'posts': results, 'type': 'post'}
        else:
            self._update_report_status(report_id, 'failed')
            return {'success': False, 'message': 'All pages failed'}
    
    def publish_video(self, report_id: int) -> Dict:
        """نشر Video/Reel على h-GAZA و DOT"""
        
        print(f"\n{'='*70}")
        print(f"🎬 Facebook VIDEO Publishing - Report #{report_id}")
        print(f"{'='*70}\n")
        
        self._update_report_status(report_id, 'publishing')
        
        # 1. Get reel content
        print("1️⃣ Getting reel content...")
        reel_content = self._get_reel_content(report_id)
        if not reel_content:
            self._update_report_status(report_id, 'failed')
            return {'success': False, 'message': 'Failed to get reel content'}
        
        # 2. Get video URL
        video_url = reel_content.get('video_url')
        if not video_url:
            self._update_report_status(report_id, 'failed')
            return {'success': False, 'message': 'No video URL found'}
        
        print(f"   ✅ Video URL: {video_url[:50]}...")
        
        # 3. Get Facebook content for caption
        print("\n2️⃣ Getting Facebook content...")
        fb_content = self._get_facebook_content(report_id)
        if not fb_content:
            self._update_report_status(report_id, 'failed')
            return {'success': False, 'message': 'Failed to get content'}
        
        # 4. Format caption
        print("3️⃣ Formatting caption...")
        caption = self._format_video_caption(fb_content['title'], fb_content['content'])
        
        # 5. Publish to pages
        results = []
        
        # h-GAZA
        print(f"\n{'─'*70}")
        print(f"📤 Publishing video to h-GAZA...")
        print(f"{'─'*70}")
        
        result = self._publish_video_to_page(
            self.FB_GAZA_PAGE_ID,
            self.FB_GAZA_ACCESS_TOKEN,
            'h-GAZA',
            caption,
            video_url
        )
        if result['success']:
            results.append(result)
        
        # DOT
        if self.FB_DOT_PAGE_ID:
            print(f"\n{'─'*70}")
            print(f"📤 Publishing video to DOT...")
            print(f"{'─'*70}")
            
            # Add delay before DOT to avoid rate limiting
            if results:  # إذا نشرنا على h-GAZA بالفعل
                delay_seconds = 5
                print(f"   ⏳ Waiting {delay_seconds} seconds (rate limit protection)...")
                time.sleep(delay_seconds)
            
            result = self._publish_video_to_page(
                self.FB_DOT_PAGE_ID,
                self.FB_DOT_ACCESS_TOKEN,
                'DOT',
                caption,
                video_url
            )
            if result['success']:
                results.append(result)
        
        # Final status
        if results:
            self._update_report_status(report_id, 'facebook_published')
            
            print(f"\n{'='*70}")
            print(f"✅ VIDEO Publishing Complete!")
            print(f"{'='*70}")
            for r in results:
                print(f"   {r['page']}: {r['video_id']}")
            print(f"{'='*70}\n")
            
            return {'success': True, 'videos': results, 'type': 'video'}
        else:
            self._update_report_status(report_id, 'failed')
            return {'success': False, 'message': 'All pages failed'}
    
    def publish_both(self, report_id: int) -> Dict:
        """نشر Post + Video سوا"""
        
        print(f"\n{'='*70}")
        print(f"📘🎬 Facebook Post + Video Publishing - Report #{report_id}")
        print(f"{'='*70}\n")
        
        results = {
            'post': None,
            'video': None,
            'success': False
        }
        
        # 1. Publish Post
        print("🔹 Publishing Post...")
        post_result = self.publish_post(report_id)
        results['post'] = post_result
        
        if not post_result['success']:
            print(f"❌ Post failed: {post_result.get('message')}")
        else:
            print(f"✅ Post published\n")
        
        # Longer delay between post and video to avoid rate limiting
        delay_seconds = 10  # زيادة من 3 إلى 10 ثواني
        print(f"⏳ Waiting {delay_seconds} seconds before video upload (rate limit protection)...")
        time.sleep(delay_seconds)
        
        # 2. Publish Video
        print("🔹 Publishing Video...")
        video_result = self.publish_video(report_id)
        results['video'] = video_result
        
        if not video_result['success']:
            print(f"❌ Video failed: {video_result.get('message')}")
        else:
            print(f"✅ Video published\n")
        
        # 3. Overall success
        results['success'] = post_result['success'] or video_result['success']
        
        # 4. Summary
        print(f"\n{'='*70}")
        print(f"📊 BOTH RESULTS:")
        print(f"{'='*70}")
        print(f"Post: {'✅ Published' if post_result['success'] else '❌ Failed'}")
        print(f"Video: {'✅ Published' if video_result['success'] else '❌ Failed'}")
        print(f"{'='*70}\n")
        
        return results
    
    def _get_facebook_templates(self, report_id: int) -> Dict[str, str]:
        """Get templates from content_type_id=9"""
        try:
            if not self.cursor:
                return {}
            
            sql = "SELECT content FROM generated_content WHERE report_id=%s AND content_type_id=9 LIMIT 1"
            self.cursor.execute(sql, (report_id,))
            result = self.cursor.fetchone()
            
            if not result or not result[0]:
                return {}
            
            content_json = json.loads(result[0]) if isinstance(result[0], str) else result[0]
            
            templates = {}
            if 'h-GAZA' in content_json and content_json['h-GAZA']:
                templates['h-GAZA'] = content_json['h-GAZA']
            if 'DOT' in content_json and content_json['DOT']:
                templates['DOT'] = content_json['DOT']
            
            return templates
        except:
            return {}
    
    def _get_image_for_page(self, report_id: int, page_key: str, template_url: str = None) -> Optional[BytesIO]:
        """
        Get image for specific page
        Priority: Template → Original → Generated
        """
        
        # 1. Template
        if template_url:
            print(f"   🎯 Using {page_key} template")
            try:
                response = requests.get(template_url, timeout=15)
                if response.status_code == 200:
                    print(f"   ✅ Template image loaded")
                    return BytesIO(response.content)
            except:
                pass
        
        # 2. Original
        print(f"   🔍 Trying original image...")
        img = self._get_original_image(report_id)
        if img:
            return img
        
        # 3. Generated
        print(f"   🔍 Trying generated image...")
        img = self._get_generated_image(report_id)
        if img:
            return img
        
        return None
    
    def _get_original_image(self, report_id: int) -> Optional[BytesIO]:
        """Get original image"""
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
                img_response = requests.get(image_url, timeout=15)
                if img_response.status_code == 200:
                    print("   ✅ Using Original Image")
                    return BytesIO(img_response.content)
        except:
            pass
        return None
    
    def _get_generated_image(self, report_id: int) -> Optional[BytesIO]:
        """Get generated image"""
        try:
            url = f"{self.API_BASE_URL}/api/v1/images/by-report/{report_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            image_url = data.get('file_url')
            
            if image_url:
                img_response = requests.get(image_url, timeout=15)
                if img_response.status_code == 200:
                    print("   ✅ Using Generated Image")
                    return BytesIO(img_response.content)
        except:
            pass
        return None
    
    def _publish_to_page(self, page_id: str, access_token: str, page_name: str, 
                         caption: str, image: BytesIO, comment_text: str = None) -> Dict:
        """Publish photo to single page"""
        
        url = f"https://graph.facebook.com/v18.0/{page_id}/photos"
        
        payload = {
            'message': caption,
            'access_token': access_token
        }
        
        files = {'source': ('news.jpg', image, 'image/jpeg')}
        
        try:
            response = requests.post(url, data=payload, files=files, timeout=30)
            result = response.json()
            
            if 'id' in result:
                post_id = result['id']
                print(f"   ✅ Published: {post_id}")
                
                if comment_text:
                    self._add_comment(post_id, comment_text, access_token)
                
                return {'success': True, 'page': page_name, 'post_id': post_id}
            else:
                error = result.get('error', {}).get('message', 'Unknown')
                print(f"   ❌ Error: {error}")
                return {'success': False, 'message': error}
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            return {'success': False, 'message': str(e)}
    
    def _publish_video_to_page(self, page_id: str, access_token: str, page_name: str,
                               caption: str, video_url: str, retry_count: int = 0) -> Dict:
        """
        Publish video to single Facebook page
        
        Uses direct file_url upload (simpler method)
        Includes retry logic for rate limiting
        """
        
        print(f"   📹 Starting video upload for {page_name}...")
        
        try:
            # Direct upload using file_url
            # Facebook will fetch the video from the URL
            url = f"https://graph.facebook.com/v18.0/{page_id}/videos"
            payload = {
                'file_url': video_url,
                'description': caption,
                'access_token': access_token
            }
            
            print(f"   🔄 Uploading video from URL...")
            print(f"   📎 Video URL: {video_url[:80]}...")
            
            response = requests.post(url, data=payload, timeout=120)
            result = response.json()
            
            if 'id' in result:
                video_id = result['id']
                print(f"   ✅ Video published: {video_id}")
                return {'success': True, 'page': page_name, 'video_id': video_id}
            
            else:
                error = result.get('error', {})
                error_message = error.get('message', 'Unknown error')
                error_code = error.get('code', 'N/A')
                
                # Check if it's a rate limit error (code 368)
                if error_code == 368 and retry_count < 2:
                    retry_delay = 30 * (retry_count + 1)  # 30s, 60s
                    print(f"   ⚠️  Rate limit hit. Retrying in {retry_delay} seconds... (attempt {retry_count + 1}/2)")
                    time.sleep(retry_delay)
                    return self._publish_video_to_page(page_id, access_token, page_name, caption, video_url, retry_count + 1)
                
                print(f"   ❌ Upload error ({error_code}): {error_message}")
                return {'success': False, 'message': f"({error_code}) {error_message}"}
                
        except requests.exceptions.Timeout:
            print(f"   ❌ Timeout: Video upload took too long")
            return {'success': False, 'message': 'Upload timeout - video may be too large'}
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            return {'success': False, 'message': str(e)}
    
    def _get_facebook_content(self, report_id: int) -> Optional[Dict]:
        """Get Facebook content"""
        try:
            url = f"{self.API_BASE_URL}/api/v1/social-media/by-report/{report_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            content_json = data.get('content', '{}')
            social_posts = json.loads(content_json)
            fb_data = social_posts.get('facebook', {})
            
            return {'title': fb_data.get('title', ''), 'content': fb_data.get('content', '')}
        except:
            return None
    
    def _get_reel_content(self, report_id: int) -> Optional[Dict]:
        """جلب محتوى Reel/Video"""
        
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
                if item.get('content_type_id') == self.FACEBOOK_REEL_CONTENT_ID:
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
            
            self.cursor.execute(sql, (report_id, self.FACEBOOK_REEL_CONTENT_ID))
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
    
    def _format_caption(self, title: str, content: str) -> str:
        """Format caption for photo post"""
        hashtag_start = content.find('#')
        
        if hashtag_start != -1:
            main_content = content[:hashtag_start].strip()
            hashtags = content[hashtag_start:].strip()
            hashtags = self._format_hashtags(hashtags)
        else:
            main_content = content.strip()
            hashtags = ''
        
        result = []
        if title:
            result.append(title.strip())
        if main_content:
            result.append(main_content)
        result.append("📖 التفاصيل الكاملة في التعليق الأول ⬇️")
        if hashtags:
            result.append(hashtags)
        
        return '\n\n'.join(result)
    
    def _format_video_caption(self, title: str, content: str) -> str:
        """Format caption for video post"""
        hashtag_start = content.find('#')
        
        if hashtag_start != -1:
            main_content = content[:hashtag_start].strip()
            hashtags = content[hashtag_start:].strip()
            hashtags = self._format_hashtags(hashtags)
        else:
            main_content = content.strip()
            hashtags = ''
        
        result = []
        if title:
            result.append(title.strip())
        if main_content:
            # For videos, keep content shorter
            short_content = main_content[:300] + '...' if len(main_content) > 300 else main_content
            result.append(short_content)
        if hashtags:
            result.append(hashtags)
        
        return '\n\n'.join(result)
    
    def _format_hashtags(self, text: str) -> str:
        """Format hashtags with Gemini"""
        hashtags = re.findall(r'#[\w\u0600-\u06FF_]+', text)
        
        if not hashtags or not self.gemini_model:
            return text
        
        try:
            corrected = self._correct_hashtags_with_gemini(hashtags)
            result = text
            for old, new in zip(hashtags, corrected):
                if old != new:
                    result = result.replace(old, new, 1)
            return result
        except:
            return text
    
    def _correct_hashtags_with_gemini(self, hashtags: list) -> list:
        """Correct hashtags with Gemini"""
        hashtags_str = '\n'.join(hashtags)
        
        prompt = f"""افصل الكلمات الملتصقة بـ _

مثال:
#قواتحفظالسلام → #قوات_حفظ_السلام

الهاشتاجات:
{hashtags_str}

النتيجة:"""
        
        response = self.gemini_model.generate_content(prompt)
        corrected_text = response.text.strip()
        
        corrected = [line.strip() for line in corrected_text.split('\n') if line.strip().startswith('#')]
        
        return corrected if len(corrected) == len(hashtags) else hashtags
    
    def _get_full_report(self, report_id: int) -> Optional[str]:
        """Get full report"""
        try:
            url = f"{self.API_BASE_URL}/api/v1/reports/{report_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            title = data.get('title', '')
            content = data.get('content', '') or data.get('body', '')
            
            return f"{title}\n\n{content}" if title and content else (content or title)
        except:
            return None
    
    def _prepare_comment(self, full_report: str) -> str:
        """Prepare comment"""
        header = "📰 التفاصيل الكاملة للخبر\n" + "─" * 40 + "\n\n"
        full_text = header + full_report
        
        if len(full_text) > self.FB_COMMENT_MAX:
            max_len = self.FB_COMMENT_MAX - 100
            truncated = full_text[:max_len]
            last_period = truncated.rfind('.')
            if last_period > max_len * 0.7:
                full_text = full_text[:last_period + 1]
            full_text += "\n\n📎 للمزيد، تابع موقعنا"
        
        return full_text
    
    def _add_comment(self, post_id: str, text: str, access_token: str):
        """Add comment"""
        url = f"https://graph.facebook.com/v18.0/{post_id}/comments"
        payload = {'message': text, 'access_token': access_token}
        
        try:
            response = requests.post(url, data=payload, timeout=15)
            result = response.json()
            
            if 'id' in result:
                print(f"   ✅ Comment added")
            else:
                print(f"   ⚠️  Comment failed")
        except:
            pass
    
    def _update_report_status(self, report_id: int, new_status: str):
        """Update status"""
        if not self.conn or not self.cursor:
            return
        
        try:
            sql = "UPDATE generated_report SET status=%s, updated_at=NOW()"
            params = [new_status]
            
            if 'published' in new_status.lower():
                sql += ", published_at=NOW()"
            
            sql += " WHERE id=%s"
            params.append(report_id)
            
            self.cursor.execute(sql, params)
            self.conn.commit()
            print(f"   📊 Status: {new_status}")
        except:
            pass


if __name__ == '__main__':
    import sys, os
    
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
    if result.get('posts'):
        for p in result['posts']:
            print(f"{p['page']}: {p['post_id']}")
    print(f"{'='*70}\n")