#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 Test Facebook Video Publishing
اختبار نشر الفيديوهات على الفيسبوك
"""

import sys
import os
import logging

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

from backend.app.services.publishers.facebook_publisher import FacebookPublisher

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


def test_video_publishing(report_id: int):
    """
    اختبار نشر فيديو على الفيسبوك
    
    Args:
        report_id: رقم التقرير
    """
    
    print(f"\n{'='*70}")
    print(f"🧪 Testing Facebook Video Publishing")
    print(f"   Report ID: {report_id}")
    print(f"{'='*70}\n")
    
    # Initialize publisher
    publisher = FacebookPublisher()
    
    # Test video only
    print("🔹 Test 1: Video Only")
    result = publisher.publish_video(report_id)
    
    print(f"\n{'─'*70}")
    print(f"📊 VIDEO ONLY RESULT:")
    print(f"{'─'*70}")
    print(f"Success: {result['success']}")
    if result.get('videos'):
        for v in result['videos']:
            print(f"  {v['page']}: {v['video_id']}")
    else:
        print(f"Error: {result.get('message', 'Unknown')}")
    print(f"{'─'*70}\n")
    
    return result


def test_both_publishing(report_id: int):
    """
    اختبار نشر بوست + فيديو سوا
    
    Args:
        report_id: رقم التقرير
    """
    
    print(f"\n{'='*70}")
    print(f"🧪 Testing Facebook Post + Video Publishing")
    print(f"   Report ID: {report_id}")
    print(f"{'='*70}\n")
    
    # Initialize publisher
    publisher = FacebookPublisher()
    
    # Test both
    print("🔹 Test 2: Post + Video")
    result = publisher.publish_both(report_id)
    
    print(f"\n{'─'*70}")
    print(f"📊 BOTH RESULT:")
    print(f"{'─'*70}")
    print(f"Overall Success: {result['success']}")
    print(f"\nPost:")
    print(f"  Success: {result['post']['success']}")
    if result['post'].get('posts'):
        for p in result['post']['posts']:
            print(f"    {p['page']}: {p['post_id']}")
    
    print(f"\nVideo:")
    print(f"  Success: {result['video']['success']}")
    if result['video'].get('videos'):
        for v in result['video']['videos']:
            print(f"    {v['page']}: {v['video_id']}")
    print(f"{'─'*70}\n")
    
    return result


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_facebook_video.py <report_id> [test_type]")
        print("  test_type: 'video' (default) or 'both'")
        sys.exit(1)
    
    report_id = int(sys.argv[1])
    test_type = sys.argv[2] if len(sys.argv) > 2 else 'video'
    
    if test_type == 'both':
        result = test_both_publishing(report_id)
    else:
        result = test_video_publishing(report_id)
    
    print(f"\n{'='*70}")
    print(f"✅ Test Complete!")
    print(f"{'='*70}\n")
