#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🕷️ News Crawler
الزحف على صفحات الأخبار واستخراج المحتوى من كل صفحة
يستخدم SmartScraper للتعامل مع كل أنواع الصفحات
"""

import time
from typing import List, Optional
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.services.ingestion.smart_scraper import (
    SmartScraper, 
    ScrapeResult, 
    PageType, 
    ContentStatus
)


@dataclass
class NewsArticle:
    """خبر مسحوب"""
    url: str
    title: str
    content: str
    image: str = ""
    published_date: Optional[str] = None
    author: Optional[str] = None


@dataclass 
class CrawlResult:
    """نتيجة الزحف"""
    success: bool
    base_url: str
    domain: str
    
    articles: List[NewsArticle] = field(default_factory=list)
    total_links_found: int = 0
    total_articles_scraped: int = 0
    
    combined_content: str = ""
    all_images: List[str] = field(default_factory=list)
    
    error_message: Optional[str] = None
    failed_urls: List[str] = field(default_factory=list)
    
    crawl_time_seconds: float = 0.0


class NewsCrawler:
    """
    🕷️ News Crawler
    يزحف على صفحة أخبار ويستخرج المحتوى من كل خبر
    """
    
    def __init__(
        self,
        max_articles: int = 10,
        timeout: int = 30,
        delay_between_requests: float = 1.0
    ):
        self.max_articles = max_articles
        self.timeout = timeout
        self.delay = delay_between_requests
        
        # SmartScraper للتعامل مع كل أنواع الصفحات
        self.scraper = SmartScraper(timeout=timeout)
    
    def crawl(self, url: str) -> CrawlResult:
        """الزحف على صفحة أخبار"""
        start_time = time.time()
        domain = self._get_domain(url)
        
        print(f"\n🕷️ Starting crawl: {url}")
        
        try:
            # الخطوة 1: سحب الصفحة الرئيسية
            print(f"   📄 Fetching main page...")
            main_result = self.scraper.scrape(url)
            
            # الخطوة 2: التحقق من نوع الصفحة
            if main_result.page_type == PageType.LISTING or main_result.article_links:
                # صفحة قوائم - استخرج الروابط وازحف عليها
                links = main_result.article_links
                if not links:
                    # جرب استخراج الروابط من الصفحة
                    links = self._extract_links_from_page(url)
                
                return self._crawl_from_links(
                    url, domain, links, start_time
                )
            
            elif main_result.content_status == ContentStatus.FULL:
                # صفحة مقال واحد - أرجعها مباشرة
                print(f"   📰 Single article page detected")
                article = NewsArticle(
                    url=url,
                    title=main_result.title,
                    content=main_result.clean_text,
                    image=main_result.images[0] if main_result.images else "",
                    published_date=main_result.published_date,
                    author=main_result.author
                )
                
                return CrawlResult(
                    success=True,
                    base_url=url,
                    domain=domain,
                    articles=[article],
                    total_links_found=0,
                    total_articles_scraped=1,
                    combined_content=f"# {article.title}\n\n{article.content}",
                    all_images=main_result.images,
                    crawl_time_seconds=time.time() - start_time
                )
            
            else:
                # محتوى فارغ أو جزئي - جرب استخراج روابط
                print(f"   ⚠️ Content insufficient, extracting links...")
                links = self._extract_links_from_page(url)
                
                if links:
                    return self._crawl_from_links(url, domain, links, start_time)
                
                return CrawlResult(
                    success=False,
                    base_url=url,
                    domain=domain,
                    error_message="لم يتم العثور على محتوى أو روابط",
                    crawl_time_seconds=time.time() - start_time
                )
            
        except Exception as e:
            return CrawlResult(
                success=False,
                base_url=url,
                domain=domain,
                error_message=str(e),
                crawl_time_seconds=time.time() - start_time
            )
        finally:
            self.scraper._close_browser()
    
    def _extract_links_from_page(self, url: str) -> List[str]:
        """استخراج الروابط من صفحة"""
        try:
            from bs4 import BeautifulSoup
            
            resp = self.scraper.session.get(url, timeout=self.timeout, verify=False)
            soup = BeautifulSoup(resp.text, 'html.parser')
            return self.scraper._extract_article_links(soup, url)
        except:
            return []
    
    def _crawl_from_links(
        self, 
        base_url: str, 
        domain: str, 
        links: List[str],
        start_time: float
    ) -> CrawlResult:
        """الزحف على قائمة روابط"""
        
        print(f"   🔗 Found {len(links)} article links")
        
        if not links:
            return CrawlResult(
                success=False,
                base_url=base_url,
                domain=domain,
                error_message="لم يتم العثور على روابط مقالات",
                crawl_time_seconds=time.time() - start_time
            )
        
        # سحب المقالات
        articles = []
        failed_urls = []
        all_images = []
        
        links_to_process = links[:self.max_articles]
        print(f"   📥 Scraping {len(links_to_process)} articles...")
        
        for i, link in enumerate(links_to_process, 1):
            try:
                print(f"   [{i}/{len(links_to_process)}] {link[:55]}...")
                
                result = self.scraper.scrape(link)
                
                if result.success and result.content_status != ContentStatus.EMPTY:
                    article = NewsArticle(
                        url=link,
                        title=result.title,
                        content=result.clean_text,
                        image=result.images[0] if result.images else "",
                        published_date=result.published_date,
                        author=result.author
                    )
                    articles.append(article)
                    all_images.extend(result.images)
                    
                    method = "🌐" if result.method_used == "playwright" else "📄"
                    print(f"       {method} ✅ {result.title[:35]}... ({len(result.clean_text)} chars)")
                else:
                    failed_urls.append(link)
                    print(f"       ⚠️ {result.error_message or 'No content'}")
                
                if i < len(links_to_process):
                    time.sleep(self.delay)
                    
            except Exception as e:
                failed_urls.append(link)
                print(f"       ❌ Error: {str(e)[:30]}")
        
        # دمج المحتوى
        combined_content = self._combine_articles(articles)
        
        crawl_time = time.time() - start_time
        
        print(f"\n   ✅ Crawl complete!")
        print(f"   📊 Articles: {len(articles)}/{len(links_to_process)}")
        print(f"   ⏱️ Time: {crawl_time:.2f}s")
        
        return CrawlResult(
            success=len(articles) > 0,
            base_url=base_url,
            domain=domain,
            articles=articles,
            total_links_found=len(links),
            total_articles_scraped=len(articles),
            combined_content=combined_content,
            all_images=all_images[:20],
            failed_urls=failed_urls,
            crawl_time_seconds=crawl_time
        )
    
    def _combine_articles(self, articles: List[NewsArticle]) -> str:
        """دمج المقالات في نص واحد"""
        parts = []
        
        for i, article in enumerate(articles, 1):
            part = f"""
═══════════════════════════════════════
📰 خبر رقم {i}
═══════════════════════════════════════
العنوان: {article.title}
الرابط: {article.url}
{'التاريخ: ' + article.published_date if article.published_date else ''}

المحتوى:
{article.content}
"""
            parts.append(part)
        
        return '\n'.join(parts)
    
    def _get_domain(self, url: str) -> str:
        """استخراج الدومين"""
        try:
            return urlparse(url).netloc
        except:
            return ""


# ============================================
# 🚀 Helper Function
# ============================================

def crawl_news_site(url: str, max_articles: int = 10) -> CrawlResult:
    """دالة مختصرة للزحف"""
    crawler = NewsCrawler(max_articles=max_articles)
    return crawler.crawl(url)