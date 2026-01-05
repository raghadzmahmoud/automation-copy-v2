#!/usr/bin/env python3
"""
🧪 Test Render Deployment Compatibility
═══════════════════════════════════════════════════════════════
اختبار التوافق مع بيئة Render

Usage:
    python test_render_compatibility.py
═══════════════════════════════════════════════════════════════
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_environment():
    """اختبار البيئة والمكتبات"""
    print("🌍 Testing Render Environment Compatibility...")
    
    # اختبار Python version
    print(f"   Python version: {sys.version}")
    
    # اختبار المكتبات الأساسية
    required_modules = [
        'PIL', 'psycopg2', 'requests', 'boto3', 
        'arabic_reshaper', 'bidi', 'moviepy'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
            print(f"   ✅ {module} available")
        except ImportError:
            print(f"   ❌ {module} missing")
            missing_modules.append(module)
    
    if missing_modules:
        print(f"   ⚠️  Missing modules: {missing_modules}")
        return False
    
    return True


def test_arabic_libraries():
    """اختبار مكتبات النص العربي"""
    print("\n📚 Testing Arabic Text Libraries...")
    
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        
        # اختبار نص عربي
        test_text = "هذا نص عربي للاختبار على Render"
        
        reshaped = arabic_reshaper.reshape(test_text)
        bidi_text = get_display(reshaped)
        
        print(f"   Original: {test_text}")
        print(f"   Processed: {bidi_text}")
        print(f"   ✅ Arabic text processing works on Render")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Arabic text processing failed: {e}")
        return False


def test_font_availability():
    """اختبار توفر الخطوط العربية"""
    print("\n🔤 Testing Font Availability on Render...")
    
    try:
        from PIL import ImageFont
        import os
        
        # قائمة الخطوط المتوقعة على Render
        render_font_paths = [
            # الخط المحلي
            'fonts/NotoSansArabic-Regular.ttf',
            './fonts/NotoSansArabic-Regular.ttf',
            
            # خطوط النظام (Ubuntu/Debian على Render)
            '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/ubuntu/Ubuntu-Regular.ttf',
        ]
        
        fonts_found = []
        for font_path in render_font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, 48)
                    fonts_found.append(font_path)
                    print(f"   ✅ Font available: {os.path.basename(font_path)}")
                except Exception as e:
                    print(f"   ⚠️  Font exists but failed to load {font_path}: {e}")
            else:
                print(f"   ❌ Font not found: {font_path}")
        
        if fonts_found:
            print(f"   ✅ {len(fonts_found)} fonts available on Render")
            return True
        else:
            print(f"   ⚠️  No fonts found - will attempt download fallback")
            return test_font_download()
            
    except Exception as e:
        print(f"   ❌ Font testing failed: {e}")
        return False


def test_font_download():
    """اختبار تحميل الخط من الإنترنت"""
    print("\n🌐 Testing Font Download Fallback...")
    
    try:
        import requests
        import tempfile
        from PIL import ImageFont
        
        font_url = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansArabic/NotoSansArabic-Regular.ttf"
        
        print(f"   📥 Downloading font from Google Fonts...")
        response = requests.get(font_url, timeout=30)
        response.raise_for_status()
        
        temp_font_path = tempfile.mktemp(suffix='.ttf')
        with open(temp_font_path, 'wb') as f:
            f.write(response.content)
        
        font = ImageFont.truetype(temp_font_path, 48)
        print(f"   ✅ Font download and loading successful")
        
        # تنظيف
        os.remove(temp_font_path)
        return True
        
    except Exception as e:
        print(f"   ❌ Font download failed: {e}")
        return False


def test_image_generation():
    """اختبار توليد الصور مع النص العربي"""
    print("\n🖼️  Testing Image Generation with Arabic Text...")
    
    try:
        from PIL import Image, ImageDraw, ImageFont
        import arabic_reshaper
        from bidi.algorithm import get_display
        import tempfile
        
        # إنشاء صورة اختبار
        img = Image.new('RGB', (800, 400), color='white')
        draw = ImageDraw.Draw(img)
        
        # نص عربي للاختبار
        test_text = "اختبار النص العربي على Render"
        
        # معالجة النص العربي
        reshaped = arabic_reshaper.reshape(test_text)
        bidi_text = get_display(reshaped)
        
        # محاولة تحميل خط
        font = None
        try:
            # محاولة الخط المحلي أولاً
            if os.path.exists('fonts/NotoSansArabic-Regular.ttf'):
                font = ImageFont.truetype('fonts/NotoSansArabic-Regular.ttf', 36)
            elif os.path.exists('/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf'):
                font = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf', 36)
            else:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        # رسم النص
        draw.text((50, 150), bidi_text, fill='black', font=font)
        
        # حفظ الصورة في ملف مؤقت
        temp_img_path = tempfile.mktemp(suffix='.png')
        img.save(temp_img_path)
        
        # التحقق من حجم الملف
        file_size = os.path.getsize(temp_img_path)
        print(f"   ✅ Image generated successfully ({file_size:,} bytes)")
        
        # تنظيف
        os.remove(temp_img_path)
        return True
        
    except Exception as e:
        print(f"   ❌ Image generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_connection():
    """اختبار الاتصال بقاعدة البيانات"""
    print("\n🗄️  Testing Database Connection...")
    
    try:
        from settings import DB_CONFIG
        import psycopg2
        
        # محاولة الاتصال
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_client_encoding('UTF8')
        
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        
        print(f"   ✅ Database connected: {version[:50]}...")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")
        return False


def test_s3_connection():
    """اختبار الاتصال بـ S3"""
    print("\n☁️  Testing S3 Connection...")
    
    try:
        import boto3
        import os
        
        s3_client = boto3.client('s3')
        bucket_name = os.getenv('S3_BUCKET_NAME', 'media-automation-bucket')
        
        # محاولة list objects (لا يحتاج permissions كثيرة)
        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
            print(f"   ✅ S3 connection successful to bucket: {bucket_name}")
            return True
        except Exception as e:
            print(f"   ⚠️  S3 connection issue: {e}")
            return False
            
    except Exception as e:
        print(f"   ❌ S3 setup failed: {e}")
        return False


def main():
    """Main function"""
    print("=" * 70)
    print("🧪 Render Deployment Compatibility Test")
    print("=" * 70)
    
    tests = [
        ("Environment", test_environment),
        ("Arabic Libraries", test_arabic_libraries),
        ("Font Availability", test_font_availability),
        ("Image Generation", test_image_generation),
        ("Database Connection", test_database_connection),
        ("S3 Connection", test_s3_connection),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"   ❌ {test_name} test crashed: {e}")
            results[test_name] = False
    
    # النتائج النهائية
    print("\n" + "=" * 70)
    print("📊 Test Results Summary:")
    print("=" * 70)
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name:<20} {status}")
        if result:
            passed += 1
    
    print(f"\n📈 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Ready for Render deployment")
    elif passed >= total * 0.8:
        print("⚠️  Most tests passed - deployment should work with minor issues")
    else:
        print("❌ Multiple failures - review configuration before deploying")
    
    print("=" * 70)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)