#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 Test Manual Scraper
ملف تجربة للـ Manual URL Scraper
"""

import sys
import os

# إضافة المسار
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================
# 🧪 Test 1: Source Detector
# ============================================
def test_source_detector():
    """تجربة تحديد نوع المصدر"""
    print("\n" + "="*60)
    print("🧪 Test 1: Source Detector")
    print("="*60)
    
    from app.services.ingestion.source_detector import detect_source
    
    test_urls = [
        "https://www.aljazeera.net/news/2024/1/15/example",
        "https://t.me/TestChannel",
        "https://t.me/TestChannel/12345",
        "https://example.com/feed.xml",
        "www.example.com/news",
        "invalid",
    ]
    
    for url in test_urls:
        info = detect_source(url)
        status = "✅" if info.is_valid else "❌"
        print(f"\n{status} {url}")
        print(f"   Type: {info.source_type.value}")
        if info.telegram_username:
            print(f"   Telegram: @{info.telegram_username}")
        if info.error_message:
            print(f"   Error: {info.error_message}")
    
    print("\n✅ Source Detector Test Complete!")
    return True


# ============================================
# 🧪 Test 2: Web Scraper (بدون DB)
# ============================================
def test_web_scraper(url: str = None):
    """تجربة سحب محتوى صفحة"""
    print("\n" + "="*60)
    print("🧪 Test 2: Web Scraper")
    print("="*60)
    
    from app.services.ingestion.web_scraper import scrape_url
    
    test_url = url or "https://www.maannews.net/"
    print(f"\n🔗 URL: {test_url}")
    print("⏳ Scraping...")
    
    result = scrape_url(test_url)
    
    if result.success:
        print(f"\n✅ Success!")
        print(f"📰 Title: {result.title[:80]}..." if result.title else "   No title")
        print(f"📝 Content Length: {len(result.clean_text)} chars")
        print(f"🖼️ Images Found: {len(result.images)}")
        print(f"🎬 Videos Found: {len(result.videos)}")
        
        if result.clean_text:
            print(f"\n📄 First 500 chars of content:")
            print("-" * 40)
            print(result.clean_text[:500])
            print("-" * 40)
        
        if result.images:
            print(f"\n🖼️ First 3 images:")
            for i, img in enumerate(result.images[:3], 1):
                print(f"   [{i}] {img[:80]}...")
    else:
        print(f"\n❌ Failed: {result.error_message}")
    
    return result.success


# ============================================
# 🧪 Test 3: Content Extractor (يحتاج API Key)
# ============================================
def test_content_extractor():
    """تجربة استخراج الأخبار بالـ AI"""
    print("\n" + "="*60)
    print("🧪 Test 3: Content Extractor (AI)")
    print("="*60)
    
    # التحقق من API Key
    from settings import GEMINI_API_KEY, GEMINI_EXTRACTION_MODEL
    
    if not GEMINI_API_KEY:
        print("\n❌ GEMINI_API_KEY not set in .env")
        return False
    
    print(f"\n🤖 Using Model: {GEMINI_EXTRACTION_MODEL}")
    
    from app.services.ingestion.content_extractor import ContentExtractor
    
    # محتوى تجريبي
    test_content = """
    أعلنت الحكومة الفلسطينية اليوم عن خطة اقتصادية جديدة
    
    رام الله - أعلن رئيس الوزراء الفلسطيني محمد مصطفى عن خطة اقتصادية شاملة 
    تهدف إلى تحسين الوضع المعيشي للمواطنين في الضفة الغربية وقطاع غزة.
    وقال في مؤتمر صحفي إن الخطة تتضمن مشاريع تنموية وتشغيلية.
    
    ---
    
    المنتخب الفلسطيني يتأهل لكأس آسيا
    
    تأهل المنتخب الفلسطيني لكرة القدم إلى نهائيات كأس آسيا 2027 
    بعد فوزه على نظيره اللبناني بنتيجة 2-0 في التصفيات المؤهلة.
    سجل الهدفين اللاعبان محمد سالم وأحمد أبو ناهية.
    """
    
    print("\n⏳ Extracting news with AI...")
    
    extractor = ContentExtractor()
    result = extractor.extract_news(
        content=test_content,
        source_url="https://www.maannews.net/"
    )
    
    if result.success:
        print(f"\n✅ Extracted {result.total_extracted} news items!")
        
        for i, news in enumerate(result.news_items, 1):
            print(f"\n--- News #{i} ---")
            print(f"📌 Title: {news.title}")
            print(f"📁 Category: {news.category}")
            print(f"🏷️ Tags: {', '.join(news.tags[:5])}")
            print(f"📝 Content: {news.content[:100]}...")
    else:
        print(f"\n❌ Failed: {result.error_message}")
    
    return result.success


# ============================================
# 🧪 Test 4: Full Pipeline (Manual Scraper)
# ============================================
def test_full_pipeline(url: str = None, save_to_db: bool = False):
    """تجربة الـ Pipeline الكامل"""
    print("\n" + "="*60)
    print("🧪 Test 4: Full Pipeline (Manual Scraper)")
    print("="*60)
    
    from app.services.ingestion.manual_scraper import ManualScraper
    
    test_url = url or "https://www.maannews.net/"
    
    print(f"\n🔗 URL: {test_url}")
    print(f"💾 Save to DB: {save_to_db}")
    
    scraper = ManualScraper(auto_save=save_to_db)
    result = scraper.scrape_url(test_url)
    
    if result.success:
        print(f"\n" + "="*60)
        print(f"✅ SUCCESS!")
        print(f"="*60)
        print(f"📰 News Extracted: {result.news_extracted}")
        print(f"💾 News Saved: {result.news_saved}")
        print(f"⏱️ Time: {result.processing_time_seconds:.2f}s")
        
        print(f"\n📋 Extracted News:")
        for i, news in enumerate(result.news_items[:5], 1):  # أول 5
            print(f"\n[{i}] {news['title'][:60]}...")
            print(f"    📁 Category: {news.get('category_name', news.get('category_id', 'N/A'))}")
            print(f"    🏷️ Tags: {news.get('tags', '')[:50]}...")
    else:
        print(f"\n❌ Failed: {result.error_message}")
    
    return result.success


# ============================================
# 🚀 Main
# ============================================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Manual Scraper')
    parser.add_argument('--url', '-u', help='URL to test', default=None)
    parser.add_argument('--test', '-t', 
                       choices=['detector', 'scraper', 'extractor', 'full', 'all'],
                       default='all',
                       help='Which test to run')
    parser.add_argument('--save', '-s', action='store_true', 
                       help='Save to database (default: False)')
    
    args = parser.parse_args()
    
    print("\n" + "🧪"*30)
    print("     MANUAL SCRAPER TEST SUITE")
    print("🧪"*30)
    
    results = {}
    
    try:
        if args.test in ['detector', 'all']:
            results['Source Detector'] = test_source_detector()
        
        if args.test in ['scraper', 'all']:
            results['Web Scraper'] = test_web_scraper(args.url)
        
        if args.test in ['extractor', 'all']:
            results['Content Extractor'] = test_content_extractor()
        
        if args.test in ['full', 'all']:
            results['Full Pipeline'] = test_full_pipeline(args.url, args.save)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # ملخص النتائج
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test_name}: {status}")
    print("="*60)