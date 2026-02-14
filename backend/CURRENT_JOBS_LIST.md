# 📋 Current Jobs List - Content Generation + Social Media

## ✅ Active Jobs (8 Types)

### 1. 📥 News Scraping
- **Task Type**: `scraping`
- **Function**: `scrape_news()` from `app.jobs.scraper_job`
- **Purpose**: جمع الأخبار من المصادر المختلفة
- **Schedule**: `*/10 * * * *` (كل 10 دقائق)
- **Max Concurrent**: 1 (تسلسلي)
- **Timeout**: 20 دقيقة

### 2. 🎙️ Audio Transcription (STT)
- **Task Type**: `audio_transcription`
- **Function**: `run_audio_transcription_job()` from `app.jobs.audio_transcription_job`
- **Purpose**: تحويل الملفات الصوتية إلى نص
- **Schedule**: حسب الحاجة (عند رفع ملفات صوتية)
- **Max Concurrent**: 3 (متوازي)
- **Timeout**: 30 دقيقة

### 3. 🔄 News Clustering
- **Task Type**: `clustering`
- **Function**: `cluster_news()` from `app.jobs.clustering_job`
- **Purpose**: تجميع الأخبار المتشابهة
- **Schedule**: `*/10 * * * *` (كل 10 دقائق)
- **Max Concurrent**: 1 (تسلسلي)
- **Timeout**: 15 دقيقة

### 4. 📝 Report Generation
- **Task Type**: `report_generation`
- **Function**: `generate_reports()` from `app.jobs.reports_job`
- **Purpose**: توليد التقارير الإخبارية
- **Schedule**: `*/10 * * * *` (كل 10 دقائق)
- **Max Concurrent**: 3 (متوازي)
- **Timeout**: 10 دقيقة

### 5. 📱 Social Media Generation
- **Task Type**: `social_media_generation`
- **Function**: `generate_social_media_content()` from `app.jobs.social_media_job`
- **Purpose**: توليد محتوى وسائل التواصل الاجتماعي
- **Schedule**: `*/15 * * * *` (كل 15 دقيقة)
- **Max Concurrent**: 2 (متوازي)
- **Timeout**: 15 دقيقة

### 6. 🖼️ Image Generation
- **Task Type**: `image_generation`
- **Function**: `generate_images()` from `app.jobs.image_generation_job`
- **Purpose**: توليد الصور للتقارير
- **Schedule**: `*/15 * * * *` (كل 15 دقيقة)
- **Max Concurrent**: 2 (متوازي)
- **Timeout**: 30 دقيقة

### 7. 🎵 Audio Generation
- **Task Type**: `audio_generation`
- **Function**: `generate_audio()` from `app.jobs.audio_generation_job`
- **Purpose**: توليد الملفات الصوتية للتقارير
- **Schedule**: `*/15 * * * *` (كل 15 دقيقة)
- **Max Concurrent**: 2 (متوازي)
- **Timeout**: 45 دقيقة

### 8. 📻 Broadcast Generation
- **Task Type**: `broadcast_generation`, `bulletin_generation`, `digest_generation`
- **Function**: `generate_all_broadcasts()` from `app.jobs.broadcast_job`
- **Purpose**: توليد النشرة الإخبارية والموجز
- **Schedule**: حسب الحاجة
- **Max Concurrent**: 1 (تسلسلي)
- **Timeout**: 20 دقيقة

## 🗑️ Removed Jobs (Publishing & Reels Only)

### ❌ المهام المحذوفة:
- ~~social_media_image_generation~~ - توليد صور وسائل التواصل
- ~~reel_generation~~ - توليد الريلز
- ~~telegram_publishing~~ - النشر على تيليجرام
- ~~facebook_publishing~~ - النشر على فيسبوك
- ~~instagram_publishing~~ - النشر على انستغرام

### ✅ المهام المحتفظ بها:
- **social_media_generation** - توليد محتوى وسائل التواصل الاجتماعي

## 🔄 Job Execution Flow

### Main Cycle (Sequential):
```
1. 📥 Scraping (جمع الأخبار)
2. 🎙️ Audio Transcription (معالجة الملفات الصوتية)
3. 🔄 Clustering (تجميع الأخبار)
4. 📝 Reports (توليد التقارير)
5. 📱 Social Media Content (توليد محتوى السوشال ميديا)
6. 🖼️ Images (توليد الصور)
7. 🎵 Audio (توليد الصوت)
```

### Broadcast Cycle:
```
📻 Broadcast Generation (النشرة والموجز)
```

## 🚀 Parallel Execution Capabilities

مع 5 workers، يمكن تشغيل:

### سيناريو الذروة:
- **3x Report Generation** متزامنة
- **2x Social Media Generation** متزامنة

### سيناريو المعالجة:
- **2x Image Generation** متزامنة
- **2x Audio Generation** متزامنة
- **1x Scraping**

### الكفاءة المتوقعة:
- **Report Generation**: 3x أسرع
- **Audio Transcription**: 3x أسرع
- **Social Media Generation**: 2x أسرع
- **Image Generation**: 2x أسرع
- **Audio Generation**: 2x أسرع

## 📊 Performance Metrics

### إجمالي المهام النشطة: 8
### إجمالي Workers: 5
### أقصى تشغيل متزامن نظري: 14 jobs
### كفاءة النظام: ~36% (5/14 workers)

## 🎯 Focus Areas

النظام الآن يركز على:
- ✅ **Content Generation** (توليد المحتوى)
- ✅ **News Processing** (معالجة الأخبار)
- ✅ **Social Media Content** (محتوى وسائل التواصل)
- ✅ **Media Generation** (توليد الوسائط)
- ❌ ~~Social Media Publishing~~ (محذوف)
- ❌ ~~Video/Reel Generation~~ (محذوف)

## 🔧 Management Commands

```bash
# عرض المهام الحالية
python manage_scheduler.py list

# عرض الأداء
python monitor_parallel_performance.py

# حذف مهام النشر والريلز (إذا لم تُحذف بعد)
python remove_social_media_tasks.py

# تحسين إعدادات التوازي
python optimize_concurrency.py
```

---

**النظام الآن محسن لتوليد المحتوى + محتوى وسائل التواصل الاجتماعي! 🎉**