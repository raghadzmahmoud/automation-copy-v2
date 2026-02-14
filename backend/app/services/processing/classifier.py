#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🤖 AI News Classifier
تصنيف الأخبار باستخدام Gemini AI

📍 منطق التصنيف:
- محلي: فقط للأخبار التي تحدث داخل فلسطين
- للأخبار خارج فلسطين: تصنيف حسب الموضوع (اقتصاد، اجتماعي، سياسة، رياضة، إلخ)
- دولي: للأخبار السياسية الدولية والدبلوماسية فقط
"""

import json
import time
from typing import Tuple, List
from google import genai

from settings import GEMINI_API_KEY, GEMINI_MODEL


# تهيئة Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)


# التصنيفات الصالحة
VALID_CATEGORIES = [
    'سياسة', 'اقتصاد', 'رياضة', 'تكنولوجيا', 'صحة',
    'ثقافة', 'محلي', 'دولي', 'عسكري', 'اجتماعي', 'فن', 'تعليم'
]


def classify_with_gemini(
    title: str,
    content: str,
    max_retries: int = 3
) -> Tuple[str, str, List[str], bool]:
    """
    تصنيف الخبر باستخدام Gemini AI
    
    Args:
        title: عنوان الخبر
        content: محتوى الخبر
        max_retries: عدد المحاولات
    
    Returns:
        tuple: (category, tags_string, tags_list, ai_success)
    """
    
    # اقتطاع المحتوى
    content_sample = content[:1800] if len(content) > 1800 else content
    
    prompt = f"""حلل هذا الخبر واستخرج التصنيف والكلمات المفتاحية.

📰 العنوان: {title}
📄 المحتوى: {content_sample}

🎯 المطلوب (JSON فقط):

1. category: اختر واحد فقط من: {VALID_CATEGORIES}

📍 قواعد التصنيف:
- "محلي": فقط للأخبار التي تحدث داخل فلسطين (الضفة الغربية، غزة، القدس، أراضي 48)
- للأخبار خارج فلسطين: اختر التصنيف حسب الموضوع:
  * "سياسة": للأخبار السياسية والدبلوماسية
  * "اقتصاد": للأخبار الاقتصادية والمالية
  * "اجتماعي": للأخبار الاجتماعية والمجتمعية
  * "رياضة": للأخبار الرياضية
  * "صحة": للأخبار الصحية والطبية
  * "تكنولوجيا": للأخبار التقنية
  * "دولي": للأخبار السياسية الدولية والعلاقات الدولية فقط
  
2. tags: من 5 إلى 10 كلمات مفتاحية (استخدم _ بدل المسافة)

✅ أمثلة:
- خبر في غزة: {{"category": "محلي", "tags": ["غزة", "فلسطين"]}}
- خبر كهرباء في اليمن: {{"category": "اجتماعي", "tags": ["اليمن", "كهرباء"]}}
- خبر اقتصادي في مصر: {{"category": "اقتصاد", "tags": ["مصر", "اقتصاد"]}}
- قمة دولية: {{"category": "دولي", "tags": ["قمة", "دبلوماسية"]}}

❌ لا ترد بأي شيء آخر غير JSON

