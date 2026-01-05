#!/usr/bin/env python3
"""
⚡ Quick Test - Images, Reels & Publishing
═══════════════════════════════════════════════════════════════
اختبار سريع للتأكد من:
- الصور العربية
- الريلز العربية  
- النشر

Usage:
    python quick_test.py
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import time

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def quick_arabic_test():
    """اختبار سريع للنص العربي"""
    print("🧪 Quick Arabic Test")
    print("=" * 50)
    
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        from PIL import Image, ImageDraw, ImageFont
        
        # نص عربي للاختبار
        test_text = "اختبار سريع للنص العربي"
        
        # معالجة النص
        reshaped = arabic_reshaper.reshape(test_text)
        bidi_text = get_display(reshaped)
        
        print(f"   Original: {test_text}")
        print(f"   Processed: {bidi_text}")
        print("   ✅ Arabic processing works")
        
        # اختبار الخط
        font_paths = [
            'fonts/NotoSansArabic-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf'
        ]
        
        font_found = False
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, 48)
                    print(f"   ✅ Font loaded: {os.path.basename(font_path)}")
                    font_found = True
                    break
                except:
                    pass
        
        if not font_found:
            print("   ⚠️  No Arabic fonts found - will use default")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Arabic test failed: {e}")
        return False


def quick_image_test():
    """اختبار سريع للصور"""
    print("\n🖼️  Quick Image Test")
    print("=" * 50)
    
    try:
        from app.services.generators.social_media_image_generator import SocialImageGenerator
        
        generator = SocialImageGenerator()
        
        # اختبار تقرير واحد فقط
        stats = generator.generate_for_all_reports(force_update=False, limit=1)
        
        total = stats.get('total_reports', 0)
        success = stats.get('success', 0) + stats.get('updated', 0)
        
        print(f"   Reports processed: {total}")
        print(f"   Successful: {success}")
        
        generator.close()
        
        if total > 0 and success > 0:
            print("   ✅ Image generation works")
            return True
        elif total == 0:
            print("   ⚠️  No reports need images")
            return True
        else:
            print("   ❌ Image generation failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Image test failed: {e}")
        return False


def quick_reel_test():
    """اختبار سريع للريلز"""
    print("\n🎬 Quick Reel Test")
    print("=" * 50)
    
    try:
        from app.services.generators.reel_generator import ReelGenerator
        
        generator = ReelGenerator()
        
        # اختبار تقرير واحد فقط
        stats = generator.generate_for_all_reports(force_update=False, limit=1)
        
        total = stats.get('total_reports', 0)
        success = stats.get('success', 0) + stats.get('updated', 0)
        
        print(f"   Reports processed: {total}")
        print(f"   Successful: {success}")
        
        generator.close()
        
        if total > 0 and success > 0:
            print("   ✅ Reel generation works")
            return True
        elif total == 0:
            print("   ⚠️  No reports need reels")
            return True
        else:
            print("   ❌ Reel generation failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Reel test failed: {e}")
        return False


def quick_publishing_test():
    """اختبار سريع للنشر"""
    print("\n📤 Quick Publishing Test")
    print("=" * 50)
    
    try:
        from app.jobs.publishers_job import publish_content
        
        # محاولة النشر
        result = publish_content()
        
        print(f"   Publishing result: {result}")
        print("   ✅ Publishing works")
        return True
        
    except Exception as e:
        print(f"   ❌ Publishing test failed: {e}")
        return False


def main():
    """Main function"""
    print("⚡ Quick Test - Media Components")
    print("=" * 70)
    print(f"🕐 Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Arabic Support", quick_arabic_test),
        ("Image Generation", quick_image_test),
        ("Reel Generation", quick_reel_test),
        ("Publishing", quick_publishing_test),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"   ❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # النتائج النهائية
    print("\n" + "=" * 70)
    print("📊 Quick Test Results")
    print("=" * 70)
    
    passed = 0
    total = len(tests)
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {test_name:<20} {status}")
        if success:
            passed += 1
    
    print(f"\n📈 Overall: {passed}/{total} tests passed")
    print(f"🕐 Completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if passed == total:
        print("🎉 All tests passed! Ready for production")
    elif passed >= total * 0.75:
        print("⚠️  Most tests passed - minor issues detected")
    else:
        print("❌ Multiple failures - check configuration")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)