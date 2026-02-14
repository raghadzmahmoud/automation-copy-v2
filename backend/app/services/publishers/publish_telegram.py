#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📱 Telegram Publisher
نشر بسيط على Telegram - عنوان + صورة

Priority:
1. Generated Image
2. Original Image
"""

import os
import requests
from typing import Dict, Optional
import psycopg2


class TelegramPublisher:
    """
    ناشر Telegram
    
    ينشر: عنوان + صورة
    """
    
    def __init__(
        self,
        bot_token: str = None,
        chat_id: str = None,
        api_base_url: str = None
    ):
        """
        Args:
            bot_token: Telegram Bot Token
            chat_id: Telegram Chat/Channel ID
            api_base_url: Base URL للـ API
        """
        
        self.BOT_TOKEN = bot_token or os.getenv('TG_BOT_TOKEN') 
        self.CHAT_ID = chat_id or os.getenv('TG_CHAT_ID') 
        self.API_BASE_URL = (api_base_url or os.getenv('API_BASE_URL') or "http://localhost:8000").rstrip('/')
        
        # Validate required config
        if not self.BOT_TOKEN:
            print("❌ TG_BOT_TOKEN not configured!")
        else:
            print(f"✅ Telegram Bot Token: {self.BOT_TOKEN[:20]}...")
        
        if not self.CHAT_ID:
            print("❌ TG_CHAT_ID not configured!")
        else:
            print(f"✅ Telegram Chat ID: {self.CHAT_ID}")
        
        print(f"✅ API Base URL: {self.API_BASE_URL}")
        
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
    
    def publish(self, report_id: int) -> Dict:
        """
        نشر على Telegram
        
        Args:
            report_id: رقم التقرير
        
        Returns:
            {'success': True/False, 'message_id': '...', 'message': '...'}
        """
        
        print(f"\n{'='*70}")
        print(f"📱 Telegram Publishing - Report #{report_id}")
        print(f"{'='*70}\n")
        
        # Validate configuration
        if not self.BOT_TOKEN:
            return {'success': False, 'message': 'TG_BOT_TOKEN not configured'}
        
        if not self.CHAT_ID:
            return {'success': False, 'message': 'TG_CHAT_ID not configured'}
        
        self._update_report_status(report_id, 'publishing')
        
        # 1. Get Title
        print("1️⃣ Getting report title...")
        title = self._get_report_title(report_id)
        if not title:
            self._update_report_status(report_id, 'failed')
            return {'success': False, 'message': 'Failed to get title'}
        
        print(f"   ✅ Title: {title[:50]}...")
        
        # 2. Get Image URL
        print("\n2️⃣ Getting image...")
        image_url = self._get_image_url(report_id)
        if not image_url:
            self._update_report_status(report_id, 'failed')
            return {'success': False, 'message': 'Failed to get image'}
        
        # 3. Send to Telegram
        print("\n3️⃣ Sending to Telegram...")
        result = self._send_photo(image_url, title)
        
        if not result['success']:
            self._update_report_status(report_id, 'failed')
            return result
        
        print(f"   ✅ Sent! Message ID: {result['message_id']}")
        
        # 4. Update status
        self._update_report_status(report_id, 'telegram_published')
        
        print(f"\n{'='*70}")
        print(f"✅ Telegram Publishing Complete!")
        print(f"{'='*70}\n")
        
        return result
    
    def _get_report_title(self, report_id: int) -> Optional[str]:
        """جلب عنوان التقرير"""
        try:
            url = f"{self.API_BASE_URL}/api/v1/reports/{report_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"   ❌ API error: {response.status_code}")
                return None
            
            data = response.json()
            return data.get('title', '')
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None
    
    def _get_image_url(self, report_id: int) -> Optional[str]:
        """
        جلب URL الصورة
        Priority: Original → Generated
        """
        
        # Try Original first
        print("   🔍 Trying original image...")
        url = self._get_original_image_url(report_id)
        if url:
            return url
        
        # Try Generated
        print("   🔍 Trying generated image...")
        url = self._get_generated_image_url(report_id)
        if url:
            return url
        
        print("   ❌ No image found")
        return None
    
    def _get_generated_image_url(self, report_id: int) -> Optional[str]:
        """Get Generated Image URL"""
        try:
            url = f"{self.API_BASE_URL}/api/v1/images/by-report/{report_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"   ⚠️  Generated image API returned: {response.status_code}")
                return None
            
            data = response.json()
            image_url = data.get('file_url')
            
            if image_url:
                print(f"   ✅ Using Generated Image: {image_url[:50]}...")
                return image_url
            
            return None
        except Exception as e:
            print(f"   ❌ Error getting generated image: {e}")
            return None
    
    def _get_original_image_url(self, report_id: int) -> Optional[str]:
        """Get Original Image URL"""
        try:
            url = f"{self.API_BASE_URL}/api/v1/reports/reports/{report_id}/raw-news-images"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"   ❌ API error: {response.status_code}")
                return None
            
            data = response.json()
            
            # Response format: {"report_id": 123, "images": [{"news_id": 1, "title": "...", "img_url": "..."}]}
            images = data.get('images', [])
            
            if isinstance(images, list) and len(images) > 0:
                # Try different possible keys for image URL
                image_url = images[0].get('img_url') or images[0].get('url') or images[0].get('image_url')
                if image_url:
                    print(f"   ✅ Using Original Image: {image_url[:50]}...")
                    return image_url
            
            print("   ⚠️  No images found in response")
            return None
        except Exception as e:
            print(f"   ❌ Error getting original image: {e}")
            return None
    
    def _send_photo(self, photo_url: str, caption: str) -> Dict:
        """إرسال صورة لـ Telegram"""
        
        url = f"https://api.telegram.org/bot{self.BOT_TOKEN}/sendPhoto"
        
        payload = {
            'chat_id': self.CHAT_ID,
            'photo': photo_url,
            'caption': caption,
            'parse_mode': 'HTML'
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            result = response.json()
            
            if result.get('ok'):
                message_id = result['result']['message_id']
                return {
                    'success': True,
                    'message_id': message_id
                }
            else:
                error = result.get('description', 'Unknown error')
                print(f"   ❌ Telegram error: {error}")
                return {
                    'success': False,
                    'message': f'Telegram error: {error}'
                }
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def _update_report_status(self, report_id: int, new_status: str):
        """Update report status"""
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
        except Exception as e:
            print(f"   ⚠️  Status update failed: {e}")


# ==========================================
# 🧪 Testing
# ==========================================

if __name__ == '__main__':
    import sys
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except:
        pass
    
    publisher = TelegramPublisher()
    
    if len(sys.argv) > 1:
        report_id = int(sys.argv[1])
    else:
        report_id = int(input("Enter report_id: "))
    
    result = publisher.publish(report_id)
    
    print(f"\n{'='*70}")
    print(f"📊 FINAL RESULT:")
    print(f"{'='*70}")
    print(f"Success: {result['success']}")
    if result.get('message_id'):
        print(f"Message ID: {result['message_id']}")
    if result.get('message'):
        print(f"Message: {result['message']}")
    print(f"{'='*70}\n")