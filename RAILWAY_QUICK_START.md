# 🚀 Railway Deployment - Quick Start

## خطوات سريعة للـ Deployment

### 1. تحضير البيئة
```bash
cd backend
python check_deployment_ready.py
```

### 2. إنشاء مشروع في Railway
1. اذهب إلى [railway.app](https://railway.app)
2. أنشئ مشروع جديد
3. اختر "Deploy from GitHub repo"

### 3. إعداد المتغيرات البيئية

في Railway Dashboard → Variables، أضف:

**Database:**
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

**API Keys:**
- `GEMINI_API_KEY`

**AWS S3:**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`
- `AWS_REGION`

### 4. إعداد الـ Service

**Settings → Build:**
- Root Directory: `backend`
- Dockerfile Path: `Dockerfile.worker`

**Settings → Deploy:**
- Start Command: `python worker.py`

### 5. Deploy!
اضغط "Deploy" وانتظر البناء

### 6. تحقق من التشغيل
```bash
# في Railway logs
railway logs --tail 100
```

يجب أن ترى:
```
⚙️ Production Worker Starting
📋 Loaded X job types
💓 Worker alive
```

## ✅ Done!
الـ worker الآن يشتغل ويعالج الملفات الصوتية تلقائياً كل 5 دقائق
