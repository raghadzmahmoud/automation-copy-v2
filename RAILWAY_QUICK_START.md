# 🚀 Railway Deployment - Quick Start

## ⚡ خطوات سريعة (5 دقائق)

### 1. تجربة محلية (اختياري)
```bash
cd backend
test_docker_build.bat  # Windows
# أو
./test_docker_build.sh  # Linux/Mac
```

### 2. إنشاء مشروع في Railway
1. [railway.app](https://railway.app) → New Project
2. Deploy from GitHub repo
3. اختر الـ repository

### 3. إعداد Service

**Settings → General:**
- Service Name: `worker`
- Root Directory: `backend`

**Settings → Build:**
- Builder: Dockerfile
- Dockerfile Path: `Dockerfile.worker`

**Settings → Deploy:**
- Start Command: `python worker.py`

### 4. Environment Variables (الأساسية)

اذهب إلى Variables tab:

```bash
# Database
DB_NAME=your_db
DB_USER=your_user
DB_PASSWORD=your_pass
DB_HOST=your_host
DB_PORT=5432

# API
GEMINI_API_KEY=your_key

# S3
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
S3_BUCKET_NAME=your_bucket
AWS_REGION=us-east-1

# Worker (اختياري)
MAX_WORKERS=3
PYTHONPATH=/app
PYTHONUNBUFFERED=1
```

### 5. Deploy!
اضغط Deploy → انتظر 5-10 دقائق

### 6. تحقق
في Logs يجب أن ترى:
```
⚙️ Production Worker Starting
📋 Loaded X job types
🚀 Started worker thread 1/3
💓 Worker alive
```

## ✅ Done!

الـ worker الآن:
- ✅ يشتغل 24/7
- ✅ يعالج الملفات الصوتية تلقائياً
- ✅ Multi-threaded (3 threads)
- ✅ Auto-restart on failure

## 🐛 مشاكل شائعة

**Build fails:**
- تأكد Root Directory = `backend`
- تأكد Dockerfile Path = `Dockerfile.worker`

**Worker not starting:**
- تحقق من Environment Variables
- تأكد من DB credentials

**Jobs not running:**
- تحقق من `scheduled_tasks` في الـ database
- تأكد إن `audio_transcription` task نشط

## 📚 المزيد
شوف `RAILWAY_DEPLOYMENT.md` للتفاصيل الكاملة
