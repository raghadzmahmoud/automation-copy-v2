#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🚀 URL Scraper - Command Line Tool
سحب الأخبار من أي رابط وحفظها في الـ Database

Usage:
    python scrape_url.py <URL>
    python scrape_url.py <URL> --max 10
    python scrape_url.py <URL> --no-save
    
Examples:
    python scrape_url.py "https://www.example.com/news"
    python scrape_url.py "https://www.example.com" --max 5
    python scrape_url.py "https://www.example.com" --no-save --max 3
"""

import sys
import os
import argparse

# إضافة المسار
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(
        description='📥 سحب الأخبار من رابط وحفظها في الـ Database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scrape_url.py "https://www.example.com/news"
  python scrape_url.py "https://www.example.com" --max 5
  python scrape_url.py "https://www.example.com" --no-save
        """
    )
    
    parser.add_argument(
        'url',
        help='الرابط المراد سحب الأخبار منه'
    )
    
    parser.add_argument(
        '--max', '-m',
        type=int,
        default=10,
        help='الحد الأقصى لعدد الأخبار (افتراضي: 10)'
    )
    
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='عدم الحفظ في الـ Database (للاختبار فقط)'
    )
    
    parser.add_argument(
        '--crawl',
        action='store_true',
        help='إجبار وضع الزحف (لصفحات القوائم)'
    )
    
    parser.add_argument(
        '--single',
        action='store_true',
        help='إجبار وضع الصفحة الواحدة (لمقال واحد)'
    )
    
    parser.add_argument(
        '--lang', '-l',
        type=int,
        default=1,
        help='ID اللغة (افتراضي: 1 = عربي)'
    )
    
    args = parser.parse_args()
    
    # التحقق من الرابط
    if not args.url:
        print("❌ الرجاء إدخال رابط!")
        parser.print_help()
        sys.exit(1)
    
    # استيراد المكونات
    try:
        from app.services.ingestion.manual_scraper import ManualScraper
    except ImportError as e:
        print(f"❌ Error importing modules: {e}")
        print("\nتأكد أنك في مجلد backend وأن جميع الملفات موجودة:")
        print("  - app/services/ingestion/manual_scraper.py")
        print("  - app/services/ingestion/news_crawler.py")
        print("  - app/services/ingestion/content_extractor.py")
        sys.exit(1)
    
    # تشغيل السحب
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    📥 URL News Scraper                       ║
╠══════════════════════════════════════════════════════════════╣
║  URL: {args.url[:50]}{'...' if len(args.url) > 50 else ''}
║  Max Articles: {args.max}
║  Save to DB: {not args.no_save}
║  Language ID: {args.lang}
╚══════════════════════════════════════════════════════════════╝
    """)
    
    scraper = ManualScraper(
        auto_save=not args.no_save,
        max_articles=args.max,
        default_language_id=args.lang
    )
    
    result = scraper.scrape_url(
        url=args.url,
        force_crawl=args.crawl,
        force_single=args.single
    )
    
    # النتيجة
    if result.success:
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                      ✅ SUCCESS                              ║
╠══════════════════════════════════════════════════════════════╣
║  📰 News Extracted: {result.news_extracted}
║  💾 News Saved: {result.news_saved}
║  🕷️ Pages Crawled: {result.pages_crawled}
║  ⏱️ Time: {result.processing_time_seconds:.2f}s
╚══════════════════════════════════════════════════════════════╝
        """)
        
        # عرض الأخبار
        if result.news_items:
            print("\n📋 Extracted News:")
            print("─" * 60)
            for i, news in enumerate(result.news_items[:5], 1):
                print(f"\n[{i}] 📌 {news.get('title', 'No Title')[:60]}...")
                print(f"    📁 Category ID: {news.get('category_id', 'N/A')}")
                print(f"    🏷️ Tags: {news.get('tags', '')[:40]}...")
            
            if len(result.news_items) > 5:
                print(f"\n    ... و {len(result.news_items) - 5} أخبار أخرى")
        
        sys.exit(0)
    else:
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                      ❌ FAILED                               ║
╠══════════════════════════════════════════════════════════════╣
║  Error: {result.error_message[:50] if result.error_message else 'Unknown error'}
╚══════════════════════════════════════════════════════════════╝
        """)
        sys.exit(1)


if __name__ == "__main__":
    main()