# 🚀 Railway Deployment Guide

## 📋 Prerequisites

1. Railway account ([railway.app](https://railway.app))
2. PostgreSQL database (Railway or external)
3. Docker installed locally (للتجربة)
4. Environment variables ready

## 🧪 Test Locally First

قبل الـ deployment، جرّب الـ build محلياً:

```bash
cd backend

# Windows
test_docker_build.bat

# Linux/Mac
chmod +x test_docker_build.sh
./test_docker_build.sh
```

إذا نجح الـ build محلياً، جاهز للـ deployment!

## 🔧 Railway Setup

### Method 1: Using Railway Dashboard (Recommended)

#### 1. Create New Project
1. اذهب إلى [railway.app](https://railway.app)
2. اضغط "New Project"
3. اختر "Deploy from GitHub repo"
4. اختر الـ repository

#### 2. Configure Service
في Service Settings:

**Root Directory:**
```
backend
```

**Build:**
- Builder: Dockerfile
- Dockerfile Path: `Dockerfile.worker`

**Deploy:**
- Start Command: `python worker.py`

#### 3. Add Environment Variables

في Railway Dashboard، أضف المتغيرات التالية:

#### 3. Add Environment Variables

اذهب إلى Variables tab وأضف:

**Database (Required):**
```
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=your_database_host
DB_PORT=5432
```

**API Keys (Required):**
```
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.0-flash-exp
```

**AWS S3 (Required):**
```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your_bucket_name
```

**Worker Configuration (Optional):**
```
MAX_WORKERS=3
WORKER_POLL_INTERVAL=5
MAX_RETRY_COUNT=5
LOG_LEVEL=INFO
PYTHONPATH=/app
PYTHONUNBUFFERED=1
```

#### 4. Deploy!
اضغط "Deploy" وانتظر البناء (5-10 دقائق)

### Method 2: Using Railway CLI

```bash
# Install CLI
npm i -g @railway/cli

# Login
railway login

# Link project
cd backend
railway link

# Add environment variables
railway variables set DB_NAME=your_db
railway variables set DB_USER=your_user
# ... etc

# Deploy
railway up
```

## 🔍 Verify Deployment

## 🔍 Verify Deployment

### 1. Check Build Logs
في Railway Dashboard → Deployments → View Logs

يجب أن ترى:
```
✅ Build complete
⚙️ Production Worker Starting
📋 Loaded X job types
🚀 Started worker thread 1/3
🚀 Started worker thread 2/3
🚀 Started worker thread 3/3
💓 Worker alive
```

### 2. Check Runtime Logs
```bash
# Using Railway CLI
railway logs --tail 100

# Or in Dashboard
Deployments → View Logs → Runtime
```

### 3. Test Database Connection
في Railway Shell:
```bash
railway run python -c "from settings import DB_CONFIG; import psycopg2; conn = psycopg2.connect(**DB_CONFIG); print('✅ Connected'); conn.close()"
```

### 4. Check Scheduled Tasks
اتصل بالـ database وشغّل:
```sql
SELECT id, name, task_type, status, next_run_at, last_run_at
FROM scheduled_tasks
WHERE status = 'active'
ORDER BY next_run_at;
```

يجب أن ترى `audio_transcription` task نشط.

## 🐛 Troubleshooting

### Build Fails

**Problem:** `COPY failed: file not found`
**Solution:** تأكد إن Root Directory = `backend`

**Problem:** `requirements.txt not found`
**Solution:** تأكد إن الـ Dockerfile path صحيح: `Dockerfile.worker`

**Problem:** Package installation fails
**Solution:** تحقق من `requirements.txt` وتأكد إن كل الـ packages موجودة

### Worker Not Starting

**Problem:** `ModuleNotFoundError`
**Solution:** تأكد إن `PYTHONPATH=/app` موجود في Environment Variables

**Problem:** `Database connection failed`
**Solution:** تحقق من DB credentials في Variables

**Problem:** `ImportError: google.generativeai`
**Solution:** تأكد إن `GEMINI_API_KEY` موجود

### Jobs Not Executing

**Problem:** Worker running but no jobs execute
**Solution:** 
1. تحقق من `scheduled_tasks` table
2. تأكد إن في tasks بـ status='active'
3. تحقق من `next_run_at` - يجب يكون في الماضي

**Problem:** Audio transcription fails
**Solution:**
1. تحقق من S3 credentials
2. تأكد إن الملفات موجودة في S3
3. تحقق من GEMINI_API_KEY

## 📊 Monitoring

### Check Worker Health
```bash
railway logs --tail 50 | grep "Worker alive"
```

### Check Job Execution
```sql
SELECT task_type, status, started_at, finished_at, error_message
FROM scheduled_task_logs
ORDER BY started_at DESC
LIMIT 20;
```

### Check Pending Audio Files
```sql
SELECT COUNT(*), processing_status
FROM uploaded_files
WHERE file_type = 'audio'
GROUP BY processing_status;
```

## 🚀 Performance Tips

1. **Adjust MAX_WORKERS** based on Railway plan:
   - Starter: 2-3 workers
   - Pro: 3-5 workers
   - Team: 5+ workers

2. **Monitor Memory Usage** in Railway Metrics

3. **Check Execution Times** in logs

4. **Scale if needed:**
   - Vertical: Upgrade Railway plan
   - Horizontal: Add more worker instances

## 📝 Common Commands

```bash
# View logs
railway logs

# View environment variables
railway variables

# Run command in container
railway run <command>

# Restart service
railway restart

# Check status
railway status
```


## 🔍 Monitoring

### Check Worker Health
```bash
railway logs --tail 50 | grep "Worker alive"
```

### Check Job Execution
```sql
SELECT task_type, status, started_at, finished_at, error_message
FROM scheduled_task_logs
ORDER BY started_at DESC
LIMIT 20;
```

### Check Pending Audio Files
```sql
SELECT COUNT(*), processing_status
FROM uploaded_files
WHERE file_type = 'audio'
GROUP BY processing_status;
```

## 🚀 Performance Tips

1. **Adjust MAX_WORKERS** based on Railway plan:
   - Starter: 2-3 workers
   - Pro: 3-5 workers
   - Team: 5+ workers

2. **Monitor Memory Usage** in Railway Metrics

3. **Check Execution Times** in logs

4. **Scale if needed:**
   - Vertical: Upgrade Railway plan
   - Horizontal: Add more worker instances

## 📝 Common Commands

```bash
# View logs
railway logs

# View environment variables
railway variables

# Run command in container
railway run <command>

# Restart service
railway restart

# Check status
railway status
```

## ✅ Success Checklist

- [ ] Docker build succeeds locally
- [ ] Railway project created
- [ ] Root directory set to `backend`
- [ ] All environment variables added
- [ ] Build completes successfully
- [ ] Worker starts and shows "Worker alive"
- [ ] Database connection works
- [ ] Audio transcription task is active
- [ ] Jobs execute successfully
