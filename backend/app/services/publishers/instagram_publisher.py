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
        
        self.IG_USER_ID = ig_user_id or os.getenv('IG_USER_ID')
        self.FB_ACCESS_TOKEN = fb_access_token or os.getenv('FB_ACCESS_TOKEN')
        self.API_BASE_URL = (api_base_url or os.getenv('API_BASE_URL') or "http://localhost:8000").rstrip('/')
        self.GEMINI_API_KEY = gemini_api_key or os.getenv('GEMINI_API_KEY')
        
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
            from settings import DB_CONFIG
            self.conn = psycopg2.connect(**DB_CONFIG)
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
            'post': None,
            'reel': None,
            'success': False
        }
        
        # 1. Publish Post
        print("🔹 Publishing Post...")
        post_result = self.publish_post(report_id)
        results['post'] = post_result
        
        if not post_result['success']:
            print(f"❌ Post failed: {post_result.get('message')}")
        else:
            print(f"✅ Post published: {post_result['media_id']}\n")
        
        # 2. Publish Reel
        print("🔹 Publishing Reel...")
        reel_result = self.publish_reel(report_id)
        results['reel'] = reel_result
        
        if not reel_result['success']:
            print(f"❌ Reel failed: {reel_result.get('message')}")
        else:
            print(f"✅ Reel published: {reel_result['media_id']}\n")
        
        # 3. Overall success
        results['success'] = post_result['success'] or reel_result['success']
        
        # 4. Summary
        print(f"\n{'='*70}")
        print(f"📊 BOTH RESULTS:")
        print(f"{'='*70}")
        print(f"Post: {'✅ ' + post_result.get('media_id', 'N/A') if post_result['success'] else '❌ Failed'}")
        print(f"Reel: {'✅ ' + reel_result.get('media_id', 'N/A') if reel_result['success'] else '❌ Failed'}")
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
        """جلب محتوى Reel من generated_content"""
        try:
            # Get from generated_content where content_type_id = 8
            url = f"{self.API_BASE_URL}/api/v1/generated-content"
            params = {
                'report_id': report_id,
                'content_type_id': self.INSTAGRAM_REEL_CONTENT_ID
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ API error: {response.status_code}")
                return None
            
            data = response.json()
            
            # Assuming API returns list or single object
            if isinstance(data, list) and len(data) > 0:
                item = data[0]
            elif isinstance(data, dict):
                item = data
            else:
                return None
            
            # Parse content JSON if needed
            content_str = item.get('content', '{}')
            try:
                content_json = json.loads(content_str) if isinstance(content_str, str) else content_str
            except:
                content_json = {}
            
            return {
                'video_url': item.get('file_url'),
                'title': item.get('title', ''),
                'description': item.get('description', ''),
                'content': content_json
            }
            
        except Exception as e:
            print(f"❌ Error getting reel: {e}")
            return None
    
    def _get_image_url(self, report_id: int) -> Optional[str]:
        """جلب URL الصورة (Generated → Original)"""
        
        # Try Generated
        url = self._get_generated_image_url(report_id)
        if url:
            return url
        
        # Try Original
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
        """تنسيق caption لـ Instagram Post"""
        
        # فصل المحتوى عن الهاشتاجات
        hashtag_start = content.find('#')
        
        if hashtag_start != -1:
            main_content = content[:hashtag_start].strip()
            hashtags = content[hashtag_start:].strip()
            hashtags = self._format_hashtags(hashtags)
            print(f"   📌 Hashtags: {hashtags[:50]}...")
        else:
            main_content = content.strip()
            hashtags = ''
            print(f"   ⚠️  No hashtags found")
        
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
            caption = caption[:self.IG_CAPTION_MAX - 50] + "...\n\n" + hashtags
        
        return caption
    
    def _format_reel_caption(self, reel_content: Dict) -> str:
        """تنسيق caption لـ Instagram Reel"""
        
        title = reel_content.get('title', '')
        description = reel_content.get('description', '')
        content = reel_content.get('content', {})
        
        # محاولة استخراج caption و hashtags من content
        if isinstance(content, dict):
            caption_text = content.get('caption', description)
            hashtags_text = content.get('hashtags', '')
        else:
            caption_text = description
            hashtags_text = ''
        
        # تنسيق الهاشتاجات
        if hashtags_text and self.gemini_model:
            hashtags_text = self._format_hashtags(hashtags_text)
        
        # تجميع
        result = []
        
        if title:
            result.append(title)
        
        if caption_text:
            result.append(caption_text)
        
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
        """نشر Reel على Instagram"""
        
        try:
            # Step 1: Create container
            print("   📦 Creating reel container...")
            container_id = self._create_reel_container(video_url, caption)
            
            if not container_id:
                return {'success': False, 'message': 'Failed to create container'}
            
            # Step 2: Wait for processing
            print("   ⏳ Waiting for video processing...")
            if not self._wait_for_container_ready(container_id):
                return {'success': False, 'message': 'Video processing timeout'}
            
            # Step 3: Publish
            print("   🚀 Publishing reel...")
            media_id = self._publish_container(container_id)
            
            if not media_id:
                return {'success': False, 'message': 'Failed to publish'}
            
            return {'success': True, 'media_id': media_id}
            
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def _create_image_container(self, image_url: str, caption: str) -> Optional[str]:
        """Create image container"""
        
        url = f"https://graph.facebook.com/v18.0/{self.IG_USER_ID}/media"
        
        payload = {
            'image_url': image_url,
            'caption': caption,
            'access_token': self.FB_ACCESS_TOKEN
        }
        
        try:
            response = requests.post(url, data=payload, timeout=30)
            result = response.json()
            
            if 'id' in result:
                return result['id']
            else:
                error = result.get('error', {}).get('message', 'Unknown')
                print(f"   ❌ Container error: {error}")
                return None
                
        except Exception as e:
            print(f"   ❌ Container error: {e}")
            return None
    
    def _create_reel_container(self, video_url: str, caption: str) -> Optional[str]:
        """Create reel container"""
        
        url = f"https://graph.facebook.com/v18.0/{self.IG_USER_ID}/media"
        
        payload = {
            'media_type': 'REELS',
            'video_url': video_url,
            'caption': caption,
            'share_to_feed': True,
            'access_token': self.FB_ACCESS_TOKEN
        }
        
        try:
            response = requests.post(url, data=payload, timeout=30)
            result = response.json()
            
            if 'id' in result:
                return result['id']
            else:
                error = result.get('error', {}).get('message', 'Unknown')
                print(f"   ❌ Container error: {error}")
                return None
                
        except Exception as e:
            print(f"   ❌ Container error: {e}")
            return None
    
    def _wait_for_container_ready(self, container_id: str, max_wait: int = 60) -> bool:
        """Wait for container processing"""
        
        url = f"https://graph.facebook.com/v18.0/{container_id}"
        params = {
            'fields': 'status_code',
            'access_token': self.FB_ACCESS_TOKEN
        }
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                response = requests.get(url, params=params, timeout=10)
                result = response.json()
                
                status = result.get('status_code')
                
                if status == 'FINISHED':
                    return True
                elif status == 'ERROR':
                    print(f"   ❌ Processing error")
                    return False
                
                print(f"   ⏳ Status: {status}")
                time.sleep(5)
                
            except Exception as e:
                print(f"   ⚠️  Status check error: {e}")
                time.sleep(5)
        
        print(f"   ⏰ Timeout")
        return False
    
    def _publish_container(self, container_id: str) -> Optional[str]:
        """Publish container"""
        
        url = f"https://graph.facebook.com/v18.0/{self.IG_USER_ID}/media_publish"
        
        payload = {
            'creation_id': container_id,
            'access_token': self.FB_ACCESS_TOKEN
        }
        
        try:
            response = requests.post(url, data=payload, timeout=30)
            result = response.json()
            
            if 'id' in result:
                return result['id']
            else:
                error = result.get('error', {}).get('message', 'Unknown')
                print(f"   ❌ Publish error: {error}")
                return None
                
        except Exception as e:
            print(f"   ❌ Publish error: {e}")
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