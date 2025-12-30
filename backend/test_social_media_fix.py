#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 Test Script for Social Media Fix
اختبار تعديلات توليد محتوى السوشيال ميديا
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re


# ============================================
# 1️⃣ NEW PARSER - يستخرج 3 منشورات من رد واحد
# ============================================

class ImprovedSocialMediaParser:
    """محلل محسّن - يستخرج Facebook, Twitter, Instagram من رد واحد"""
    
    @staticmethod
    def parse_multi_platform(text: str) -> dict:
        """
        استخراج محتوى 3 منصات من نص واحد
        Returns: {'facebook': {...}, 'twitter': {...}, 'instagram': {...}}
        """
        result = {}
        
        # البحث عن كل منصة
        platforms = ['facebook', 'twitter', 'instagram']
        
        for platform in platforms:
            # Pattern: [FACEBOOK] العنوان: ... المحتوى: ...
            pattern = rf'\[{platform.upper()}\](.*?)(?=\[(?:FACEBOOK|TWITTER|INSTAGRAM)\]|$)'
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            
            if match:
                section = match.group(1).strip()
                content_obj = ImprovedSocialMediaParser._extract_title_content(section, platform)
                if content_obj:
                    result[platform] = content_obj
        
        return result if len(result) == 3 else None
    
    @staticmethod
    def _extract_title_content(section: str, platform: str) -> dict:
        """استخراج العنوان والمحتوى من قسم واحد"""
        
        # البحث عن العنوان
        title_patterns = [
            r'العنوان[:\s]+(.+?)(?=المحتوى|$)',
            r'Title[:\s]+(.+?)(?=Content|المحتوى|$)',
            r'\*\*العنوان\*\*[:\s]+(.+?)(?=\*\*المحتوى|المحتوى|$)',
        ]
        
        title = None
        for pattern in title_patterns:
            match = re.search(pattern, section, re.DOTALL | re.IGNORECASE)
            if match:
                title = ImprovedSocialMediaParser._clean_text(match.group(1))
                if title and len(title) > 5:
                    break
        
        if not title:
            # Fallback: أول سطر
            lines = [l.strip() for l in section.split('\n') if l.strip()]
            if lines:
                title = ImprovedSocialMediaParser._clean_text(lines[0])
        
        # البحث عن المحتوى
        content_patterns = [
            r'المحتوى[:\s]+(.+)',
            r'Content[:\s]+(.+)',
            r'\*\*المحتوى\*\*[:\s]+(.+)',
        ]
        
        content = None
        for pattern in content_patterns:
            match = re.search(pattern, section, re.DOTALL | re.IGNORECASE)
            if match:
                content = ImprovedSocialMediaParser._clean_text(match.group(1))
                if content and len(content) > 50:
                    break
        
        if not content:
            # Fallback: كل شيء بعد العنوان
            lines = [l.strip() for l in section.split('\n') if l.strip()]
            if len(lines) > 1:
                content = '\n'.join(lines[1:])
                content = ImprovedSocialMediaParser._clean_text(content)
        
        if title and content:
            return {
                'title': title,
                'content': content
            }
        
        return None
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """تنظيف النص"""
        if not text:
            return ""
        
        # إزالة markdown
        text = re.sub(r'\*\*|\*|__|_|```|`', '', text)
        
        # إزالة HTML
        text = re.sub(r'<[^>]+>', '', text)
        
        # إزالة JSON artifacts
        text = re.sub(r'[{}\[\]]', '', text)
        
        # تنظيف المسافات
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        
        return text.strip()


# ============================================
# 2️⃣ IMPROVED PROMPT - يطلب 3 منشورات بوضوح
# ============================================

def create_improved_prompt(report_title: str, report_content: str) -> str:
    """برومبت محسّن - يطلب 3 منشورات بصيغة واضحة"""
    
    return f"""أنت كاتب محتوى محترف لوسائل التواصل الاجتماعي.

📰 التقرير:
العنوان: {report_title}
المحتوى: {report_content[:1000]}...

═══════════════════════════════════════
المطلوب: اكتب 3 منشورات منفصلة
═══════════════════════════════════════

**قواعد مهمة:**
- كل منشور له عنوان + محتوى
- استخدم emojis مناسبة (2-3 فقط)
- أضف هاشتاقات في النهاية
- **مهم:** ضع "_" بين كل كلمة في الهشتاق (مثال: #فلسطين_المحتلة)

═══════════════════════════════════════
الشكل المطلوب بالضبط:
═══════════════════════════════════════

[FACEBOOK]
العنوان: عنوان جذاب (5-10 كلمات)
المحتوى: 
منشور Facebook هنا (400-600 حرف)
- أسلوب جذاب ومشوّق
- 3 هاشتاقات

[TWITTER]
العنوان: عنوان قصير (5-8 كلمات)
المحتوى:
منشور Twitter هنا (250-350 حرف)
- أسلوب مختصر وقوي
- 2 هاشتاقات

[INSTAGRAM]
العنوان: عنوان ملهم (5-10 كلمات)
المحتوى:
منشور Instagram هنا (350-500 حرف)
- أسلوب بصري وملهم
- 5 هاشتاقات

═══════════════════════════════════════
الآن اكتب المنشورات الثلاثة:
"""


