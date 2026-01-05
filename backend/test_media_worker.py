#!/usr/bin/env python3
"""
🎯 Media Worker - Images, Reels & Publishing Only
═══════════════════════════════════════════════════════════════
وركر إنتاج مخصص لـ:
- توليد الصور (Social Media Images) - 1 تقرير
- توليد الريلز (Reels) - 1 تقرير  
- النشر (Publishing)

Production Deployment Worker for Render
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import logging
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup logging for production
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global health status
health_status = {
    'status': 'starting',
    'last_cycle': None,
    'cycles_completed': 0,
    'last_error': None
}


class HealthHandler(BaseHTTPRequestHandler):
    """Health check handler for Render"""
    
    def do_GET(self):
        if self.path == '/health':
            # Health check endpoint
            status_code = 200 if health_status['status'] == 'healthy' else 503
            
            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            import json
            response = {
                'status': health_status['status'],
                'worker_type': 'media',
                'last_cycle': health_status['last_cycle'],
                'cycles_completed': health_status['cycles_completed'],
                'last_error': health_status['last_error']
            }
            
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress HTTP server logs
        pass


def start_health_server():
    """Start health check server in background"""
    try:
        port = int(os.getenv('PORT', 8000))
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        logger.info(f"🏥 Health server started on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"❌ Health server failed: {e}")


def test_social_media_images():
    """اختبار توليد صور السوشال ميديا"""
    logger.info("=" * 70)
    logger.info("🖼️  Testing Social Media Image Generation")
    logger.info("=" * 70)
    
    try:
        from app.services.generators.social_media_image_generator import SocialImageGenerator
        
        generator = SocialImageGenerator()
        
        # توليد صور لتقرير واحد فقط
        stats = generator.generate_for_all_reports(force_update=False, limit=1)
        
        logger.info(f"📊 Social Media Images Results:")
        logger.info(f"   Total reports: {stats.get('total_reports', 0)}")
        logger.info(f"   Success: {stats.get('success', 0)}")
        logger.info(f"   Updated: {stats.get('updated', 0)}")
        logger.info(f"   Failed: {stats.get('failed', 0)}")
        logger.info(f"   Skipped: {stats.get('skipped', 0)}")
        
        generator.close()
        
        success_count = stats.get('success', 0) + stats.get('updated', 0)
        return success_count > 0
        
    except Exception as e:
        logger.error(f"❌ Social Media Images failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_reel_generation():
    """اختبار توليد الريلز"""
    logger.info("=" * 70)
    logger.info("🎬 Testing Reel Generation")
    logger.info("=" * 70)
    
    try:
        from app.services.generators.reel_generator import ReelGenerator
        
        generator = ReelGenerator()
        
        # توليد ريل لتقرير واحد فقط
        stats = generator.generate_for_all_reports(force_update=False, limit=1)
        
        logger.info(f"📊 Reel Generation Results:")
        logger.info(f"   Total reports: {stats.get('total_reports', 0)}")
        logger.info(f"   Success: {stats.get('success', 0)}")
        logger.info(f"   Updated: {stats.get('updated', 0)}")
        logger.info(f"   Failed: {stats.get('failed', 0)}")
        
        generator.close()
        
        success_count = stats.get('success', 0) + stats.get('updated', 0)
        return success_count > 0
        
    except Exception as e:
        logger.error(f"❌ Reel Generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_publishing():
    """اختبار النشر"""
    logger.info("=" * 70)
    logger.info("📤 Testing Publishing")
    logger.info("=" * 70)
    
    try:
        from app.jobs.publishers_job import publish_content
        
        # تشغيل النشر
        result = publish_content()
        
        logger.info(f"📊 Publishing Results:")
        if isinstance(result, dict):
            for platform, count in result.items():
                logger.info(f"   {platform}: {count} items published")
        else:
            logger.info(f"   Result: {result}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Publishing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_media_cycle():
    """تشغيل دورة كاملة للميديا"""
    logger.info("🚀 Starting Media Worker Cycle")
    logger.info(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Update health status
    health_status['status'] = 'running'
    health_status['last_cycle'] = datetime.now().isoformat()
    
    results = {
        'social_images': False,
        'reels': False,
        'publishing': False
    }
    
    try:
        # 1. توليد صور السوشال ميديا
        logger.info("\n🔄 Step 1: Social Media Images")
        results['social_images'] = test_social_media_images()
        
        # انتظار قصير بين المهام
        time.sleep(5)
        
        # 2. توليد الريلز
        logger.info("\n🔄 Step 2: Reel Generation")
        results['reels'] = test_reel_generation()
        
        # انتظار قصير بين المهام
        time.sleep(5)
        
        # 3. النشر
        logger.info("\n🔄 Step 3: Publishing")
        results['publishing'] = test_publishing()
        
        # النتائج النهائية
        logger.info("=" * 70)
        logger.info("📊 Media Worker Cycle Results")
        logger.info("=" * 70)
        
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        for task, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            logger.info(f"   {task.replace('_', ' ').title():<20} {status}")
        
        logger.info(f"\n📈 Overall: {success_count}/{total_count} tasks completed successfully")
        logger.info(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Update health status
        health_status['cycles_completed'] += 1
        health_status['last_error'] = None
        
        if success_count == total_count:
            logger.info("🎉 All media tasks completed successfully!")
            health_status['status'] = 'healthy'
            return True
        elif success_count > 0:
            logger.info("⚠️  Some tasks completed - check logs for issues")
            health_status['status'] = 'degraded'
            return True
        else:
            logger.info("❌ All tasks failed - check configuration")
            health_status['status'] = 'unhealthy'
            return False
            
    except Exception as e:
        logger.error(f"❌ Media cycle failed: {e}")
        health_status['status'] = 'unhealthy'
        health_status['last_error'] = str(e)
        return False


def continuous_mode():
    """وضع التشغيل المستمر للإنتاج"""
    logger.info("🔄 Starting Media Worker Production Mode")
    logger.info("   Processing: Images, Reels & Publishing")
    logger.info("   Batch Size: 1 report per cycle")
    logger.info("   Cycle Interval: 2 minutes")
    
    cycle_count = 0
    consecutive_failures = 0
    max_consecutive_failures = 5
    
    try:
        while True:
            cycle_count += 1
            logger.info(f"\n{'='*50}")
            logger.info(f"🎯 Media Worker Cycle #{cycle_count}")
            logger.info(f"{'='*50}")
            
            # تشغيل دورة الميديا
            success = run_media_cycle()
            
            if success:
                logger.info(f"✅ Cycle #{cycle_count} completed successfully")
                consecutive_failures = 0  # Reset failure counter
            else:
                consecutive_failures += 1
                logger.warning(f"⚠️  Cycle #{cycle_count} completed with issues (failures: {consecutive_failures})")
                
                # إذا فشل عدة مرات متتالية، زيد وقت الانتظار
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(f"❌ Too many consecutive failures ({consecutive_failures})")
                    logger.info("💤 Extended wait time due to repeated failures...")
                    time.sleep(600)  # انتظار 10 دقائق
                    consecutive_failures = 0  # Reset counter
            
            # انتظار حسب متغير البيئة أو 2 دقيقة افتراضياً
            wait_time = int(os.getenv('CYCLE_INTERVAL', 120))
            logger.info(f"💤 Waiting {wait_time}s until next cycle...")
            time.sleep(wait_time)
            
    except KeyboardInterrupt:
        logger.info(f"\n🛑 Media Worker stopped by user after {cycle_count} cycles")
    except Exception as e:
        logger.error(f"❌ Media Worker crashed: {e}")
        import traceback
        traceback.print_exc()
        
        # في حالة crash، انتظر قبل إعادة المحاولة
        logger.info("🔄 Restarting in 60 seconds...")
        time.sleep(60)
        
        # إعادة تشغيل تلقائي
        logger.info("🚀 Attempting automatic restart...")
        continuous_mode()


def test_single_report(report_id: int):
    """اختبار تقرير واحد فقط"""
    logger.info(f"🎯 Testing Single Report: {report_id}")
    
    results = {}
    
    # اختبار الصور
    try:
        from app.services.generators.social_media_image_generator import SocialImageGenerator
        generator = SocialImageGenerator()
        result = generator.generate_all(report_id)
        
        if result['success']:
            saved = generator._save_to_generated_content(report_id, result['images'], False)
            results['images'] = f"✅ Generated {len(result['images'])} images, {saved}"
        else:
            results['images'] = f"❌ Failed: {result.get('error')}"
        
        generator.close()
        
    except Exception as e:
        results['images'] = f"❌ Error: {e}"
    
    # اختبار الريلز
    try:
        from app.services.generators.reel_generator import ReelGenerator
        generator = ReelGenerator()
        result = generator.generate_for_report(report_id, force_update=False)
        
        if result.success:
            results['reel'] = f"✅ Generated reel: {result.reel_url}"
        else:
            results['reel'] = f"❌ Failed: {result.error_message}"
        
        generator.close()
        
    except Exception as e:
        results['reel'] = f"❌ Error: {e}"
    
    # عرض النتائج
    logger.info(f"📊 Results for Report #{report_id}:")
    for task, result in results.items():
        logger.info(f"   {task.title()}: {result}")


def main():
    """Main function"""
    import argparse
    
    # Start health server in background for production
    if os.getenv('WORKER_TYPE') == 'media':
        health_thread = Thread(target=start_health_server, daemon=True)
        health_thread.start()
        logger.info("🏥 Health check server started in background")
    
    parser = argparse.ArgumentParser(
        description='Media Worker - Images, Reels & Publishing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run single cycle
  python test_media_worker.py
  
  # Run continuous mode (production)
  python test_media_worker.py --continuous
  
  # Test specific report
  python test_media_worker.py --report-id 123
  
  # Test only images
  python test_media_worker.py --images-only
  
  # Test only reels
  python test_media_worker.py --reels-only
        """
    )
    
    parser.add_argument(
        '--continuous', '-c',
        action='store_true',
        help='Run in continuous mode (every 2 minutes)'
    )
    
    parser.add_argument(
        '--report-id', '-r',
        type=int,
        help='Test specific report ID'
    )
    
    parser.add_argument(
        '--images-only',
        action='store_true',
        help='Test only social media images'
    )
    
    parser.add_argument(
        '--reels-only',
        action='store_true',
        help='Test only reel generation'
    )
    
    parser.add_argument(
        '--publishing-only',
        action='store_true',
        help='Test only publishing'
    )
    
    args = parser.parse_args()
    
    # تشغيل حسب الخيارات
    if args.report_id:
        test_single_report(args.report_id)
    elif args.images_only:
        test_social_media_images()
    elif args.reels_only:
        test_reel_generation()
    elif args.publishing_only:
        test_publishing()
    elif args.continuous:
        continuous_mode()
    else:
        # تشغيل دورة واحدة
        run_media_cycle()


if __name__ == "__main__":
    main()