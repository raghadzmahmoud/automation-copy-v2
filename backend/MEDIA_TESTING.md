# 🎯 Media Testing Guide

## اختبار مكونات الميديا (الصور، الريلز، النشر)

### 🚀 الملفات الجديدة

#### 1. **test_media_worker.py** - وركر اختبار شامل
```bash
# تشغيل دورة واحدة
python test_media_worker.py

# تشغيل مستمر (كل دقيقتين)
python test_media_worker.py --continuous

# اختبار تقرير محدد
python test_media_worker.py --report-id 123

# اختبار الصور فقط
python test_media_worker.py --images-only

# اختبار الريلز فقط
python test_media_worker.py --reels-only

# اختبار النشر فقط
python test_media_worker.py --publishing-only
```

#### 2. **quick_test.py** - اختبار سريع
```bash
# اختبار سريع لكل المكونات
python quick_test.py
```

---

## 🎯 التحسينات المطبقة

### **تقليل الأحمال:**
- ✅ **الريلز**: 4 تقارير بدلاً من 10
- ✅ **الصور**: 4 تقارير بدلاً من 10
- ✅ **معالجة محسنة** للموارد

### **دعم النص العربي:**
- ✅ **خطوط عربية** محسنة مع fallback
- ✅ **معالجة RTL** صحيحة
- ✅ **ربط الحروف** العربية
- ✅ **تحسين للموبايل** (3 كلمات بالسطر)

### **تحسينات Render:**
- ✅ **Dockerfile محسن** مع الخطوط العربية
- ✅ **render.yaml محدث** مع المتغيرات الجديدة
- ✅ **تحميل خطوط تلقائي** من Google Fonts

---

## 📋 خطوات الاختبار

### 1. **اختبار سريع**
```bash
cd backend
python quick_test.py
```

**النتيجة المتوقعة:**
```
⚡ Quick Test - Media Components
======================================================================
🧪 Quick Arabic Test
==================================================
   Original: اختبار سريع للنص العربي
   Processed: يبرعلا صنلا عيرس رابتخا
   ✅ Arabic processing works
   ✅ Font loaded: NotoSansArabic-Regular.ttf

🖼️  Quick Image Test
==================================================
   Reports processed: 1
   Successful: 1
   ✅ Image generation works

🎬 Quick Reel Test
==================================================
   Reports processed: 1
   Successful: 1
   ✅ Reel generation works

📤 Quick Publishing Test
==================================================
   Publishing result: {...}
   ✅ Publishing works

======================================================================
📊 Quick Test Results
======================================================================
   Arabic Support       ✅ PASS
   Image Generation     ✅ PASS
   Reel Generation      ✅ PASS
   Publishing           ✅ PASS

📈 Overall: 4/4 tests passed
🎉 All tests passed! Ready for production
```

### 2. **اختبار شامل**
```bash
cd backend
python test_media_worker.py
```

### 3. **اختبار مستمر**
```bash
cd backend
python test_media_worker.py --continuous
```

---

## 🔧 إعدادات Render المحدثة

### **render.yaml الجديد:**
```yaml
envVars:
  # Enhanced Worker Configuration
  - key: REEL_BATCH_SIZE
    value: "4"
  - key: IMAGE_BATCH_SIZE
    value: "4"
  
  # Arabic Font Support
  - key: FONTCONFIG_PATH
    value: /etc/fonts
  - key: FC_LANG
    value: ar
  
  # Optimized Timeouts
  - key: IMAGES_TIMEOUT
    value: "600"
  - key: VIDEO_TIMEOUT
    value: "900"
  - key: BROADCAST_TIMEOUT
    value: "600"
```

### **Dockerfile.worker المحسن:**
```dockerfile
# Arabic fonts installation
RUN apt-get update && apt-get install -y \
    fonts-noto \
    fonts-noto-arabic \
    fontconfig \
    && fc-cache -fv

# Copy Arabic fonts
COPY fonts/ ./fonts/

# Enhanced environment variables
ENV FONTCONFIG_PATH=/etc/fonts
ENV FC_LANG=ar
ENV REEL_BATCH_SIZE=4
```

