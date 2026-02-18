#!/usr/bin/env python3
"""
🚀 Run Scraper Immediately (No Schedule)
═══════════════════════════════════════════════════════════════
يشغّل الـ scraper فوراً بدون انتظار الـ cron schedule

Usage:
    python run_scraper_now.py
═══════════════════════════════════════════════════════════════
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.jobs.scraper_job import scrape_news

# ─── ألوان للـ terminal ───────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def main():
    print(f"\n{BOLD}{'═' * 70}{RESET}")
    print(f"{BOLD}  🚀 Running Scraper Now (No Schedule){RESET}")
    print(f"{BOLD}{'═' * 70}{RESET}\n")

    try:
        print(f"{BLUE}⏳ Starting scraper...{RESET}\n")
        result = scrape_news()

        print(f"\n{BOLD}{'═' * 70}{RESET}")
        print(f"{GREEN}✅ Scraper completed!{RESET}")
        print(f"{BOLD}{'═' * 70}{RESET}\n")

        if result:
            print(f"{GREEN}📊 Results:{RESET}")
            for key, value in result.items():
                print(f"   {key}: {value}")
        else:
            print(f"{YELLOW}⚠️  No results returned{RESET}")

        print()

    except Exception as e:
        print(f"\n{RED}❌ Error: {e}{RESET}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
