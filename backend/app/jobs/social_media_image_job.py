#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🎨 Social Media Image Generation Job
يولد صور السوشال ميديا للتقارير الجديدة
محدود بـ 4 تقارير فقط في كل دورة
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
    import os
    
    # Get batch size from environment variable
    batch_size = int(os.getenv('MAX_SOCIAL_IMAGES_PER_RUN', 4))
    
    logger.info(f"🎨 Starting Social Media Image Generation Job for Published Reports (max {batch_size} reports)")
    
    generator = None
    try:
        generator = SocialImageGenerator()
        
        # Generate Facebook images for reports
        stats = generator.generate_for_all_reports(
            force_update=False,  # فقط التقارير الجديدة بدون صور فيسبوك
            limit=batch_size
        )
        
        logger.info(f"🎨 Facebook Images Job completed: {stats}")
        
        return {
            'success': True,
            'stats': stats,
            'message': f"Generated Facebook images for {stats['success']} published reports (max {batch_size} per run)"
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