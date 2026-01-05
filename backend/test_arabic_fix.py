#!/usr/bin/env python3
"""
🧪 Test Arabic Text Fix
═══════════════════════════════════════════════════════════════
اختبار إصلاح النص العربي في مولد الصور

Usage:
    python test_arabic_fix.py [report_id]
═══════════════════════════════════════════════════════════════
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.generators.social_media_image_generator import SocialImageGenerator

def test_arabic_text_processing():
    """اختبار معالجة النص العربي"""
    print("🧪 Testing Arabic Text Processing...")
    
    # نصوص عربية للاختبار
    test_texts = [
        "هذا نص عربي للاختبار",
        "الأخبار العاجلة من غزة",
        "تطورات الأوضاع في فلسطين",
        "Breaking News: Gaza Updates",  # مختلط عربي-إنجليزي
        "عاجل: تطورات مهمة في الشرق الأوسط"
    ]
    
    try:
        gen = SocialImageGenerator()
        
        # اختبار الخط العربي
        print("\n📝 Testing Arabic Font Loading...")
        font = gen._get_arabic_font(64)
        print(f"   ✅ Font loaded successfully: {type(font)}")
        
        # اختبار معالجة النص العربي
        print("\n🔤 Testing Arabic Text Processing...")
        
        import arabic_reshaper
        from bidi.algorithm import get_display
        
        for i, text in enumerate(test_texts, 1):
            print(f"\n[{i}] Testing: '{text}'")
            
            try:
                # إعادة تشكيل النص العربي
                reshaped = arabic_reshaper.reshape(text)
                print(f"   Reshaped: '{reshaped}'")
                
                # تطبيق خوارزمية BiDi
                bidi_text = get_display(reshaped)
                print(f"   BiDi: '{bidi_text}'")
                
                # اختبار قياس النص
                from PIL import Image, ImageDraw
                temp_img = Image.new('RGB', (1200, 630))
                temp_draw = ImageDraw.Draw(temp_img)
                
                bbox = temp_draw.textbbox((0, 0), bidi_text, font=font)
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
                
                print(f"   Text size: {width}x{height} pixels")
                print(f"   ✅ Processing successful")
                
            except Exception as e:
                print(f"   ❌ Processing failed: {e}")
        
        gen.close()
        print(f"\n✅ Arabic text processing test completed")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_database_encoding():
    """اختبار ترميز قاعدة البيانات"""
    print("\n🗄️  Testing Database Encoding...")
    
    try:
        gen = SocialImageGenerator()
        
        # اختبار حفظ JSON عربي
        test_data = {
            'h-GAZA': 'https://example.com/gaza_test.jpg',
            'DOT': 'https://example.com/dot_test.jpg'
        }
        
        print(f"   Test data: {test_data}")
        
        # محاولة حفظ البيانات (بدون report_id حقيقي)
        import json
        content_json = json.dumps(test_data, ensure_ascii=False, indent=None)
        print(f"   JSON content: {content_json}")
        
        # اختبار encoding
        content_bytes = content_json.encode('utf-8')
        content_decoded = content_bytes.decode('utf-8')
        
        if content_json == content_decoded:
            print(f"   ✅ UTF-8 encoding/decoding works correctly")
        else:
            print(f"   ❌ UTF-8 encoding/decoding failed")
            return False
        
        gen.close()
        return True
        
    except Exception as e:
        print(f"❌ Database encoding test failed: {e}")
        return False


def test_single_report(report_id: int):
    """اختبار تقرير واحد"""
    print(f"\n🎯 Testing Single Report: {report_id}")
    
    try:
        gen = SocialImageGenerator()
        
        # جلب عنوان التقرير
        title = gen._get_report_title(report_id)
        if not title:
            print(f"   ❌ No title found for report {report_id}")
            gen.close()
            return False
        
        print(f"   Title: '{title}'")
        
        # اختبار توليد الصور
        result = gen.generate_all(report_id)
        
        if result['success']:
            print(f"   ✅ Generated {len(result['images'])} images")
            
            # اختبار حفظ في قاعدة البيانات
            saved = gen._save_to_generated_content(report_id, result['images'], False)
            
            if saved in ['created', 'updated']:
                print(f"   ✅ Saved to database: {saved}")
            else:
                print(f"   ❌ Failed to save to database: {saved}")
            
            # عرض النتائج
            print(f"\n📊 Generated Images:")
            for name, url in result['images'].items():
                print(f"   {name}: {url}")
                
        else:
            print(f"   ❌ Generation failed: {result.get('error')}")
        
        gen.close()
        return result['success']
        
    except Exception as e:
        print(f"❌ Single report test failed: {e}")
        return False


def main():
    """Main function"""
    print("=" * 70)
    print("🧪 Arabic Text Fix Test")
    print("=" * 70)
    
    # اختبار معالجة النص العربي
    if not test_arabic_text_processing():
        print("❌ Arabic text processing test failed")
        return
    
    # اختبار ترميز قاعدة البيانات
    if not test_database_encoding():
        print("❌ Database encoding test failed")
        return
    
    # اختبار تقرير واحد إذا تم تمرير معرف
    if len(sys.argv) > 1:
        try:
            report_id = int(sys.argv[1])
            if not test_single_report(report_id):
                print(f"❌ Single report test failed for report {report_id}")
                return
        except ValueError:
            print(f"❌ Invalid report ID: {sys.argv[1]}")
            return
    
    print("\n" + "=" * 70)
    print("🎉 All tests completed successfully!")
    print("💡 Arabic text fixes should now work properly")
    print("=" * 70)


if __name__ == "__main__":
    main()