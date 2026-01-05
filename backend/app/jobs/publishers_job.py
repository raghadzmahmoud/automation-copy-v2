#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
📤 Publishers Job - Multi-Platform Publishing
═══════════════════════════════════════════════════════════════
ينشر التقارير على جميع منصات السوشال ميديا:
- Facebook (h-GAZA + DOT)
- Instagram (Posts + Reels)
- Telegram

يعمل بشكل دوري ويبحث عن التقارير الجاهزة للنشر
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import logging
import psycopg2
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from settings import DB_CONFIG
from app.services.publishers.facebook_publisher import FacebookPublisher
from app.services.publishers.instagram_publisher import InstagramPublisher
from app.services.publishers.publish_telegram import TelegramPublisher

logger = logging.getLogger(__name__)


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
        self.max_concurrent_publishes = 3  # عدد التقارير التي تنشر بنفس الوقت
        self.max_reports_per_run = 10      # أقصى عدد تقارير في كل دورة
    
    def get_reports_ready_for_publishing(self) -> List[Tuple[int, str, datetime]]:
        """
        جلب التقارير الجاهزة للنشر
        
        Returns:
            List of (report_id, current_status, created_at) tuples
        """
        
        if not self.cursor:
            return []
        
        try:
            # البحث عن التقارير التي لها محتوى سوشال ميديا
            # نبسط الاستعلام - الـ publishers سيتحققون من وجود الصور بأنفسهم
            sql = """
                SELECT DISTINCT gr.id, gr.status, gr.created_at
                FROM generated_report gr
                WHERE gr.status IN (
                    'ready_for_publishing',
                    'draft',
                    'completed'
                )
                AND EXISTS (
                    SELECT 1 FROM generated_content gc 
                    WHERE gc.report_id = gr.id 
                    AND gc.content_type_id = 1  -- Social Media Content
                    AND gc.content IS NOT NULL
                )
                ORDER BY gr.created_at DESC
                LIMIT %s
            """
            
            self.cursor.execute(sql, (self.max_reports_per_run,))
            results = self.cursor.fetchall()
            
            logger.info(f"📊 Found {len(results)} reports ready for publishing")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error getting reports: {e}")
            return []
    
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
            'facebook': {'success': False, 'message': 'Not attempted'},
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
                    result = publisher.publish(report_id)
                elif platform == 'instagram':
                    result = publisher.publish(report_id, 'both')  # Post + Reel
                elif platform == 'telegram':
                    result = publisher.publish(report_id)
                
                results[platform] = result
                
                if result.get('success'):
                    results['published_platforms'].append(platform)
                    logger.info(f"✅ {platform.title()} published successfully")
                else:
                    logger.error(f"❌ {platform.title()} failed: {result.get('message', 'Unknown error')}")
                
                # Small delay between platforms
                time.sleep(2)
                
            except Exception as e:
                error_msg = str(e)
                results[platform] = {'success': False, 'message': error_msg}
                logger.error(f"❌ {platform.title()} exception: {error_msg}")
        
        # Determine overall success
        results['overall_success'] = len(results['published_platforms']) > 0
        
        # Update final status
        if results['overall_success']:
            # Create status based on published platforms
            if len(results['published_platforms']) == 3:
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
        
        logger.info(f"🚀 Publishing {len(reports)} reports concurrently (max {self.max_concurrent_publishes} at once)")
        
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
    
    def run_publishing_cycle(self) -> Dict:
        """
        تشغيل دورة نشر كاملة
        
        Returns:
            Summary of publishing results
        """
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📤 Starting Publishers Job Cycle")
        logger.info(f"{'='*70}")
        
        start_time = datetime.now()
        
        # 1. Get reports ready for publishing
        reports = self.get_reports_ready_for_publishing()
        
        if not reports:
            logger.info("📭 No reports ready for publishing")
            return {
                'success': True,
                'reports_processed': 0,
                'reports_published': 0,
                'duration_seconds': 0,
                'message': 'No reports to publish'
            }
        
        # 2. Publish reports
        results = self.publish_reports_concurrently(reports)
        
        # 3. Calculate summary
        total_reports = len(results)
        successful_reports = sum(1 for r in results if r.get('overall_success', False))
        
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
        for result in results:
            for platform in result.get('published_platforms', []):
                platform_stats[platform] += 1
        
        logger.info(f"Platform stats:")
        for platform, count in platform_stats.items():
            logger.info(f"  {platform.title()}: {count}/{total_reports}")
        
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
    
    if len(sys.argv) > 1:
        # Manual single report publishing
        try:
            report_id = int(sys.argv[1])
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
                platform_result = result[platform]
                status = "✅" if platform_result['success'] else "❌"
                print(f"{platform.title()}: {status} {platform_result.get('message', '')}")
            
            print(f"{'='*70}\n")
            
        except ValueError:
            logger.error("❌ Invalid report_id. Please provide a valid integer.")
        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
    else:
        # Run full publishing cycle
        logger.info("🧪 Testing full publishing cycle")
        result = publish_to_social_media()
        
        print(f"\n{'='*70}")
        print(f"📊 FULL CYCLE TEST RESULT:")
        print(f"{'='*70}")
        print(f"Success: {result['success']}")
        print(f"Reports Processed: {result.get('reports_processed', 0)}")
        print(f"Reports Published: {result.get('reports_published', 0)}")
        if result.get('platform_stats'):
            print("Platform Stats:")
            for platform, count in result['platform_stats'].items():
                print(f"  {platform.title()}: {count}")
        print(f"Duration: {result.get('duration_seconds', 0):.2f}s")
        print(f"{'='*70}\n")