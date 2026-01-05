#!/usr/bin/env python3
"""
🧪 Test Image Generation Script
═══════════════════════════════════════════════════════════════
يختبر توليد الصور مع النصوص العربية

Usage:
    python test_image_generation.py
═══════════════════════════════════════════════════════════════
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_single_report():
    """اختبار توليد صورة لتقرير واحد"""
    print("🧪 Testing single report image generation...")
    
    try:
        from app.services.generators.social_media_image_generator import SocialMediaImageGenerator
        
        generator = SocialMediaImageGenerator()
        
        # اختبار مع تقرير واحد
        result = generator.generate_for_all_reports(force_update=True, limit=1)
        
        print(f"Result: {result}")
        
        if result.get('success'):
            print("✅ Image generation test passed!")
            images = result.get('images', {})
            for template, url in images.items():
                print(f"   {template}: {url}")
        else:
            print("❌ Image generation test failed")
            print(f"   Error: {result.get('error', 'Unknown error')}")
        
        generator.close()
        return result.get('success', False)
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_connection():
    """اختبار اتصال قاعدة البيانات"""
    print("🔍 Testing database connection...")
    
    try:
        import psycopg2
        from settings import DB_CONFIG
        
        # إعداد اتصال مع UTF-8
        db_config = DB_CONFIG.copy()
        db_config['options'] = '-c client_encoding=utf8 -c standard_conforming_strings=on'
        
        conn = psycopg2.connect(**db_config)
        conn.set_client_encoding('UTF8')
        
        cursor = conn.cursor()
        cursor.execute("SET client_encoding TO 'UTF8'")
        
        # اختبار استعلام بسيط
        cursor.execute("SELECT COUNT(*) FROM generated_report")
        count = cursor.fetchone()[0]
        print(f"   ✅ Found {count} reports in database")
        
        # اختبار النص العربي
        cursor.execute("SELECT title FROM generated_report ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        if result:
            title = result[0]
            print(f"   ✅ Latest report title: {title[:50]}...")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        return False


def main():
    """Main function"""
    print("=" * 70)
    print("🧪 Image Generation Test Script")
    print("=" * 70)
    
    # اختبار اتصال قاعدة البيانات
    if not test_database_connection():
        print("❌ Database connection failed - stopping tests")
        return
    
    print()
    
    # اختبار توليد الصور
    if test_single_report():
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Tests failed!")
        print("💡 Try running: python fix_encoding.py")
    
    print("=" * 70)


if __name__ == "__main__":
    main()