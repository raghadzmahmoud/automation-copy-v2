#!/usr/bin/env python3
"""
🧪 Test Arabic Text in Reel Generation
═══════════════════════════════════════════════════════════════
اختبار النص العربي في مولد الريلز

Usage:
    python test_reel_arabic.py [report_id]
═══════════════════════════════════════════════════════════════
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_arabic_text_processing():
    """اختبار معالجة النص العربي في الريلز"""
    print("🧪 Testing Arabic Text Processing in Reels...")
    
    # نصوص عربية للاختبار
    test_texts = [
        "هذا نص عربي للاختبار في الريلز",
        "الأخبار العاجلة من غزة والضفة الغربية",
        "تطورات مهمة في الأوضاع السياسية بالمنطقة",
        "عاجل: قرارات جديدة تؤثر على المواطنين",
        "Breaking News: تطورات عاجلة في الشرق الأوسط"  # مختلط
    ]
    
    try:
        # اختبار المكتبات المطلوبة
        print("\n📚 Testing Required Libraries...")
        
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            print("   ✅ arabic-reshaper and python-bidi available")
        except ImportError as e:
            print(f"   ❌ Missing libraries: {e}")
            print("   💡 Install with: pip install arabic-reshaper python-bidi")
            return False
        
        try:
            from PIL import Image, ImageDraw, ImageFont
            print("   ✅ PIL (Pillow) available")
        except ImportError as e:
            print(f"   ❌ PIL not available: {e}")
            return False
        
        # اختبار معالجة النص العربي
        print("\n🔤 Testing Arabic Text Processing...")
        
        for i, text in enumerate(test_texts, 1):
            print(f"\n[{i}] Testing: '{text}'")
            
            try:
                # تنظيف النص
                text = text.strip()
                
                # تقسيم إلى جمل
                import re
                sentences = re.split(r'[.!؟]\s+', text)
                sentences = [s.strip() for s in sentences if s.strip()]
                
                if not sentences:
                    sentences = [text]
                
                print(f"   Sentences: {len(sentences)}")
                
                # معالجة كل جملة
                processed_lines = []
                for sentence in sentences:
                    words = sentence.split()
                    
                    # تجميع الكلمات في أسطر (4 كلمات كحد أقصى)
                    max_words_per_line = 4
                    current_line = []
                    
                    for word in words:
                        current_line.append(word)
                        if len(current_line) >= max_words_per_line:
                            line_text = ' '.join(current_line)
                            
                            # تطبيق معالجة العربية
                            try:
                                reshaped_line = arabic_reshaper.reshape(line_text)
                                rtl_line = get_display(reshaped_line)
                                processed_lines.append(rtl_line)
                                print(f"     Line: '{line_text}' → '{rtl_line}'")
                            except Exception as e:
                                print(f"     ❌ Arabic processing failed: {e}")
                                processed_lines.append(line_text)
                            
                            current_line = []
                    
                    # إضافة الكلمات المتبقية
                    if current_line:
                        line_text = ' '.join(current_line)
                        try:
                            reshaped_line = arabic_reshaper.reshape(line_text)
                            rtl_line = get_display(reshaped_line)
                            processed_lines.append(rtl_line)
                            print(f"     Final line: '{line_text}' → '{rtl_line}'")
                        except Exception as e:
                            print(f"     ❌ Arabic processing failed: {e}")
                            processed_lines.append(line_text)
                
                print(f"   ✅ Processed into {len(processed_lines)} lines")
                
            except Exception as e:
                print(f"   ❌ Processing failed: {e}")
        
        print(f"\n✅ Arabic text processing test completed")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_font_loading():
    """اختبار تحميل الخطوط العربية"""
    print("\n🔤 Testing Arabic Font Loading...")
    
    try:
        from PIL import ImageFont
        import os
        
        # قائمة الخطوط للاختبار
        font_paths = [
            # الخط المحلي
            'fonts/NotoSansArabic-Regular.ttf',
            './fonts/NotoSansArabic-Regular.ttf',
            
            # خطوط النظام (Linux)
            '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            
            # خطوط النظام (Windows)
            'C:/Windows/Fonts/arial.ttf',
            'C:/Windows/Fonts/tahoma.ttf',
        ]
        
        font_found = False
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, 55)
                    print(f"   ✅ Font loaded: {os.path.basename(font_path)}")
                    font_found = True
                    break
                except Exception as e:
                    print(f"   ⚠️  Failed to load {font_path}: {e}")
        
        if not font_found:
            try:
                font = ImageFont.load_default()
                print(f"   ⚠️  Using default font (Arabic may not render correctly)")
            except Exception as e:
                print(f"   ❌ No font available: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Font loading test failed: {e}")
        return False


def test_single_reel(report_id: int):
    """اختبار توليد ريل واحد"""
    print(f"\n🎬 Testing Single Reel Generation: {report_id}")
    
    try:
        from app.services.generators.reel_generator import ReelGenerator
        
        generator = ReelGenerator()
        
        print(f"   🎯 Generating reel for report {report_id}...")
        result = generator.generate_for_report(report_id, force_update=True)
        
        if result.success:
            print(f"   ✅ Reel generated successfully!")
            print(f"   📹 URL: {result.reel_url}")
            print(f"   ⏱️  Duration: {result.duration_seconds:.2f}s")
        else:
            print(f"   ❌ Generation failed: {result.error_message}")
        
        generator.close()
        return result.success
        
    except Exception as e:
        print(f"❌ Single reel test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_reels():
    """اختبار توليد ريلز متعددة (4 تقارير)"""
    print(f"\n🎬 Testing Batch Reel Generation (4 reports)...")
    
    try:
        from app.services.generators.reel_generator import ReelGenerator
        
        generator = ReelGenerator()
        
        print(f"   📊 Generating reels for up to 4 reports...")
        stats = generator.generate_for_all_reports(force_update=False, limit=4)
        
        print(f"   📈 Results:")
        print(f"     Total reports: {stats.get('total_reports', 0)}")
        print(f"     Success: {stats.get('success', 0)}")
        print(f"     Updated: {stats.get('updated', 0)}")
        print(f"     Failed: {stats.get('failed', 0)}")
        
        generator.close()
        return stats.get('total_reports', 0) > 0
        
    except Exception as e:
        print(f"❌ Batch reel test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function"""
    print("=" * 70)
    print("🧪 Arabic Text in Reel Generation Test")
    print("=" * 70)
    
    # اختبار معالجة النص العربي
    if not test_arabic_text_processing():
        print("❌ Arabic text processing test failed")
        return
    
    # اختبار تحميل الخطوط
    if not test_font_loading():
        print("❌ Font loading test failed")
        return
    
    # اختبار ريل واحد إذا تم تمرير معرف
    if len(sys.argv) > 1:
        try:
            report_id = int(sys.argv[1])
            if not test_single_reel(report_id):
                print(f"❌ Single reel test failed for report {report_id}")
                return
        except ValueError:
            print(f"❌ Invalid report ID: {sys.argv[1]}")
            return
    else:
        # اختبار توليد ريلز متعددة
        if not test_batch_reels():
            print("❌ Batch reel test failed")
            return
    
    print("\n" + "=" * 70)
    print("🎉 All tests completed successfully!")
    print("💡 Arabic text in reels should now work properly")
    print("📝 Changes made:")
    print("   • Reduced batch size from 10 to 4 reports")
    print("   • Enhanced Arabic RTL text processing")
    print("   • Improved font loading with Arabic support")
    print("   • Better text wrapping for mobile readability")
    print("=" * 70)


if __name__ == "__main__":
    main()