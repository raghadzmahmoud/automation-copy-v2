#!/usr/bin/env python3
"""
🧪 Test Arabic Text Direction
═══════════════════════════════════════════════════════════════
اختبار اتجاه النص العربي في الصور

Usage:
    python test_arabic_direction.py
═══════════════════════════════════════════════════════════════
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_arabic_processing():
    """اختبار معالجة النص العربي"""
    print("🧪 Testing Arabic Text Processing")
    print("=" * 50)
    
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        
        # نصوص للاختبار
        test_texts = [
            "فيماخم: وروديام لايحي بتوجي كريمأ بن يابرز",
            "دوديحلا نم ما حي بلك نطلطشاو تتايعادتن نم",
            "نقفاطلاو",
            "هذا نص عربي للاختبار",
            "الأخبار العاجلة من غزة"
        ]
        
        for i, text in enumerate(test_texts, 1):
            print(f"\n[{i}] Testing: '{text}'")
            
            # تحقق إذا النص يحتوي على عربي
            has_arabic = any('\u0600' <= char <= '\u06FF' for char in text)
            print(f"   Has Arabic: {has_arabic}")
            
            if has_arabic:
                try:
                    # إعادة تشكيل النص العربي
                    reshaped = arabic_reshaper.reshape(text)
                    print(f"   Reshaped: '{reshaped}'")
                    
                    # تطبيق خوارزمية BiDi
                    bidi_text = get_display(reshaped)
                    print(f"   BiDi: '{bidi_text}'")
                    
                    # مقارنة
                    if text != bidi_text:
                        print(f"   ✅ Text was processed (RTL applied)")
                    else:
                        print(f"   ⚠️  Text unchanged")
                        
                except Exception as e:
                    print(f"   ❌ Processing failed: {e}")
            else:
                print(f"   ℹ️  No Arabic characters detected")
        
        return True
        
    except ImportError as e:
        print(f"❌ Arabic libraries not available: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_image_generation():
    """اختبار توليد صورة مع نص عربي"""
    print("\n🖼️  Testing Image Generation with Arabic")
    print("=" * 50)
    
    try:
        from PIL import Image, ImageDraw, ImageFont
        import arabic_reshaper
        from bidi.algorithm import get_display
        import tempfile
        
        # نص عربي للاختبار
        test_text = "فيماخم: وروديام لايحي بتوجي كريمأ بن يابرز"
        
        print(f"Original text: {test_text}")
        
        # معالجة النص العربي
        has_arabic = any('\u0600' <= char <= '\u06FF' for char in test_text)
        
        if has_arabic:
            reshaped = arabic_reshaper.reshape(test_text)
            processed_text = get_display(reshaped)
            print(f"Processed text: {processed_text}")
        else:
            processed_text = test_text
            print(f"No Arabic processing needed")
        
        # إنشاء صورة اختبار
        img = Image.new('RGB', (800, 200), color='white')
        draw = ImageDraw.Draw(img)
        
        # محاولة تحميل خط عربي
        font = None
        font_paths = [
            'fonts/NotoSansArabic-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf'
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, 36)
                    print(f"✅ Using font: {font_path}")
                    break
                except:
                    continue
        
        if not font:
            font = ImageFont.load_default()
            print("⚠️  Using default font")
        
        # رسم النص الأصلي
        draw.text((50, 50), f"Original: {test_text}", fill='red', font=font)
        
        # رسم النص المعالج
        draw.text((50, 100), f"Processed: {processed_text}", fill='blue', font=font)
        
        # حفظ الصورة
        temp_path = tempfile.mktemp(suffix='.png')
        img.save(temp_path)
        
        print(f"✅ Test image saved: {temp_path}")
        print("   Red text: Original Arabic")
        print("   Blue text: Processed Arabic (should be RTL)")
        
        return True
        
    except Exception as e:
        print(f"❌ Image generation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function"""
    print("🧪 Arabic Text Direction Test")
    print("=" * 70)
    
    # اختبار معالجة النص
    if not test_arabic_processing():
        print("❌ Arabic processing test failed")
        return False
    
    # اختبار توليد الصورة
    if not test_image_generation():
        print("❌ Image generation test failed")
        return False
    
    print("\n" + "=" * 70)
    print("🎉 All tests completed!")
    print("💡 Check the generated image to verify Arabic text direction")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)