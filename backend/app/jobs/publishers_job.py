#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📤 Publishers Job - Multi-Platform Publishing
═══════════════════════════════════════════════════════════════
ينشر التقارير على جميع منصات السوشال ميديا:
- Facebook (h-GAZA + DOT) - Posts + Videos/Reels
- Instagram (Posts + Reels) - ACTIVE
- Telegram

يعمل بشكل دوري ويبحث عن التقارير الجاهزة للنشر

Publishing Limits:
- Social Media (FB + IG): 1 تقرير/دورة (بوست + ريل لكل منصة)
- Telegram: 3 تقارير/دورة
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import logging
import psycopg2
import json
import traceback
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from settings import DB_CONFIG
from app.services.publishers.facebook_publisher import FacebookPublisher
from app.services.publishers.instagram_publisher import InstagramPublisher
from app.services.publishers.publish_telegram import TelegramPublisher

logger = logging.getLogger(__name__)

# ============================================
# Publishing Pause Management
# ============================================

PAUSE_FILE = os.path.join(os.path.dirname(__file__), '.publishing_pause.json')

def set_publishing_pause(platform: str, hours: int = 12):
    """
    إيقاف النشر على منصة معينة لمدة محددة
    
    Args:
        platform: 'facebook', 'instagram', or 'all'
        hours: عدد الساعات للإيقاف
    """
    pause_until = datetime.now() + timedelta(hours=hours)
    
    # Load existing pauses
    pauses = {}
    if os.path.exists(PAUSE_FILE):
        try:
            with open(PAUSE_FILE, 'r') as f:
                pauses = json.load(f)
        except:
            pauses = {}
    
    # Set pause
    if platform == 'all':
        pauses['facebook'] = pause_until.isoformat()
        pauses['instagram'] = pause_until.isoformat()
    else:
        pauses[platform] = pause_until.isoformat()
    
    # Save
    with open(PAUSE_FILE, 'w') as f:
        json.dump(pauses, f, indent=2)
    
    logger.info(f"⏸️  Publishing paused for {platform} until {pause_until}")

def is_publishing_paused(platform: str) -> bool:
    """
    التحقق من إيقاف النشر على منصة معينة
    
    Args:
        platform: 'facebook' or 'instagram'
    
    Returns:
        True if paused, False otherwise
    """
    if not os.path.exists(PAUSE_FILE):
        return False
    
    try:
        with open(PAUSE_FILE, 'r') as f:
            pauses = json.load(f)
        
        if platform not in pauses:
            return False
        
        pause_until = datetime.fromisoformat(pauses[platform])
        
        if datetime.now() < pause_until:
            remaining = pause_until - datetime.now()
            hours = remaining.total_seconds() / 3600
            logger.info(f"⏸️  {platform.title()} publishing paused for {hours:.1f} more hours")
            return True
        else:
            # Pause expired, remove it
            del pauses[platform]
            with open(PAUSE_FILE, 'w') as f:
                json.dump(pauses, f, indent=2)
            logger.info(f"▶️  {platform.title()} publishing pause expired, resuming")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error checking pause status: {e}")
        return False

def clear_publishing_pause(platform: str = 'all'):
    """
    إلغاء إيقاف النشر
    
    Args:
        platform: 'facebook', 'instagram', or 'all'
    """
    if not os.path.exists(PAUSE_FILE):
        return
    
    try:
        with open(PAUSE_FILE, 'r') as f:
            pauses = json.load(f)
        
        if platform == 'all':
            pauses = {}
        elif platform in pauses:
            del pauses[platform]
        
        with open(PAUSE_FILE, 'w') as f:
            json.dump(pauses, f, indent=2)
        
        logger.info(f"▶️  Publishing pause cleared for {platform}")
        
    except Exception as e:
        logger.error(f"❌ Error clearing pause: {e}")