---

## 🐛 استكشاف الأخطاء

### **مشاكل شائعة:**

#### 1. **النص العربي معكوس**
```bash
# تحقق من المكتبات
python -c "import arabic_reshaper, bidi; print('OK')"

# اختبار المعالجة
python quick_test.py
```

#### 2. **الخطوط لا تحمل**
```bash
# تحقق من الخطوط المتاحة
fc-list | grep -i noto

# اختبار تحميل الخط
python -c "
from PIL import ImageFont
import os
paths = ['fonts/NotoSansArabic-Regular.ttf', '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf']
for p in paths:
    if os.path.exists(p):
        font = ImageFont.truetype(p, 48)
        print(f'✅ {p}')
        break
"
```

#### 3. **مشاكل في الريلز**
```bash
# اختبار الريلز فقط
python test_media_worker.py --reels-only

# اختبار تقرير محدد
python test_media_worker.py --report-id 123
```

#### 4. **مشاكل في النشر**
```bash
# اختبار النشر فقط
python test_media_worker.py --publishing-only

# تحقق من المتغيرات
python -c "
import os
keys = ['FB_GAZA_ACCESS_TOKEN', 'TG_BOT_TOKEN', 'AWS_ACCESS_KEY_ID']
for key in keys:
    print(f'{key}: {\"✅\" if os.getenv(key) else \"❌\"}')"
```

---

## 📊 مراقبة الأداء

### **مؤشرات مهمة:**
- **معدل نجاح الصور**: يجب أن يكون > 80%
- **معدل نجاح الريلز**: يجب أن يكون > 70%
- **وقت معالجة الصور**: < 2 دقيقة لكل 4 تقارير
- **وقت معالجة الريلز**: < 5 دقائق لكل 4 تقارير

### **لوجز مهمة:**
```
✅ Using Arabic font: NotoSansArabic-Regular.ttf
✅ Processed 3 lines with Arabic RTL support
✅ Generated 2 images
✅ Reel generated successfully
```

### **لوجز تحذيرية:**
```
⚠️  Using default font - Arabic may not render correctly
⚠️  No reports need images
⚠️  Font download fallback activated
```

---

## 🚀 النشر على Render

### **خطوات النشر:**

1. **تحديث الكود:**
```bash
git add .
git commit -m "Enhanced Arabic support + reduced batch sizes"
git push origin main
```

2. **تحديث render.yaml:**
   - ✅ تم تحديثه مع المتغيرات الجديدة
   - ✅ تم تحسين الـ timeouts
   - ✅ تم إضافة دعم الخطوط العربية

3. **مراقبة النشر:**
   - تحقق من لوجز البناء
   - تأكد من تثبيت الخطوط العربية
   - راقب أول دورة تشغيل

4. **اختبار بعد النشر:**
```bash
# مراقبة اللوجز
# تحقق من النص العربي في الصور/الريلز
# تأكد من معالجة 4 تقارير فقط
```

---

## ✅ قائمة التحقق

### **قبل النشر:**
- [ ] `python quick_test.py` يمر بنجاح
- [ ] `python test_media_worker.py` يعمل بدون أخطاء
- [ ] النص العربي يظهر بالاتجاه الصحيح
- [ ] الخطوط العربية تحمل بنجاح
- [ ] متغيرات البيئة محدثة في Render

### **بعد النشر:**
- [ ] Worker يبدأ بدون أخطاء
- [ ] الخطوط العربية مثبتة في Container
- [ ] معالجة 4 تقارير فقط في كل دورة
- [ ] النص العربي صحيح في الصور والريلز
- [ ] النشر يعمل بدون مشاكل

---

*آخر تحديث: يناير 2026*