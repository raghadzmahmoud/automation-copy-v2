#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 Local Publishers Job Tester
═══════════════════════════════════════════════════════════════
تست محلي للـ Publishers Job

Usage:
python test_publishers_local.py                    # تست كامل (أحدث التقارير)
python test_publishers_local.py --social-only      # تست Social Media فقط
python test_publishers_local.py --telegram-only    # تست Telegram فقط
python test_publishers_local.py --dry-run          # تست بدون نشر فعلي
python test_publishers_local.py --debug            # معلومات تفصيلية
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import logging
import argparse
from datetime import datetime

# Add paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def test_full_cycle(dry_run=False):
    """تست الدورة الكاملة - أحدث التقارير"""
    
    print(f"\n{'='*70}")
    print(f"🧪 FULL PUBLISHERS CYCLE TEST")
    print(f"{'='*70}")
    print(f"Mode: {'DRY RUN (no actual publishing)' if dry_run else 'LIVE (actual publishing)'}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    try:
        from app.jobs.publishers_job import PublishersJob
        
        # Create job instance
        job = PublishersJob()
        
        if dry_run:
            # Dry run - just check what would be published
            print("🔍 DRY RUN - Checking available reports...\n")
            
            # Check Social Media reports
            print("📘 Social Media Reports Available:")
            social_reports = job.get_reports_ready_for_publishing('social_media')
            if social_reports:
                for i, (report_id, status, created_at) in enumerate(social_reports, 1):
                    print(f"   {i}. Report #{report_id} - {status} - {created_at}")
            else:
                print("   📭 No reports available")
            
            print()
            
            # Check Telegram reports
            print("📱 Telegram Reports Available:")
            telegram_reports = job.get_reports_ready_for_publishing('telegram')
            if telegram_reports:
                for i, (report_id, status, created_at) in enumerate(telegram_reports, 1):
                    print(f"   {i}. Report #{report_id} - {status} - {created_at}")
            else:
                print("   📭 No reports available")
            
            print(f"\n{'='*70}")
            print(f"📊 DRY RUN SUMMARY:")
            print(f"{'='*70}")
            print(f"Social Media reports ready: {len(social_reports)}")
            print(f"Telegram reports ready: {len(telegram_reports)}")
            print(f"Total reports would be processed: {len(social_reports) + len(telegram_reports)}")
            print(f"{'='*70}\n")
            
            return {
                'success': True,
                'dry_run': True,
                'social_media_count': len(social_reports),
                'telegram_count': len(telegram_reports)
            }
        
        else:
            # Live run - actual publishing
            print("🚀 LIVE RUN - Publishing reports...\n")
            result = job.run_publishing_cycle()
            
            print(f"\n{'='*70}")
            print(f"📊 LIVE RUN RESULTS:")
            print(f"{'='*70}")
            print(f"Success: {result['success']}")
            print(f"Reports Processed: {result.get('reports_processed', 0)}")
            print(f"Reports Published: {result.get('reports_published', 0)}")
            print(f"Duration: {result.get('duration_seconds', 0):.2f}s")
            
            if result.get('platform_stats'):
                print("\nPlatform Stats:")
                for platform, count in result['platform_stats'].items():
                    print(f"  {platform.title()}: {count}")
            
            print(f"{'='*70}\n")
            
            return result
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def test_social_media_only(dry_run=False):
    """تست Social Media فقط"""
    
    print(f"\n{'='*70}")
    print(f"📘 SOCIAL MEDIA ONLY TEST")
    print(f"{'='*70}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'='*70}\n")
    
    try:
        from app.jobs.publishers_job import PublishersJob
        
        job = PublishersJob()
        
        # Get available reports
        social_reports = job.get_reports_ready_for_publishing('social_media')
        
        if not social_reports:
            print("📭 No Social Media reports available")
            return {'success': True, 'reports_processed': 0}
        
        print(f"📊 Found {len(social_reports)} Social Media report(s):")
        for i, (report_id, status, created_at) in enumerate(social_reports, 1):
            print(f"   {i}. Report #{report_id} - {status} - {created_at}")
        
        if dry_run:
            print(f"\n🔍 DRY RUN - Would publish {len(social_reports)} report(s)")
            return {'success': True, 'dry_run': True, 'reports_found': len(social_reports)}
        
        # Live publishing
        print(f"\n🚀 Publishing {len(social_reports)} report(s)...")
        results = []
        
        for report_id, status, created_at in social_reports:
            print(f"\n📤 Publishing Report #{report_id}...")
            result = job.publish_to_social_media_only(report_id, status)
            results.append(result)
            
            if result['overall_success']:
                platforms = ', '.join(result['published_platforms'])
                print(f"   ✅ Published to: {platforms}")
            else:
                print(f"   ❌ Failed")
        
        successful = sum(1 for r in results if r['overall_success'])
        
        print(f"\n{'='*70}")
        print(f"📊 SOCIAL MEDIA TEST RESULTS:")
        print(f"{'='*70}")
        print(f"Reports Processed: {len(results)}")
        print(f"Reports Published: {successful}")
        print(f"Success Rate: {(successful/len(results)*100):.1f}%")
        print(f"{'='*70}\n")
        
        return {
            'success': True,
            'reports_processed': len(results),
            'reports_published': successful,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"❌ Social Media test failed: {e}")
        return {'success': False, 'error': str(e)}


def test_telegram_only(dry_run=False):
    """تست Telegram فقط"""
    
    print(f"\n{'='*70}")
    print(f"📱 TELEGRAM ONLY TEST")
    print(f"{'='*70}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'='*70}\n")
    
    try:
        from app.jobs.publishers_job import PublishersJob
        
        job = PublishersJob()
        
        # Get available reports
        telegram_reports = job.get_reports_ready_for_publishing('telegram')
        
        if not telegram_reports:
            print("📭 No Telegram reports available")
            return {'success': True, 'reports_processed': 0}
        
        print(f"📊 Found {len(telegram_reports)} Telegram report(s):")
        for i, (report_id, status, created_at) in enumerate(telegram_reports, 1):
            print(f"   {i}. Report #{report_id} - {status} - {created_at}")
        
        if dry_run:
            print(f"\n🔍 DRY RUN - Would publish {len(telegram_reports)} report(s)")
            return {'success': True, 'dry_run': True, 'reports_found': len(telegram_reports)}
        
        # Live publishing
        print(f"\n🚀 Publishing {len(telegram_reports)} report(s)...")
        results = []
        
        for report_id, status, created_at in telegram_reports:
            print(f"\n📤 Publishing Report #{report_id}...")
            result = job.publish_to_telegram_only(report_id, status)
            results.append(result)
            
            if result['overall_success']:
                print(f"   ✅ Published to Telegram")
            else:
                print(f"   ❌ Failed")
        
        successful = sum(1 for r in results if r['overall_success'])
        
        print(f"\n{'='*70}")
        print(f"📊 TELEGRAM TEST RESULTS:")
        print(f"{'='*70}")
        print(f"Reports Processed: {len(results)}")
        print(f"Reports Published: {successful}")
        print(f"Success Rate: {(successful/len(results)*100):.1f}%")
        print(f"{'='*70}\n")
        
        return {
            'success': True,
            'reports_processed': len(results),
            'reports_published': successful,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"❌ Telegram test failed: {e}")
        return {'success': False, 'error': str(e)}


def debug_reports():
    """عرض معلومات تفصيلية عن التقارير"""
    
    print(f"\n{'='*70}")
    print(f"🔍 DEBUG - Reports Analysis")
    print(f"{'='*70}\n")
    
    try:
        from app.jobs.publishers_job import PublishersJob
        
        job = PublishersJob()
        
        if not job.cursor:
            print("❌ Database connection failed")
            return
        
        # Total reports
        job.cursor.execute("SELECT COUNT(*) FROM generated_report")
        total = job.cursor.fetchone()[0]
        print(f"📊 Total Reports: {total}")
        
        # Reports by status
        job.cursor.execute("""
            SELECT status, COUNT(*) 
            FROM generated_report 
            GROUP BY status 
            ORDER BY COUNT(*) DESC
        """)
        statuses = job.cursor.fetchall()
        print(f"\n📊 Reports by Status:")
        for status, count in statuses:
            print(f"   {status}: {count}")
        
        # Recent reports
        job.cursor.execute("""
            SELECT id, title, status, created_at
            FROM generated_report 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        recent = job.cursor.fetchall()
        print(f"\n📊 10 Most Recent Reports:")
        for report_id, title, status, created_at in recent:
            title_short = title[:50] + "..." if len(title) > 50 else title
            print(f"   #{report_id}: {title_short} - {status} - {created_at}")
        
        # Reports with content
        job.cursor.execute("""
            SELECT COUNT(DISTINCT gr.id)
            FROM generated_report gr
            WHERE EXISTS (
                SELECT 1 FROM generated_content gc 
                WHERE gc.report_id = gr.id 
                AND gc.content_type_id = 1
                AND gc.content IS NOT NULL
            )
        """)
        with_content = job.cursor.fetchone()[0]
        print(f"\n📊 Reports with Social Media Content: {with_content}")
        
        # Reports with images
        job.cursor.execute("""
            SELECT COUNT(DISTINCT gr.id)
            FROM generated_report gr
            WHERE EXISTS (
                SELECT 1 FROM generated_content gc 
                WHERE gc.report_id = gr.id 
                AND gc.content_type_id = 2
                AND gc.file_url IS NOT NULL
            )
        """)
        with_images = job.cursor.fetchone()[0]
        print(f"📊 Reports with Generated Images: {with_images}")
        
        # Available for publishing
        social_reports = job.get_reports_ready_for_publishing('social_media')
        telegram_reports = job.get_reports_ready_for_publishing('telegram')
        
        print(f"\n📊 Ready for Publishing:")
        print(f"   Social Media: {len(social_reports)}")
        print(f"   Telegram: {len(telegram_reports)}")
        
        if social_reports:
            print(f"\n📘 Social Media Reports Ready:")
            for report_id, status, created_at in social_reports[:5]:
                print(f"   #{report_id} - {status} - {created_at}")
        
        if telegram_reports:
            print(f"\n📱 Telegram Reports Ready:")
            for report_id, status, created_at in telegram_reports[:5]:
                print(f"   #{report_id} - {status} - {created_at}")
        
        print(f"\n{'='*70}\n")
        
    except Exception as e:
        logger.error(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main function"""
    
    parser = argparse.ArgumentParser(description='Test Publishers Job locally')
    parser.add_argument('--social-only', action='store_true', help='Test Social Media only')
    parser.add_argument('--telegram-only', action='store_true', help='Test Telegram only')
    parser.add_argument('--dry-run', action='store_true', help='Dry run (no actual publishing)')
    parser.add_argument('--debug', action='store_true', help='Show debug information')
    
    args = parser.parse_args()
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Environment variables loaded")
    except ImportError:
        print("⚠️  python-dotenv not installed, using system environment")
    except Exception as e:
        print(f"⚠️  Could not load .env file: {e}")
    
    # Debug mode
    if args.debug:
        debug_reports()
        return
    
    # Test modes
    if args.social_only:
        result = test_social_media_only(dry_run=args.dry_run)
    elif args.telegram_only:
        result = test_telegram_only(dry_run=args.dry_run)
    else:
        result = test_full_cycle(dry_run=args.dry_run)
    
    # Final result
    if result['success']:
        print("✅ Test completed successfully!")
    else:
        print("❌ Test failed!")
        if 'error' in result:
            print(f"Error: {result['error']}")


if __name__ == '__main__':
    main()