class PublishersJob:
    """
    مدير النشر على جميع المنصات
    
    يبحث عن التقارير الجاهزة للنشر ويوزعها على المنصات المختلفة
    """
    
    def __init__(self):
        """Initialize publishers and database connection"""
        
        # Database connection
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            logger.info("✅ Database connected")
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            self.conn = None
            self.cursor = None
        
        # Initialize publishers
        self.publishers = {}
        
        # Facebook Publisher
        try:
            self.publishers['facebook'] = FacebookPublisher()
            logger.info("✅ Facebook Publisher initialized")
        except Exception as e:
            logger.error(f"❌ Facebook Publisher failed: {e}")
            self.publishers['facebook'] = None
        
        # Instagram Publisher
        try:
            self.publishers['instagram'] = InstagramPublisher()
            logger.info("✅ Instagram Publisher initialized")
        except Exception as e:
            logger.error(f"❌ Instagram Publisher failed: {e}")
            self.publishers['instagram'] = None
        
        # Telegram Publisher
        try:
            self.publishers['telegram'] = TelegramPublisher()
            logger.info("✅ Telegram Publisher initialized")
        except Exception as e:
            logger.error(f"❌ Telegram Publisher failed: {e}")
            self.publishers['telegram'] = None
        
        # Publishing settings
        self.max_concurrent_publishes = 2  # عدد التقارير التي تنشر بنفس الوقت
        
        # عدد التقارير لكل منصة في كل دورة
        self.max_reports_per_run = int(os.getenv('MAX_REPORTS_PER_PUBLISH', 10))  # للتيليجرام
        self.max_social_media_reports = int(os.getenv('MAX_SOCIAL_MEDIA_REPORTS', 1))  # للفيسبوك/انستغرام
        
        logger.info(f"📊 Publishing limits:")
        logger.info(f"   Telegram: {self.max_reports_per_run} reports/cycle")
        logger.info(f"   Social Media (FB/IG): {self.max_social_media_reports} reports/cycle")
    
    def get_reports_ready_for_publishing(self, platform: str = 'all', limit: int = None) -> List[Tuple[int, str, datetime]]:
        """
        جلب التقارير الجاهزة للنشر
        
        Args:
            platform: 'all', 'social_media', or 'telegram'
            limit: عدد التقارير (None = استخدام الحد الافتراضي)
        
        Returns:
            List of (report_id, current_status, created_at) tuples
        """
        
        if not self.cursor:
            return []
        
        # تحديد الحد الأقصى حسب المنصة
        if limit is None:
            if platform == 'social_media':
                limit = self.max_social_media_reports
            elif platform == 'telegram':
                limit = self.max_reports_per_run
            else:
                limit = max(self.max_reports_per_run, self.max_social_media_reports)
        
        try:
            # البحث عن التقارير التي لها محتوى سوشال ميديا
            # نبسط الاستعلام - الـ publishers سيتحققون من وجود الصور بأنفسهم
            
            if platform == 'social_media':
                # للفيسبوك/انستغرام: تقارير لم تنشر على social media بعد
                sql = """
                    SELECT gr.id, gr.status, gr.created_at
                    FROM generated_report gr
                    WHERE gr.status IN (
                        'ready_for_publishing',
                        'completed',
                        'telegram_published'
                    )
                    AND gr.status NOT LIKE '%%facebook%%'
                    AND gr.status NOT LIKE '%%instagram%%'
                    ORDER BY gr.created_at DESC
                    LIMIT %s
                """
            elif platform == 'facebook':
                # للفيسبوك فقط: تقارير لم تنشر على facebook بعد
                sql = """
                    SELECT gr.id, gr.status, gr.created_at
                    FROM generated_report gr
                    WHERE gr.status IN (
                        'ready_for_publishing',
                        'completed',
                        'telegram_published',
                        'instagram_published'
                    )
                    AND gr.status NOT LIKE '%%facebook%%'
                    ORDER BY gr.created_at DESC
                    LIMIT %s
                """
            elif platform == 'instagram':
                # للانستغرام فقط: تقارير لم تنشر على instagram بعد
                sql = """
                    SELECT gr.id, gr.status, gr.created_at
                    FROM generated_report gr
                    WHERE gr.status IN (
                        'facebook_telegram_published',
                        'ready_for_publishing',
                        'completed',
                        'telegram_published',
                        'facebook_published'
                    )
                    AND gr.status NOT LIKE '%%instagram%%'
                    ORDER BY gr.created_at DESC
                    LIMIT %s
                """
            elif platform == 'telegram':
                # للتيليجرام: تقارير لم تنشر على telegram بعد
                sql = """
                    SELECT gr.id, gr.status, gr.created_at
                    FROM generated_report gr
                    WHERE gr.status IN (
                        'draft',
                        'ready_for_publishing',
                        'completed',
                        'facebook_published',
                        'instagram_published',
                        'facebook_instagram_published'
                    )
                    AND gr.status NOT LIKE '%%telegram%%'
                    AND gr.title IS NOT NULL
                    AND gr.title != ''
                    ORDER BY gr.created_at DESC
                    LIMIT %s
                """
            else:
                # الكل: أي تقارير جاهزة
                sql = """
                    SELECT gr.id, gr.status, gr.created_at
                    FROM generated_report gr
                    WHERE gr.status IN (
                        'ready_for_publishing',
                        'draft',
                        'completed'
                    )
                    ORDER BY gr.created_at DESC
                    LIMIT %s
                """
            
            self.cursor.execute(sql, (limit,))
            results = self.cursor.fetchall()
            
            if results:
                logger.info(f"📊 Found {len(results)} reports for {platform} (limit: {limit})")
                # Log first few report IDs for debugging
                report_ids = [r[0] for r in results[:5]]
                logger.info(f"   Report IDs: {report_ids}")
            else:
                logger.info(f"📭 No reports found for {platform}")
                # Debug: check why no reports
                self._debug_no_reports(platform)
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error getting reports: {e}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return []
    
    def _debug_no_reports(self, platform: str):
        """Debug why no reports are found"""
        if not self.cursor:
            return
        
        try:
            # Check total reports
            self.cursor.execute("SELECT COUNT(*) FROM generated_report")
            result = self.cursor.fetchone()
            total = result[0] if result else 0
            logger.info(f"   📊 Total reports in DB: {total}")
            
            # Check reports by status
            self.cursor.execute("""
                SELECT status, COUNT(*) 
                FROM generated_report 
                GROUP BY status 
                ORDER BY COUNT(*) DESC
                LIMIT 5
            """)
            statuses = self.cursor.fetchall()
            logger.info(f"   📊 Top statuses:")
            for status, count in statuses:
                logger.info(f"      {status}: {count}")
            
            # Check reports with social media content
            self.cursor.execute("""
                SELECT COUNT(DISTINCT gr.id)
                FROM generated_report gr
                WHERE EXISTS (
                    SELECT 1 FROM generated_content gc 
                    WHERE gc.report_id = gr.id 
                    AND gc.content_type_id = 1
                    AND gc.content IS NOT NULL
                )
            """)
            result = self.cursor.fetchone()
            with_content = result[0] if result else 0
            logger.info(f"   📊 Reports with social media content: {with_content}")
            
            # Check reports with images
            self.cursor.execute("""
                SELECT COUNT(DISTINCT gr.id)
                FROM generated_report gr
                WHERE EXISTS (
                    SELECT 1 FROM generated_content gc 
                    WHERE gc.report_id = gr.id 
                    AND gc.content_type_id = 2
                    AND gc.file_url IS NOT NULL
                )
            """)
            result = self.cursor.fetchone()
            with_images = result[0] if result else 0
            logger.info(f"   📊 Reports with generated images: {with_images}")
            
            if platform == 'social_media':
                # Check unpublished on social media
                self.cursor.execute("""
                    SELECT COUNT(*)
                    FROM generated_report
                    WHERE status NOT LIKE '%%facebook%%'
                    AND status NOT LIKE '%%instagram%%'
                """)
                result = self.cursor.fetchone()
                unpublished = result[0] if result else 0
                logger.info(f"   📊 Reports not published on social media: {unpublished}")
            
            elif platform == 'telegram':
                # Check unpublished on telegram
                self.cursor.execute("""
                    SELECT COUNT(*)
                    FROM generated_report
                    WHERE status NOT LIKE '%%telegram%%'
                """)
                result = self.cursor.fetchone()
                unpublished = result[0] if result else 0
                logger.info(f"   📊 Reports not published on telegram: {unpublished}")
                
        except Exception as e:
            logger.error(f"   ⚠️  Debug error: {e}")
    
    def publish_report_to_all_platforms(self, report_id: int, current_status: str) -> Dict:
        """
        نشر تقرير واحد على جميع المنصات
        
        Args:
            report_id: رقم التقرير
            current_status: الحالة الحالية للتقرير
        
        Returns:
            Dict with results for each platform
        """
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📤 Publishing Report #{report_id} to All Platforms")
        logger.info(f"{'='*70}")
        
        results = {
            'report_id': report_id,
            'facebook_post': {'success': False, 'message': 'Not attempted'},
            'facebook_video': {'success': False, 'message': 'Not attempted'},
            'instagram': {'success': False, 'message': 'Not attempted'},
            'telegram': {'success': False, 'message': 'Not attempted'},
            'overall_success': False,
            'published_platforms': []
        }
        
        # Update status to publishing
        self._update_report_status(report_id, 'publishing')
        
        # Publish to each platform
        platforms_to_publish = ['facebook', 'instagram', 'telegram']
        
        for platform in platforms_to_publish:
            publisher = self.publishers.get(platform)
            
            if not publisher:
                results[platform] = {'success': False, 'message': f'{platform} publisher not available'}
                logger.warning(f"⚠️  {platform.title()} publisher not available")
                continue
            
            try:
                logger.info(f"\n🔹 Publishing to {platform.title()}...")
                
                # Publish based on platform
                if platform == 'facebook':
                    # Publish both post and video to Facebook
                    result = publisher.publish(report_id, 'both')
                    
                    # Store individual results
                    if isinstance(result, dict) and 'post' in result and 'video' in result:
                        results['facebook_post'] = result['post']
                        results['facebook_video'] = result['video']
                        
                        # Check if at least one succeeded
                        if result['post']['success'] or result['video']['success']:
                            results['published_platforms'].append('facebook')
                            logger.info(f"✅ Facebook published (Post: {result['post']['success']}, Video: {result['video']['success']})")
                        else:
                            logger.error(f"❌ Facebook failed on both post and video")
                    else:
                        # Fallback for old format
                        results['facebook_post'] = result
                        if result.get('success'):
                            results['published_platforms'].append('facebook')
                            logger.info(f"✅ Facebook published successfully")
                        else:
                            logger.error(f"❌ Facebook failed: {result.get('message', 'Unknown error')}")
                    
                elif platform == 'instagram':
                    result = publisher.publish(report_id, 'both')  # Post + Reel
                    results[platform] = result
                    
                    if result.get('success'):
                        results['published_platforms'].append(platform)
                        logger.info(f"✅ {platform.title()} published successfully")
                    else:
                        logger.error(f"❌ {platform.title()} failed: {result.get('message', 'Unknown error')}")
                
                elif platform == 'telegram':
                    result = publisher.publish(report_id)
                    results[platform] = result
                    
                    if result.get('success'):
                        results['published_platforms'].append(platform)
                        logger.info(f"✅ {platform.title()} published successfully")
                    else:
                        logger.error(f"❌ {platform.title()} failed: {result.get('message', 'Unknown error')}")
                
                # Longer delay between platforms to avoid rate limiting
                time.sleep(5)  # زيادة من 2 إلى 5 ثواني
                
            except Exception as e:
                error_msg = str(e)
                results[platform] = {'success': False, 'message': error_msg}
                logger.error(f"❌ {platform.title()} exception: {error_msg}")
        
        # Determine overall success
        results['overall_success'] = len(results['published_platforms']) > 0
        
        # Update final status
        if results['overall_success']:
            # Create status based on published platforms
            if len(results['published_platforms']) == 3:  # facebook + instagram + telegram
                new_status = 'all_platforms_published'
            else:
                platform_names = '_'.join(sorted(results['published_platforms']))
                new_status = f"{platform_names}_published"
            
            self._update_report_status(report_id, new_status)
            logger.info(f"✅ Report #{report_id} published to: {', '.join(results['published_platforms'])}")
        else:
            self._update_report_status(report_id, 'publishing_failed')
            logger.error(f"❌ Report #{report_id} failed on all platforms")
        
        logger.info(f"{'='*70}\n")
        
        return results
    
    def publish_reports_concurrently(self, reports: List[Tuple[int, str, datetime]]) -> List[Dict]:
        """
        نشر عدة تقارير بشكل متوازي
        
        Args:
            reports: List of (report_id, status, created_at) tuples
        
        Returns:
            List of results for each report
        """
        
        if not reports:
            logger.info("📭 No reports to publish")
            return []
        
        logger.info(f"🚀 Publishing {len(reports)} reports concurrently (max {self.max_reports_per_run} reports per cycle, max {self.max_concurrent_publishes} at once)")
        
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent_publishes) as executor:
            # Submit all publishing tasks
            future_to_report = {
                executor.submit(self.publish_report_to_all_platforms, report_id, status): (report_id, status, created_at)
                for report_id, status, created_at in reports
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_report):
                report_id, status, created_at = future_to_report[future]
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result['overall_success']:
                        logger.info(f"✅ Report #{report_id}: {len(result['published_platforms'])}/3 platforms")
                    else:
                        logger.error(f"❌ Report #{report_id}: Failed on all platforms")
                        
                except Exception as e:
                    logger.error(f"❌ Report #{report_id} exception: {e}")
                    results.append({
                        'report_id': report_id,
                        'overall_success': False,
                        'error': str(e)
                    })
        
        return results
    
    def publish_to_social_media_only(self, report_id: int, current_status: str) -> Dict:
        """
        نشر تقرير على Social Media فقط (Facebook + Instagram)
        
        Args:
            report_id: رقم التقرير
            current_status: الحالة الحالية للتقرير
        
        Returns:
            Dict with results
        """
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📘 Publishing Report #{report_id} to Social Media (FB + IG)")
        logger.info(f"{'='*70}")
        
        results = {
            'report_id': report_id,
            'facebook_post': {'success': False, 'message': 'Not attempted'},
            'facebook_video': {'success': False, 'message': 'Not attempted'},
            'instagram': {'success': False, 'message': 'Not attempted'},
            'overall_success': False,
            'published_platforms': []
        }
        
        # Update status
        self._update_report_status(report_id, 'publishing')
        
        # ============================================
        # 1. Publish to Facebook
        # ============================================
        if not is_publishing_paused('facebook'):
            publisher = self.publishers.get('facebook')
            
            if publisher:
                try:
                    logger.info(f"🔹 Publishing to Facebook...")
                    
                    # Publish both post and video
                    result = publisher.publish(report_id, 'both')
                    
                    # Store individual results
                    if isinstance(result, dict) and 'post' in result and 'video' in result:
                        results['facebook_post'] = result['post']
                        results['facebook_video'] = result['video']
                        
                        # Check if at least one succeeded
                        if result['post']['success'] or result['video']['success']:
                            results['published_platforms'].append('facebook')
                            logger.info(f"✅ Facebook published (Post: {result['post']['success']}, Video: {result['video']['success']})")
                        else:
                            logger.error(f"❌ Facebook failed on both post and video")
                    else:
                        # Fallback
                        results['facebook_post'] = result
                        if result.get('success'):
                            results['published_platforms'].append('facebook')
                            logger.info(f"✅ Facebook published successfully")
                        else:
                            logger.error(f"❌ Facebook failed: {result.get('message', 'Unknown error')}")
                            
                except Exception as e:
                    error_msg = str(e)
                    results['facebook_post'] = {'success': False, 'message': error_msg}
                    logger.error(f"❌ Facebook exception: {error_msg}")
            else:
                logger.warning(f"⚠️  Facebook publisher not available")
        else:
            logger.warning(f"⏸️  Facebook publishing is paused")
            results['facebook_post'] = {'success': False, 'message': 'Publishing paused'}
            results['facebook_video'] = {'success': False, 'message': 'Publishing paused'}
        
        # ============================================
        # 2. Publish to Instagram
        # ============================================
        if not is_publishing_paused('instagram'):
            publisher = self.publishers.get('instagram')
            
            if publisher:
                try:
                    logger.info(f"🔹 Publishing to Instagram...")
                    
                    # Publish both post and reel
                    result = publisher.publish(report_id, 'both')
                    results['instagram'] = result
                    
                    if result.get('success'):
                        results['published_platforms'].append('instagram')
                        logger.info(f"✅ Instagram published successfully")
                    else:
                        logger.error(f"❌ Instagram failed: {result.get('message', 'Unknown error')}")
                        
                except Exception as e:
                    error_msg = str(e)
                    results['instagram'] = {'success': False, 'message': error_msg}
                    logger.error(f"❌ Instagram exception: {error_msg}")
            else:
                logger.warning(f"⚠️  Instagram publisher not available")
        else:
            logger.warning(f"⏸️  Instagram publishing is paused")
            results['instagram'] = {'success': False, 'message': 'Publishing paused'}
        
        # ============================================
        # 3. Update final status
        # ============================================
        results['overall_success'] = len(results['published_platforms']) > 0
        
        if results['overall_success']:
            # Create status based on published platforms
            platform_names = '_'.join(sorted(results['published_platforms']))
            new_status = f"{platform_names}_published"
            self._update_report_status(report_id, new_status)
            logger.info(f"✅ Social Media published to: {', '.join(results['published_platforms'])}")
        else:
            self._update_report_status(report_id, 'publishing_failed')
            logger.error(f"❌ All social media platforms failed")
        
        logger.info(f"{'='*70}\n")
        
        return results
    
    def publish_to_telegram_only(self, report_id: int, current_status: str) -> Dict:
        """
        نشر تقرير على Telegram فقط
        
        Args:
            report_id: رقم التقرير
            current_status: الحالة الحالية للتقرير
        
        Returns:
            Dict with results
        """
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📱 Publishing Report #{report_id} to Telegram")
        logger.info(f"{'='*70}")
        
        results = {
            'report_id': report_id,
            'telegram': {'success': False, 'message': 'Not attempted'},
            'overall_success': False,
            'published_platforms': []
        }
        
        # Update status
        self._update_report_status(report_id, 'publishing')
        
        # Publish to Telegram
        publisher = self.publishers.get('telegram')
        
        if not publisher:
            results['telegram'] = {'success': False, 'message': 'Telegram publisher not available'}
            logger.warning(f"⚠️  Telegram publisher not available")
            self._update_report_status(report_id, 'publishing_failed')
            return results
        
        try:
            logger.info(f"🔹 Publishing to Telegram...")
            
            result = publisher.publish(report_id)
            results['telegram'] = result
            
            if result.get('success'):
                results['published_platforms'].append('telegram')
                results['overall_success'] = True
                
                # Update status based on current status
                if 'facebook' in current_status.lower():
                    new_status = 'all_platforms_published'
                else:
                    new_status = 'telegram_published'
                
                self._update_report_status(report_id, new_status)
                logger.info(f"✅ Telegram published successfully")
            else:
                self._update_report_status(report_id, 'publishing_failed')
                logger.error(f"❌ Telegram failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            error_msg = str(e)
            results['telegram'] = {'success': False, 'message': error_msg}
            logger.error(f"❌ Telegram exception: {error_msg}")
            self._update_report_status(report_id, 'publishing_failed')
        
        logger.info(f"{'='*70}\n")
        
        return results
    
    def publish_to_facebook_only(self, report_id: int, current_status: str) -> Dict:
        """
        نشر تقرير على Facebook فقط
        
        Args:
            report_id: رقم التقرير
            current_status: الحالة الحالية للتقرير
        
        Returns:
            Dict with results
        """
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📘 Publishing Report #{report_id} to Facebook Only")
        logger.info(f"{'='*70}")
        
        results = {
            'report_id': report_id,
            'facebook_post': {'success': False, 'message': 'Not attempted'},
            'facebook_video': {'success': False, 'message': 'Not attempted'},
            'overall_success': False,
            'published_platforms': []
        }
        
        # Check if paused
        if is_publishing_paused('facebook'):
            logger.warning(f"⏸️  Facebook publishing is paused")
            results['facebook_post'] = {'success': False, 'message': 'Publishing paused'}
            results['facebook_video'] = {'success': False, 'message': 'Publishing paused'}
            return results
        
        # Update status
        self._update_report_status(report_id, 'publishing')
        
        # Publish to Facebook
        publisher = self.publishers.get('facebook')
        
        if not publisher:
            results['facebook_post'] = {'success': False, 'message': 'Facebook publisher not available'}
            logger.warning(f"⚠️  Facebook publisher not available")
            self._update_report_status(report_id, current_status)  # Restore status
            return results
        
        try:
            logger.info(f"🔹 Publishing to Facebook...")
            
            # Publish both post and video
            result = publisher.publish(report_id, 'both')
            
            # Store individual results
            if isinstance(result, dict) and 'post' in result and 'video' in result:
                results['facebook_post'] = result['post']
                results['facebook_video'] = result['video']
                
                # Check if at least one succeeded
                if result['post']['success'] or result['video']['success']:
                    results['published_platforms'].append('facebook')
                    results['overall_success'] = True
                    logger.info(f"✅ Facebook published (Post: {result['post']['success']}, Video: {result['video']['success']})")
                else:
                    logger.error(f"❌ Facebook failed on both post and video")
            else:
                # Fallback
                results['facebook_post'] = result
                if result.get('success'):
                    results['published_platforms'].append('facebook')
                    results['overall_success'] = True
                    logger.info(f"✅ Facebook published successfully")
                else:
                    logger.error(f"❌ Facebook failed: {result.get('message', 'Unknown error')}")
            
            # Update status
            if results['overall_success']:
                # Determine new status based on current status
                if 'instagram' in current_status.lower():
                    new_status = 'facebook_instagram_published'
                elif 'telegram' in current_status.lower():
                    new_status = 'facebook_telegram_published'
                else:
                    new_status = 'facebook_published'
                self._update_report_status(report_id, new_status)
            else:
                self._update_report_status(report_id, current_status)  # Restore status
                
        except Exception as e:
            error_msg = str(e)
            results['facebook_post'] = {'success': False, 'message': error_msg}
            logger.error(f"❌ Facebook exception: {error_msg}")
            self._update_report_status(report_id, current_status)  # Restore status
        
        logger.info(f"{'='*70}\n")
        
        return results
    
    def publish_to_instagram_only(self, report_id: int, current_status: str) -> Dict:
        """
        نشر تقرير على Instagram فقط
        
        Args:
            report_id: رقم التقرير
            current_status: الحالة الحالية للتقرير
        
        Returns:
            Dict with results
        """
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📸 Publishing Report #{report_id} to Instagram Only")
        logger.info(f"{'='*70}")
        
        results = {
            'report_id': report_id,
            'instagram_post': {'success': False, 'message': 'Not attempted'},
            'instagram_reel': {'success': False, 'message': 'Not attempted'},
            'overall_success': False,
            'published_platforms': []
        }
        
        # Check if paused
        if is_publishing_paused('instagram'):
            logger.warning(f"⏸️  Instagram publishing is paused")
            results['instagram_post'] = {'success': False, 'message': 'Publishing paused'}
            results['instagram_reel'] = {'success': False, 'message': 'Publishing paused'}
            return results
        
        # Update status
        self._update_report_status(report_id, 'publishing')
        
        # Publish to Instagram
        publisher = self.publishers.get('instagram')
        
        if not publisher:
            results['instagram_post'] = {'success': False, 'message': 'Instagram publisher not available'}
            logger.warning(f"⚠️  Instagram publisher not available")
            self._update_report_status(report_id, current_status)  # Restore status
            return results
        
        try:
            logger.info(f"🔹 Publishing to Instagram...")
            
            # Publish both post and reel
            result = publisher.publish(report_id, 'both')
            
            # Store results
            if isinstance(result, dict):
                if 'post' in result:
                    results['instagram_post'] = result['post']
                if 'reel' in result:
                    results['instagram_reel'] = result['reel']
                
                # Check success - handle case where post/reel might be None
                post_result = result.get('post') or {}
                reel_result = result.get('reel') or {}
                post_success = post_result.get('success', False)
                reel_success = reel_result.get('success', False)
                
                if post_success or reel_success or result.get('success'):
                    results['published_platforms'].append('instagram')
                    results['overall_success'] = True
                    logger.info(f"✅ Instagram published (Post: {post_success}, Reel: {reel_success})")
                else:
                    logger.error(f"❌ Instagram failed: {result.get('message', 'Unknown error')}")
            elif result is None:
                logger.error(f"❌ Instagram publisher returned None")
            else:
                logger.error(f"❌ Instagram returned unexpected result type: {type(result)}")
            
            # Update status
            if results['overall_success']:
                # Determine new status based on current status
                if 'facebook' in current_status.lower():
                    new_status = 'facebook_instagram_published'
                elif 'telegram' in current_status.lower():
                    new_status = 'instagram_telegram_published'
                else:
                    new_status = 'instagram_published'
                self._update_report_status(report_id, new_status)
            else:
                self._update_report_status(report_id, current_status)  # Restore status
                
        except Exception as e:
            error_msg = str(e)
            results['instagram_post'] = {'success': False, 'message': error_msg}
            logger.error(f"❌ Instagram exception: {error_msg}")
            self._update_report_status(report_id, current_status)  # Restore status
        
        logger.info(f"{'='*70}\n")
        
        return results
    
    def run_publishing_cycle(self) -> Dict:
        """
        تشغيل دورة نشر كاملة
        
        ينشر على Social Media (1 تقرير) و Telegram (3 تقارير) بشكل منفصل
        
        Returns:
            Summary of publishing results
        """
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📤 Starting Publishers Job Cycle")
        logger.info(f"   Social Media (FB/IG): {self.max_social_media_reports} report(s)/cycle")
        logger.info(f"   Telegram: {self.max_reports_per_run} reports/cycle")
        logger.info(f"   Max concurrent publishes: {self.max_concurrent_publishes}")
        logger.info(f"{'='*70}")
        
        start_time = datetime.now()
        all_results = []
        
        # ═══════════════════════════════════════════════════════════
        # 1. نشر على Social Media (Facebook + Instagram) - 1 تقرير فقط
        # ═══════════════════════════════════════════════════════════
        logger.info(f"\n{'─'*70}")
        logger.info(f"📘 Phase 1: Social Media Publishing (FB + IG)")
        logger.info(f"{'─'*70}")
        
        social_reports = self.get_reports_ready_for_publishing('social_media')
        
        if social_reports:
            logger.info(f"📊 Publishing {len(social_reports)} report(s) to Social Media...")
            
            for report_id, status, created_at in social_reports:
                result = self.publish_to_social_media_only(report_id, status)
                all_results.append(result)
                
                # تأخير بين التقارير لتجنب rate limiting
                if len(social_reports) > 1:
                    time.sleep(60)  # دقيقة بين كل تقرير
        else:
            logger.info("📭 No reports for Social Media")
        
        # ═══════════════════════════════════════════════════════════
        # 2. نشر على Telegram - 3 تقارير
        # ═══════════════════════════════════════════════════════════
        logger.info(f"\n{'─'*70}")
        logger.info(f"📱 Phase 2: Telegram Publishing")
        logger.info(f"{'─'*70}")
        
        telegram_reports = self.get_reports_ready_for_publishing('telegram')
        
        if telegram_reports:
            logger.info(f"📊 Publishing {len(telegram_reports)} report(s) to Telegram...")
            
            for report_id, status, created_at in telegram_reports:
                result = self.publish_to_telegram_only(report_id, status)
                all_results.append(result)
                
                # تأخير صغير بين التقارير
                if len(telegram_reports) > 1:
                    time.sleep(5)  # 5 ثواني بين كل تقرير
        else:
            logger.info("📭 No reports for Telegram")
        
        # ═══════════════════════════════════════════════════════════
        # 3. حساب الملخص
        # ═══════════════════════════════════════════════════════════
        total_reports = len(all_results)
        successful_reports = sum(1 for r in all_results if r.get('overall_success', False))
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # 4. Log summary
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 Publishers Job Summary")
        logger.info(f"{'='*70}")
        logger.info(f"Reports processed: {total_reports}")
        logger.info(f"Reports published: {successful_reports}")
        logger.info(f"Success rate: {(successful_reports/total_reports*100):.1f}%" if total_reports > 0 else "N/A")
        logger.info(f"Duration: {duration:.2f} seconds")
        
        # Platform breakdown
        platform_stats = {'facebook': 0, 'instagram': 0, 'telegram': 0}
        for result in all_results:
            for platform in result.get('published_platforms', []):
                platform_stats[platform] += 1
        
        logger.info(f"Platform stats:")
        for platform, count in platform_stats.items():
            logger.info(f"  {platform.title()}: {count}/{total_reports}")
        
        # Facebook detailed stats (post vs video)
        fb_post_success = sum(1 for r in all_results if (r.get('facebook_post') or {}).get('success', False))
        fb_video_success = sum(1 for r in all_results if (r.get('facebook_video') or {}).get('success', False))
        if fb_post_success > 0 or fb_video_success > 0:
            logger.info(f"  Facebook Posts: {fb_post_success}/{total_reports}")
            logger.info(f"  Facebook Videos: {fb_video_success}/{total_reports}")
        
        logger.info(f"{'='*70}\n")
        
        return {
            'success': True,
            'reports_processed': total_reports,
            'reports_published': successful_reports,
            'platform_stats': platform_stats,
            'duration_seconds': duration,
            'results': all_results,
            'social_media_count': len(social_reports) if social_reports else 0,
            'telegram_count': len(telegram_reports) if telegram_reports else 0
        }
        
        logger.info(f"{'='*70}\n")
        
        return {
            'success': True,
            'reports_processed': total_reports,
            'reports_published': successful_reports,
            'platform_stats': platform_stats,
            'duration_seconds': duration,
            'results': results
        }
    
    def _update_report_status(self, report_id: int, new_status: str):
        """Update report status in database"""
        
        if not self.conn or not self.cursor:
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
            
        except Exception as e:
            logger.error(f"❌ Status update failed for report {report_id}: {e}")
            if self.conn:
                self.conn.rollback()
    
    def __del__(self):
        """Cleanup database connection"""
        if hasattr(self, 'cursor') and self.cursor:
            self.cursor.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()


# ============================================
# Job Function (for scheduler)
# ============================================

def publish_to_social_media():
    """
    Main job function for the scheduler
    
    Returns:
        Dict with execution results
    """
    
    try:
        job = PublishersJob()
        result = job.run_publishing_cycle()
        
        logger.info(f"✅ Publishers job completed: {result['reports_published']}/{result['reports_processed']} reports published")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Publishers job failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'reports_processed': 0,
            'reports_published': 0
        }


