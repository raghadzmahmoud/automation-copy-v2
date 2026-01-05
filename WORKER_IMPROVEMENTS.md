# 🚀 Worker Improvements Documentation

## المشكلة الأصلية

النظام الأصلي كان يشتغل **sequential** (بالترتيب)، وإذا job واحد علّق أو أخذ وقت طويل:
- كامل الـ pipeline يتوقف
- الأخبار الجديدة تتراكم  
- Media generation و publishing يتأخروا
- System latency ترتفع بدون إنذار

هاي مشكلة شائعة مع:
- Scraping (مواقع بطيئة)
- Image generation (AI APIs)
- Video/reels processing
- External API calls

## 🔧 الحلول المطبقة

### 1. **Job Timeouts** ⏰
- كل job له timeout محدد
- إذا Job أخذ أكثر من الوقت المحدد، يتقتل تلقائياً
- Timeouts قابلة للتخصيص عبر environment variables

```python
@timeout_job_by_type('scraping')  # 10 دقائق
def scrape_news():
    # job code
    pass
```

### 2. **Parallel Execution** 🔄
- Jobs مستقلة تشتغل مع بعض
- Media generation: images + audio parallel
- Publishing: social images + reels + publishing parallel
- Error isolation: job واحد يفشل ما يأثر على الباقي

### 3. **Better Monitoring** 📊
- إحصائيات مفصلة عن كل job
- Timeout tracking
- Performance metrics
- Enhanced logging

## 📁 الملفات الجديدة

```
backend/
├── start_worker_improved.py          # الـ worker المحسن
├── app/utils/
│   ├── job_timeout.py                # نظام الـ timeouts
│   ├── parallel_executor.py          # تشغيل parallel
│   └── job_queue.py                  # نظام queue متقدم (مستقبلي)
├── switch_worker.py                  # script للتبديل بين الـ workers
├── verify_jobs.py                    # script للتحقق من الـ jobs
├── .env.example                      # template محدث
└── Dockerfile.worker                 # محدث للـ worker الجديد

# Root level
├── docker-compose.yml                # للتطوير المحلي
├── render.yaml                       # محدث للـ deployment
└── WORKER_IMPROVEMENTS.md            # هذا الملف
```

## 📋 الـ Jobs المضمنة

### الـ Jobs الأساسية:
- **scrape_news** - جمع الأخبار (timeout: 10 دق)
- **cluster_news** - تجميع الأخبار (timeout: 3 دق)
- **generate_reports** - توليد التقارير (timeout: 5 دق)
- **generate_social_media_content** - محتوى السوشيال ميديا (timeout: 4 دق)

### الـ Media Jobs:
- **generate_images** - توليد الصور (timeout: 15 دق)
- **generate_audio** - توليد الصوت (timeout: 10 دق)

### الـ Publishing Jobs:
- **generate_social_media_images** - صور السوشيال ميديا (timeout: 15 دق)
- **generate_reels** - توليد الريلز (timeout: 20 دق)
- **publish_to_social_media** - النشر (timeout: 5 دق)

### الـ Broadcast Jobs:
- **generate_all_broadcasts** - كل البثات (موصى به)
- **generate_bulletin_job** - النشرة فقط
- **generate_digest_job** - الموجز فقط

## 🚀 كيفية الاستخدام

### للـ Development المحلي:

```bash
# 1. نسخ الـ environment variables
cp backend/.env.example backend/.env
# عدل الـ .env بالقيم الصحيحة

# 2. تشغيل بـ Docker Compose
docker-compose up worker-improved

# أو تشغيل مباشر
cd backend
python start_worker_improved.py
```

### للـ Production (Render):

```bash
# التبديل للـ worker المحسن
cd backend
python switch_worker.py --mode improved

# تحقق من الحالة
python switch_worker.py --status

# تحقق من الـ jobs
python verify_jobs.py

# Deploy على Render
git add .
git commit -m "Switch to improved worker"
git push
```

## ⚙️ Configuration

### Environment Variables الجديدة:

```bash
# Worker Configuration
WORKER_TYPE=improved
MAX_PARALLEL_JOBS=4
ENABLE_JOB_TIMEOUTS=true
ENABLE_PARALLEL_EXECUTION=true
BROADCAST_MODE=unified              # unified (recommended) or separate

# Job Timeouts (seconds)
SCRAPING_TIMEOUT=600        # 10 دقائق
CLUSTERING_TIMEOUT=180      # 3 دقائق
REPORTS_TIMEOUT=300         # 5 دقائق
SOCIAL_MEDIA_TIMEOUT=240    # 4 دقائق
IMAGES_TIMEOUT=900          # 15 دقيقة
AUDIO_TIMEOUT=600           # 10 دقائق
VIDEO_TIMEOUT=1200          # 20 دقيقة
PUBLISHING_TIMEOUT=300      # 5 دقائق
BROADCAST_TIMEOUT=180       # 3 دقائق
```

## 📊 النتائج المتوقعة

### قبل التحسينات:
- إذا image generation علّق 30 دقيقة → كل شي يتوقف
- Pipeline latency: 30+ دقيقة
- No error isolation
- No monitoring

### بعد التحسينات:
- إذا image generation علّق → يتقتل بعد 15 دقيقة
- باقي الـ jobs تكمل شغل
- Pipeline latency: 10-15 دقيقة max
- Full error isolation
- Detailed monitoring

## 🔄 Job Flow الجديد

```
Cycle كل 10 دقائق:

┌─────────────────────────────────────────┐
│ 1. 📥 Scraping (Sequential)             │
│    └── timeout: 10 min                  │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 2. 🔄 Processing (Sequential)           │
│    ├── Clustering (3 min timeout)       │
│    ├── Reports (5 min timeout)          │
│    └── Social Media (4 min timeout)     │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 3. 🎨 Media (Parallel - 2 workers)      │
│    ├── Images (15 min timeout)          │
│    └── Audio (10 min timeout)           │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 4. 📤 Publishing (Parallel - 3 workers) │
│    ├── Social Images (15 min timeout)   │
│    ├── Reels (20 min timeout)           │
│    └── Publishers (5 min timeout)       │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 5. 📻 Broadcast (Sequential)            │
│    └── timeout: 3 min                   │
└─────────────────────────────────────────┘
```

## 🛠️ Troubleshooting

### إذا job معين يتايم أوت كثير:
```bash
# زيد الـ timeout لهذا الـ job
export IMAGES_TIMEOUT=1800  # 30 دقيقة بدل 15
```

### إذا تحب ترجع للـ worker الأصلي:
```bash
cd backend
python switch_worker.py --mode original
```

### للتحقق من الـ logs:
```bash
# Local
docker-compose logs worker-improved

# Render
# شوف الـ logs من Render dashboard
```

### للتحقق من كل الـ jobs:
```bash
cd backend
python verify_jobs.py
```

## 🔮 المستقبل

### Job Queue System (قريباً):
- Redis-based job queue
- Priority queues
- Retry mechanism
- Distributed workers
- Dead letter queue

### Auto-scaling:
- Dynamic worker count based on load
- Resource monitoring
- Intelligent job scheduling

## 📝 Notes

- الـ worker المحسن backward compatible مع النظام الحالي
- يمكن التبديل بين الـ workers بدون مشاكل
- كل الـ environment variables اختيارية (لها defaults)
- الـ timeouts تقدر تعطلها بـ `ENABLE_JOB_TIMEOUTS=false`
- الـ broadcast mode يمكن تغييره بـ `BROADCAST_MODE=separate` لتشغيل bulletin و digest منفصلين