# ============================================
# 3️⃣ TEST CASES
# ============================================

def test_parser_with_sample_response():
    """اختبار الـ Parser مع رد نموذجي"""
    
    print("\n" + "="*70)
    print("🧪 TEST 1: Parser with Sample Response")
    print("="*70)
    
    # رد نموذجي من Gemini
    sample_response = """
[FACEBOOK]
العنوان: غارات إسرائيلية على غزة توقع عشرات الشهداء
المحتوى:
🔴 عاجل من غزة

شنت قوات الاحتلال سلسلة من الغارات العنيفة على مناطق متفرقة من قطاع غزة، أسفرت عن استشهاد عشرات المواطنين.

المقاومة تواصل التصدي بكل قوة والشعب الفلسطيني صامد رغم المعاناة.

#فلسطين_المحتلة #غزة_تحت_القصف #المقاومة_الفلسطينية

[TWITTER]
العنوان: غزة تحت النار
المحتوى:
🚨 عاجل: غارات إسرائيلية عنيفة على غزة تسفر عن عشرات الشهداء. المقاومة ترد بقوة والشعب صامد.

#غزة_تقاوم #فلسطين

[INSTAGRAM]
العنوان: صمود غزة المستمر
المحتوى:
💔 في قطاع غزة، يواصل الشعب الفلسطيني صموده رغم الغارات المتواصلة.

📍 قصف عنيف على مناطق سكنية
👥 عشرات الشهداء والجرحى
✊ المقاومة تواصل الدفاع عن الأرض

#فلسطين_الحرة #غزة_العزة #صمود_غزة #المقاومة_الفلسطينية #فلسطين_تنتصر
"""
    
    parser = ImprovedSocialMediaParser()
    result = parser.parse_multi_platform(sample_response)
    
    if result and len(result) == 3:
        print("✅ Parser extracted 3 platforms successfully!")
        print("\n📱 Extracted Content:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return True
    else:
        print("❌ Parser failed!")
        print(f"   Result: {result}")
        return False


def test_json_storage_format():
    """اختبار التنسيق النهائي للتخزين"""
    
    print("\n" + "="*70)
    print("🧪 TEST 2: JSON Storage Format")
    print("="*70)
    
    # محتوى نموذجي
    test_content = {
        'facebook': {
            'title': 'غارات إسرائيلية على غزة',
            'content': '🔴 عاجل من غزة...\n\n#فلسطين_المحتلة #غزة'
        },
        'twitter': {
            'title': 'غزة تحت النار',
            'content': '🚨 عاجل...\n\n#غزة #فلسطين'
        },
        'instagram': {
            'title': 'صمود غزة',
            'content': '💔 في قطاع غزة...\n\n#فلسطين #غزة'
        }
    }
    
    # تحويل لـ JSON (هذا هو اللي يتخزن بالـ DB)
    json_string = json.dumps(test_content, ensure_ascii=False, indent=2)
    
    print("💾 JSON to be stored in DB:")
    print(json_string)
    
    # محاكاة القراءة من DB
    print("\n📖 Reading from DB:")
    retrieved = json.loads(json_string)
    
    print("\n✅ Frontend can access:")
    print(f"   Facebook: {retrieved['facebook']['title']}")
    print(f"   Twitter:  {retrieved['twitter']['title']}")
    print(f"   Instagram: {retrieved['instagram']['title']}")
    
    return True


def test_validation():
    """اختبار التحقق من الصحة"""
    
    print("\n" + "="*70)
    print("🧪 TEST 3: Content Validation")
    print("="*70)
    
    test_cases = [
        {
            'platform': 'facebook',
            'title': 'عنوان قصير جداً',
            'content': 'محتوى قصير',
            'should_pass': False
        },
        {
            'platform': 'facebook',
            'title': 'عنوان مناسب لفيسبوك',
            'content': 'محتوى مناسب ' * 20,  # ~240 chars
            'should_pass': True
        },
        {
            'platform': 'twitter',
            'title': 'عنوان تويتر',
            'content': 'محتوى طويل جداً للتويتر ' * 50,  # ~1200 chars
            'should_pass': False
        },
    ]
    
    passed = 0
    failed = 0
    
    for i, case in enumerate(test_cases, 1):
        platform = case['platform']
        title = case['title']
        content = case['content']
        should_pass = case['should_pass']
        
        # Validation logic
        max_length = {'facebook': 600, 'twitter': 350, 'instagram': 500}[platform]
        is_valid = (
            len(title) >= 5 and
            len(content) >= 50 and
            len(content) <= max_length
        )
        
        if is_valid == should_pass:
            print(f"✅ Test {i}: {platform} - {'PASS' if should_pass else 'FAIL'} (expected)")
            passed += 1
        else:
            print(f"❌ Test {i}: {platform} - unexpected result")
            failed += 1
    
    print(f"\n📊 Validation: {passed} passed, {failed} failed")
    return failed == 0


def test_hashtag_format():
    """اختبار تنسيق الهاشتاقات"""
    
    print("\n" + "="*70)
    print("🧪 TEST 4: Hashtag Format Check")
    print("="*70)
    
    test_content = """
    محتوى المنشور هنا...
    
    #فلسطين_المحتلة #غزة_تحت_القصف #المقاومة_الفلسطينية
    """
    
    # استخراج الهاشتاقات
    hashtags = re.findall(r'#[\w_]+', test_content)
    
    print(f"📍 Found {len(hashtags)} hashtags:")
    
    correct = 0
    incorrect = 0
    
    for tag in hashtags:
        # فحص: لا يحتوي على spaces أو حروف مدمجة غير صحيحة
        has_underscore = '_' in tag
        has_space = ' ' in tag
        
        if has_underscore and not has_space:
            print(f"   ✅ {tag}")
            correct += 1
        else:
            print(f"   ❌ {tag} - invalid format")
            incorrect += 1
    
    print(f"\n📊 Hashtags: {correct} correct, {incorrect} incorrect")
    return incorrect == 0


# ============================================
# 4️⃣ FULL INTEGRATION TEST
# ============================================

def test_full_workflow():
    """اختبار كامل للـ workflow"""
    
    print("\n" + "="*70)
    print("🧪 TEST 5: Full Workflow Simulation")
    print("="*70)
    
    # 1. إنشاء البرومبت
    report_title = "غارات إسرائيلية على غزة"
    report_content = "شنت قوات الاحتلال..."
    
    prompt = create_improved_prompt(report_title, report_content)
    print("✅ Step 1: Prompt created")
    print(f"   Length: {len(prompt)} chars")
    
    # 2. محاكاة رد Gemini
    gemini_response = """
[FACEBOOK]
العنوان: غارات إسرائيلية على غزة توقع عشرات الشهداء
المحتوى:
🔴 عاجل من غزة
شنت قوات الاحتلال سلسلة من الغارات...
#فلسطين_المحتلة #غزة_تحت_القصف #المقاومة

[TWITTER]
العنوان: غزة تحت النار
المحتوى:
🚨 عاجل: غارات على غزة...
#غزة #فلسطين

[INSTAGRAM]
العنوان: صمود غزة
المحتوى:
💔 في قطاع غزة...
#فلسطين #غزة #صمود #المقاومة #العزة
"""
    
    print("✅ Step 2: Gemini response received (simulated)")
    
    # 3. استخراج المحتوى
    parser = ImprovedSocialMediaParser()
    extracted = parser.parse_multi_platform(gemini_response)
    
    if not extracted or len(extracted) != 3:
        print("❌ Step 3: Parsing failed!")
        return False
    
    print("✅ Step 3: Content extracted (3 platforms)")
    
    # 4. تحويل لـ JSON
    json_output = json.dumps(extracted, ensure_ascii=False, indent=2)
    print("✅ Step 4: JSON formatted")
    print(f"   Size: {len(json_output)} chars")
    
    # 5. محاكاة الحفظ والقراءة
    saved_to_db = json_output  # يتخزن في DB
    retrieved_from_db = json.loads(saved_to_db)  # يتقرأ من DB
    
    print("✅ Step 5: Saved to DB and retrieved")
    
    # 6. عرض النتيجة
    print("\n📱 Final Output:")
    for platform, data in retrieved_from_db.items():
        print(f"\n{platform.upper()}:")
        print(f"  Title: {data['title'][:40]}...")
        print(f"  Content: {data['content'][:60]}...")
    
    return True


# ============================================
# MAIN
# ============================================

def main():
    """تشغيل جميع الاختبارات"""
    
    print("="*70)
    print("🧪 SOCIAL MEDIA GENERATOR - FIX TESTS")
    print("="*70)
    
    results = []
    
    # Test 1: Parser
    results.append(("Parser", test_parser_with_sample_response()))
    
    # Test 2: JSON Format
    results.append(("JSON Format", test_json_storage_format()))
    
    # Test 3: Validation
    results.append(("Validation", test_validation()))
    
    # Test 4: Hashtags
    results.append(("Hashtags", test_hashtag_format()))
    
    # Test 5: Full Workflow
    results.append(("Full Workflow", test_full_workflow()))
    
    # Summary
    print("\n" + "="*70)
    print("📊 FINAL SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    print("\n" + "="*70)
    print(f"Results: {passed}/{total} passed")
    print("="*70)
    
    if passed == total:
        print("\n🎉 All tests passed!")
        print("\n📝 Next Steps:")
        print("   1. نسخ الكود الجديد لـ social_media_generator.py")
        print("   2. اختبار مع تقرير حقيقي")
        print("   3. التحقق من DB output")
        return 0
    else:
        print("\n⚠️  Some tests failed. Review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())