الرد:"""
    
    # المحاولات المتكررة
    for attempt in range(max_retries):
        try:
            # استدعاء Gemini
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )
            
            result_text = response.text.strip()
            
            # تنظيف الرد
            result_text = result_text.replace('```json', '').replace('```', '').strip()
            result_text = result_text.replace('`', '').strip()
            
            # استخراج JSON
            start_idx = result_text.find('{')
            end_idx = result_text.rfind('}')
            
            if start_idx == -1 or end_idx == -1:
                raise ValueError("No JSON found")
            
            json_str = result_text[start_idx:end_idx+1]
            result = json.loads(json_str)
            
            # استخراج التصنيف
            category = result.get('category', '').strip()
            
            if not category:
                raise ValueError("Empty category")
            
            # تنظيف التصنيف
            category = category.replace('_', ' ')
            
            # محاولة تصحيح التصنيف
            if category not in VALID_CATEGORIES:
                category = _fix_category(category)
            
            # استخراج Tags
            tags = result.get('tags', [])
            if not isinstance(tags, list):
                raise ValueError("Tags not a list")
            
            if len(tags) < 3:
                raise ValueError("Too few tags")
            
            # تنظيف Tags
            cleaned_tags = _clean_tags(tags)
            
            if len(cleaned_tags) < 3:
                raise ValueError("Not enough valid tags")
            
            tags_str = ", ".join(cleaned_tags)
            
            return category, tags_str, cleaned_tags, True
            
        except json.JSONDecodeError:
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            else:
                print(f"      ❌ JSON error after {max_retries} attempts")
        
        except ValueError as e:
            if attempt < max_retries - 1:
                time.sleep(4)
                continue
            else:
                print(f"      ❌ Validation error: {str(e)[:60]}")
        
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(6)
                continue
            else:
                print(f"      ❌ API error: {str(e)[:60]}")
    
    # Fallback classification
    print("      🔄 Using fallback classification...")
    return _fallback_classification(title, content)


def _fix_category(category: str) -> str:
    """محاولة تصحيح التصنيف"""
    category_lower = category.lower()
    
    if any(word in category_lower for word in ['سياس', 'حكوم', 'انتخاب']):
        return 'سياسة'
    elif any(word in category_lower for word in ['اقتصاد', 'مال', 'تجار']):
        return 'اقتصاد'
    elif any(word in category_lower for word in ['رياضة', 'كرة', 'فريق']):
        return 'رياضة'
    elif any(word in category_lower for word in ['تقني', 'تكنولوجيا', 'ذكاء']):
        return 'تكنولوجيا'
    elif any(word in category_lower for word in ['صحة', 'طب', 'مرض']):
        return 'صحة'
    elif any(word in category_lower for word in ['عسكر', 'جيش', 'سلاح']):
        return 'عسكري'
    
    return category


def _clean_tags(tags: List[str]) -> List[str]:
    """تنظيف قائمة Tags"""
    cleaned_tags = []
    
    for tag in tags[:12]:
        tag = str(tag).strip()
        if not tag:
            continue
        
        # استبدال المسافات بـ _
        tag = tag.replace(' ', '_')
        
        # إزالة علامات الترقيم
        tag = tag.replace(',', '').replace('.', '').replace('،', '').replace(':', '')
        
        if len(tag) > 1:
            cleaned_tags.append(tag)
    
    return cleaned_tags


def _fallback_classification(title: str, content: str) -> Tuple[str, str, List[str], bool]:
    """تصنيف بسيط بدون AI"""
    try:
        text_lower = f"{title} {content}".lower()
        
        # أولاً: تحديد إذا كان الخبر في فلسطين
        palestinian_keywords = [
            'فلسطين', 'غزة', 'الضفة', 'القدس', 'رام الله', 'نابلس', 'الخليل', 
            'جنين', 'طولكرم', 'قلقيلية', 'سلفيت', 'أريحا', 'بيت لحم', 'طوباس',
            'الناصرة', 'حيفا', 'يافا', 'عكا', 'الجليل', 'النقب', 'أراضي 48',
            'الاحتلال', 'المستوطنات', 'جيش الاحتلال', 'الاحتلال الإسرائيلي'
        ]
        
        is_palestinian = any(keyword in text_lower for keyword in palestinian_keywords)
        
        # إذا كان في فلسطين → محلي
        if is_palestinian:
            return 'محلي', "", [], False
        
        # إذا كان خارج فلسطين → تصنيف حسب الموضوع
        if any(word in text_lower for word in ['حكومة', 'وزير', 'رئيس', 'انتخاب', 'برلمان', 'دبلوماسية', 'قمة', 'مؤتمر دولي']):
            # تحديد إذا كان سياسة محلية أم دولية
            if any(word in text_lower for word in ['دولي', 'عالمي', 'قمة', 'مؤتمر', 'الأمم المتحدة', 'دبلوماسية']):
                return 'دولي', "", [], False
            else:
                return 'سياسة', "", [], False
        elif any(word in text_lower for word in ['اقتصاد', 'دولار', 'شيكل', 'بنك', 'تجارة', 'مال', 'استثمار', 'بورصة']):
            return 'اقتصاد', "", [], False
        elif any(word in text_lower for word in ['رياضة', 'كرة', 'فريق', 'مباراة', 'لاعب', 'بطولة']):
            return 'رياضة', "", [], False
        elif any(word in text_lower for word in ['جيش', 'عسكري', 'سلاح', 'صاروخ', 'قصف', 'حرب']):
            return 'عسكري', "", [], False
        elif any(word in text_lower for word in ['صحة', 'مرض', 'طب', 'مستشفى', 'علاج', 'دواء']):
            return 'صحة', "", [], False
        elif any(word in text_lower for word in ['تكنولوجيا', 'تقنية', 'ذكاء اصطناعي', 'إنترنت', 'هاتف', 'كمبيوتر']):
            return 'تكنولوجيا', "", [], False
        elif any(word in text_lower for word in ['مجتمع', 'اجتماعي', 'أسرة', 'تعليم', 'كهرباء', 'مياه', 'خدمات']):
            return 'اجتماعي', "", [], False
        elif any(word in text_lower for word in ['ثقافة', 'فن', 'مسرح', 'سينما', 'كتاب', 'معرض']):
            return 'ثقافة', "", [], False
        else:
            return 'سياسة', "", [], False  # افتراضي للأخبار غير المصنفة
            
    except:
        return 'سياسة', "", [], False