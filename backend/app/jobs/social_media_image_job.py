#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎨 Social Media Image Generation Job
يولد صور السوشال ميديا للتقارير الجديدة
"""

import logging
from app.services.generators.social_media_image_generator import SocialImageGenerator

logger = logging.getLogger(__name__)


def generate_social_media_images():
    """
    Job function للـ Social Media Image Generation
    يولد صور فيسبوك للتقارير المنشورة (published)
    
    الأولوية للصور:
    1. Generated image (content_type_id = 6)
    2. Raw news image من الـ cluster
    """
    logger.info("🎨 Starting Social Media Image Generation Job for Published Reports")
    
    generator = None
    try:
        generator = SocialImageGenerator()
        
        # Generate Facebook images for reports
        # limit=10 لمعالجة المزيد من التقارير في كل run
        stats = generator.generate_for_all_reports(
            force_update=False,  # فقط التقارير الجديدة بدون صور فيسبوك
            limit=10
        )
        
        logger.info(f"🎨 Facebook Images Job completed: {stats}")
        
        return {
            'success': True,
            'stats': stats,
            'message': f"Generated Facebook images for {stats['success']} published reports"
        }
        
    except Exception as e:
        logger.error(f"🎨 Facebook Images Job failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }
    
    finally:
        if generator:
            generator.close()


if __name__ == "__main__":
    # للاختبار المباشر
    result = generate_social_media_images()
    print(f"Result: {result}")