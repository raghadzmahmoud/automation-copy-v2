#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 Test Social Media Generator
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from app.services.social_media_generator import SocialMediaGenerator, SocialMediaContent


def test_format_output():
    """اختبار التنسيق فقط"""
    print("="*70)
    print("🧪 TEST: Social Media Content Format")
    print("="*70)
    
    test_content = {
        'facebook': SocialMediaContent(
            title="تطورات جديدة في غزة",
            content="🔴 عاجل: تصاعد الأحداث...\n\n#فلسطين #غزة #أخبار",
            platform='facebook'
        ),
        'twitter': SocialMediaContent(
            title="غزة تحت النار",
            content="🚨 عاجل من غزة...\n\n#غزة #فلسطين",
            platform='twitter'
        )
    }
    
    json_content = {}
    for platform, content in test_content.items():
        json_content[platform] = content.to_dict()
    
    formatted_json = json.dumps(json_content, ensure_ascii=False, indent=2)
    
    print("\n📝 JSON OUTPUT:")
    print(formatted_json)
    
    print("\n🎨 FRONTEND CODE:")
    print("""
const socialMedia = JSON.parse(response.content);
const facebook = socialMedia.facebook;
const twitter = socialMedia.twitter;
console.log(facebook.title, facebook.content);
""")
    print("\n✅ Test completed!")


def test_with_real_report(report_id: int):
    """اختبار مع تقرير حقيقي"""
    print("="*70)
    print(f"🧪 TEST: Generate for Real Report #{report_id}")
    print("="*70)
    
    try:
        generator = SocialMediaGenerator()
        
        result = generator.generate_for_report(
            report_id=report_id,
            platforms=['facebook', 'twitter', 'instagram'],
            force_update=False
        )
        
        print("\n📊 RESULT:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        if result.get('success') and not result.get('skipped'):
            content = generator._get_existing_content(report_id)
            
            if content:
                print("\n💾 SAVED CONTENT:")
                parsed = json.loads(content['content'])
                print(json.dumps(parsed, ensure_ascii=False, indent=2))
        
        generator.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ Test completed!")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        test_with_real_report(int(sys.argv[1]))
    else:
        test_format_output()