def publish_content():
    """
    Alias for publish_to_social_media() for backward compatibility
    
    Returns:
        Dict with execution results
    """
    return publish_to_social_media()


# ============================================
# Separate Platform Publishing Functions
# ============================================

def run_facebook_cycle(limit: int = 1) -> Dict:
    """
    دورة نشر منفصلة للفيسبوك فقط
    
    Args:
        limit: عدد التقارير للنشر
    
    Returns:
        Dict with execution results
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"📘 Starting Facebook Only Publishing Cycle")
    logger.info(f"   Limit: {limit} report(s)")
    logger.info(f"{'='*70}")
    
    start_time = datetime.now()
    results = []
    
    try:
        job = PublishersJob()
        
        # Get reports ready for Facebook
        reports = job.get_reports_ready_for_publishing('facebook', limit=limit)
        
        if not reports:
            logger.info("📭 No reports ready for Facebook publishing")
            return {
                'success': True,
                'platform': 'facebook',
                'reports_processed': 0,
                'reports_published': 0,
                'results': []
            }
        
        logger.info(f"📊 Found {len(reports)} report(s) for Facebook")
        
        for report_id, status, created_at in reports:
            result = job.publish_to_facebook_only(report_id, status)
            results.append(result)
            
            # Delay between reports
            if len(reports) > 1:
                time.sleep(30)
        
        # Calculate stats
        successful = sum(1 for r in results if r.get('overall_success', False))
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📘 Facebook Cycle Complete")
        logger.info(f"   Published: {successful}/{len(results)}")
        logger.info(f"   Duration: {duration:.2f}s")
        logger.info(f"{'='*70}\n")
        
        return {
            'success': True,
            'platform': 'facebook',
            'reports_processed': len(results),
            'reports_published': successful,
            'duration_seconds': duration,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"❌ Facebook cycle failed: {e}")
        return {
            'success': False,
            'platform': 'facebook',
            'error': str(e),
            'reports_processed': 0,
            'reports_published': 0
        }


def run_instagram_cycle(limit: int = 1) -> Dict:
    """
    دورة نشر منفصلة للانستغرام فقط
    
    Args:
        limit: عدد التقارير للنشر
    
    Returns:
        Dict with execution results
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"📸 Starting Instagram Only Publishing Cycle")
    logger.info(f"   Limit: {limit} report(s)")
    logger.info(f"{'='*70}")
    
    start_time = datetime.now()
    results = []
    
    try:
        job = PublishersJob()
        
        # Get reports ready for Instagram
        reports = job.get_reports_ready_for_publishing('instagram', limit=limit)
        
        if not reports:
            logger.info("📭 No reports ready for Instagram publishing")
            return {
                'success': True,
                'platform': 'instagram',
                'reports_processed': 0,
                'reports_published': 0,
                'results': []
            }
        
        logger.info(f"📊 Found {len(reports)} report(s) for Instagram")
        
        for report_id, status, created_at in reports:
            result = job.publish_to_instagram_only(report_id, status)
            results.append(result)
            
            # Delay between reports
            if len(reports) > 1:
                time.sleep(30)
        
        # Calculate stats
        successful = sum(1 for r in results if r.get('overall_success', False))
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📸 Instagram Cycle Complete")
        logger.info(f"   Published: {successful}/{len(results)}")
        logger.info(f"   Duration: {duration:.2f}s")
        logger.info(f"{'='*70}\n")
        
        return {
            'success': True,
            'platform': 'instagram',
            'reports_processed': len(results),
            'reports_published': successful,
            'duration_seconds': duration,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"❌ Instagram cycle failed: {e}")
        return {
            'success': False,
            'platform': 'instagram',
            'error': str(e),
            'reports_processed': 0,
            'reports_published': 0
        }


