# 🚀 Railway Deployment - Quick Start

## ⚡ خطوات سريعة (5 دقائق)

### 1. تجربة محلية (اختياري)
```bash
# من الـ root directory
docker build -f Dockerfile.worker -t worker-test .

# أو من backend/
cd backend
test_docker_build.bat  # Windows
./test_docker_build.sh  # Linux/Mac
```

### 2. إنشاء مشروع في Railway
1. [railway.app](https://railway.app) → New Project
2. Deploy from GitHub repo
3. اختر الـ repository

### 3. إعداد Service (مهم جداً!)

**الطريقة الأولى: استخدام railway.json (موجود في الـ repo)**
- Railway سيقرأ الإعدادات تلقائياً من `railway.json`
- فقط تأكد إن الملف موجود في الـ root

**الطريقة الثانية: Manual Configuration**

في Service Settings:

**Settings → General:**
- Service Name: `worker`
- Root Directory: **اتركه فاضي** (لا تكتب شي!)

**Settings → Build:**
- Builder: `Dockerfile`
- Dockerfile Path: `Dockerfile.worker`

**Settings → Deploy:**
- Start Command: `python worker.py`

### 4. Environment Variables (الأساسية)

اذهب إلى Variables tab:

```bash
# Database (Required)
DB_NAME=your_db
DB_USER=your_user
DB_PASSWORD=your_pass
DB_HOST=your_host
DB_PORT=5432

# API (Required)
GEMINI_API_KEY=your_key

# S3 (Required)
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
S3_BUCKET_NAME=your_bucket
AWS_REGION=us-east-1

# Worker (Optional - already set in Dockerfile)
MAX_WORKERS=3
PYTHONPATH=/app
PYTHONUNBUFFERED=1
```

### 5. Deploy!
اضغط Deploy → انتظر 5-10 دقائق

### 6. تحقق
في Deployments → View Logs يجب أن ترى:
```
✅ Build complete
⚙️ Production Worker Starting
📋 Loaded X job types
🚀 Started worker thread 1/3
🚀 Started worker thread 2/3
🚀 Started worker thread 3/3
💓 Worker alive
```

## ✅ Done!

الـ worker الآن:
- ✅ يشتغل 24/7
- ✅ يعالج الملفات الصوتية تلقائياً
- ✅ Multi-threaded (3 threads)
- ✅ Auto-restart on failure

## 🐛 مشاكل شائعة

### Build Fails: "requirements.txt not found"

**السبب:** Root Directory مضبوط غلط

**الحل:**
1. اذهب إلى Settings → General
2. Root Directory: **اتركه فاضي** (أو احذف أي قيمة موجودة)
3. Dockerfile Path: `Dockerfile.worker`
4. احفظ وأعد Deploy

### Build Fails: "Dockerfile not found"

**السبب:** Dockerfile Path غلط

**الحل:**
- Dockerfile Path: `Dockerfile.worker` (بدون backend/)

### Worker not starting

**السبب:** Environment Variables ناقصة

**الحل:**
- تحقق من DB credentials
- تأكد من GEMINI_API_KEY موجود
- تأكد من AWS credentials موجودة

### Jobs not running

**السبب:** scheduled_tasks مش نشطة

**الحل:**
```sql
-- تحقق من الـ database
SELECT id, name, task_type, status 
FROM scheduled_tasks 
WHERE task_type = 'audio_transcription';

-- لو مش نشط، فعّله
UPDATE scheduled_tasks 
SET status = 'active' 
WHERE task_type = 'audio_transcription';
```

## 📚 المزيد
شوف `backend/RAILWAY_DEPLOYMENT.md` للتفاصيل الكاملة