def run_telegram_cycle(limit: int = 10) -> Dict:
    """
    دورة نشر منفصلة للتيليجرام فقط
    
    Args:
        limit: عدد التقارير للنشر
    
    Returns:
        Dict with execution results
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"📱 Starting Telegram Only Publishing Cycle")
    logger.info(f"   Limit: {limit} report(s)")
    logger.info(f"{'='*70}")
    
    start_time = datetime.now()
    results = []
    
    try:
        job = PublishersJob()
        
        # Get reports ready for Telegram
        reports = job.get_reports_ready_for_publishing('telegram', limit=limit)
        
        if not reports:
            logger.info("📭 No reports ready for Telegram publishing")
            return {
                'success': True,
                'platform': 'telegram',
                'reports_processed': 0,
                'reports_published': 0,
                'results': []
            }
        
        logger.info(f"📊 Found {len(reports)} report(s) for Telegram")
        
        for report_id, status, created_at in reports:
            result = job.publish_to_telegram_only(report_id, status)
            results.append(result)
            
            # Delay between reports
            if len(reports) > 1:
                time.sleep(5)
        
        # Calculate stats
        successful = sum(1 for r in results if r.get('overall_success', False))
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📱 Telegram Cycle Complete")
        logger.info(f"   Published: {successful}/{len(results)}")
        logger.info(f"   Duration: {duration:.2f}s")
        logger.info(f"{'='*70}\n")
        
        return {
            'success': True,
            'platform': 'telegram',
            'reports_processed': len(results),
            'reports_published': successful,
            'duration_seconds': duration,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"❌ Telegram cycle failed: {e}")
        return {
            'success': False,
            'platform': 'telegram',
            'error': str(e),
            'reports_processed': 0,
            'reports_published': 0
        }


def run_separate_cycles() -> Dict:
    """
    تشغيل دورات نشر منفصلة لكل منصة
    
    Returns:
        Dict with results for each platform
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"🚀 Starting Separate Publishing Cycles")
    logger.info(f"{'='*70}")
    
    start_time = datetime.now()
    
    # Run each platform separately
    facebook_result = run_facebook_cycle(limit=1)
    time.sleep(10)  # Delay between platforms
    
    instagram_result = run_instagram_cycle(limit=1)
    time.sleep(10)
    
    telegram_result = run_telegram_cycle(limit=10)
    
    duration = (datetime.now() - start_time).total_seconds()
    
    # Summary
    total_processed = (
        facebook_result.get('reports_processed', 0) +
        instagram_result.get('reports_processed', 0) +
        telegram_result.get('reports_processed', 0)
    )
    total_published = (
        facebook_result.get('reports_published', 0) +
        instagram_result.get('reports_published', 0) +
        telegram_result.get('reports_published', 0)
    )
    
    logger.info(f"\n{'='*70}")
    logger.info(f"📊 Separate Cycles Summary")
    logger.info(f"{'='*70}")
    logger.info(f"Facebook:  {facebook_result.get('reports_published', 0)}/{facebook_result.get('reports_processed', 0)}")
    logger.info(f"Instagram: {instagram_result.get('reports_published', 0)}/{instagram_result.get('reports_processed', 0)}")
    logger.info(f"Telegram:  {telegram_result.get('reports_published', 0)}/{telegram_result.get('reports_processed', 0)}")
    logger.info(f"Total:     {total_published}/{total_processed}")
    logger.info(f"Duration:  {duration:.2f}s")
    logger.info(f"{'='*70}\n")
    
    return {
        'success': True,
        'facebook': facebook_result,
        'instagram': instagram_result,
        'telegram': telegram_result,
        'total_processed': total_processed,
        'total_published': total_published,
        'duration_seconds': duration
    }


# ============================================
# Testing & Manual Execution
# ============================================

if __name__ == '__main__':
    import sys
    
    # Setup logging for testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    def print_usage():
        print("""
Usage: python publishers_job.py [command] [options]

Commands:
  <report_id>       Publish single report to all platforms
  --facebook        Run Facebook only cycle
  --instagram       Run Instagram only cycle  
  --telegram        Run Telegram only cycle
  --separate        Run separate cycles for each platform
  --all             Run combined cycle (default)
  
Options:
  --limit=N         Number of reports to publish (default: 1 for FB/IG, 10 for Telegram)

Examples:
  python publishers_job.py 123              # Publish report #123 to all platforms
  python publishers_job.py --facebook       # Run Facebook cycle
  python publishers_job.py --instagram      # Run Instagram cycle
  python publishers_job.py --telegram       # Run Telegram cycle
  python publishers_job.py --separate       # Run all platforms separately
  python publishers_job.py --facebook --limit=2  # Publish 2 reports to Facebook
        """)
    
    # Parse arguments
    args = sys.argv[1:]
    
    if not args or '--help' in args or '-h' in args:
        print_usage()
        if not args:
            # Default: run combined cycle
            logger.info("🧪 Running default combined publishing cycle")
            result = publish_to_social_media()
            print(f"\n✅ Done! Published: {result.get('reports_published', 0)}/{result.get('reports_processed', 0)}")
    
    elif '--facebook' in args:
        # Facebook only
        limit = 1
        for arg in args:
            if arg.startswith('--limit='):
                limit = int(arg.split('=')[1])
        
        logger.info(f"🧪 Running Facebook only cycle (limit: {limit})")
        result = run_facebook_cycle(limit=limit)
        print(f"\n📘 Facebook: {result.get('reports_published', 0)}/{result.get('reports_processed', 0)} published")
    
    elif '--instagram' in args:
        # Instagram only
        limit = 1
        for arg in args:
            if arg.startswith('--limit='):
                limit = int(arg.split('=')[1])
        
        logger.info(f"🧪 Running Instagram only cycle (limit: {limit})")
        result = run_instagram_cycle(limit=limit)
        print(f"\n📸 Instagram: {result.get('reports_published', 0)}/{result.get('reports_processed', 0)} published")
    
    elif '--telegram' in args:
        # Telegram only
        limit = 3
        for arg in args:
            if arg.startswith('--limit='):
                limit = int(arg.split('=')[1])
        
        logger.info(f"🧪 Running Telegram only cycle (limit: {limit})")
        result = run_telegram_cycle(limit=limit)
        print(f"\n📱 Telegram: {result.get('reports_published', 0)}/{result.get('reports_processed', 0)} published")
    
    elif '--separate' in args:
        # Separate cycles for each platform
        logger.info("🧪 Running separate cycles for each platform")
        result = run_separate_cycles()
        print(f"\n📊 Summary:")
        print(f"   Facebook:  {result['facebook'].get('reports_published', 0)}/{result['facebook'].get('reports_processed', 0)}")
        print(f"   Instagram: {result['instagram'].get('reports_published', 0)}/{result['instagram'].get('reports_processed', 0)}")
        print(f"   Telegram:  {result['telegram'].get('reports_published', 0)}/{result['telegram'].get('reports_processed', 0)}")
        print(f"   Total:     {result['total_published']}/{result['total_processed']}")
    
    elif '--all' in args:
        # Combined cycle
        logger.info("🧪 Running combined publishing cycle")
        result = publish_to_social_media()
        print(f"\n✅ Done! Published: {result.get('reports_published', 0)}/{result.get('reports_processed', 0)}")
    
    else:
        # Try to parse as report_id
        try:
            report_id = int(args[0])
            logger.info(f"🧪 Testing single report publishing: {report_id}")
            
            job = PublishersJob()
            result = job.publish_report_to_all_platforms(report_id, 'draft')
            
            print(f"\n{'='*70}")
            print(f"📊 SINGLE REPORT TEST RESULT:")
            print(f"{'='*70}")
            print(f"Report ID: {result['report_id']}")
            print(f"Overall Success: {result['overall_success']}")
            print(f"Published Platforms: {', '.join(result['published_platforms'])}")
            
            for platform in ['facebook', 'instagram', 'telegram']:
                platform_result = result.get(platform, {})
                status = "✅" if platform_result.get('success') else "❌"
                print(f"{platform.title()}: {status} {platform_result.get('message', '')}")
            
            print(f"{'='*70}\n")
            
        except ValueError:
            print(f"❌ Unknown command: {args[0]}")
            print_usage()
