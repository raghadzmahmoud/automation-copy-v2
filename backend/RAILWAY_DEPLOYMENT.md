# 🚀 Railway Deployment Guide

## 📋 Prerequisites

1. Railway account
2. PostgreSQL database (Railway or external)
3. Environment variables ready

## 🔧 Setup Steps

### 1. Create New Project in Railway

```bash
# Install Railway CLI (optional)
npm i -g @railway/cli

# Login
railway login

# Link project
railway link
```

### 2. Configure Environment Variables

في Railway Dashboard، أضف المتغيرات التالية:

#### Database
```
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=your_database_host
DB_PORT=5432
```

#### API Keys
```
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.0-flash-exp
```

#### AWS S3
```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your_bucket_name
```

#### Worker Configuration
```
MAX_WORKERS=3
WORKER_POLL_INTERVAL=5
MAX_RETRY_COUNT=5
LOG_LEVEL=INFO
```

### 3. Deploy

#### Option A: Using Railway CLI
```bash
cd backend
railway up
```

#### Option B: Using Git
```bash
git push railway main
```

#### Option C: Using Railway Dashboard
1. Connect GitHub repository
2. Select `backend` as root directory
3. Railway will auto-detect Dockerfile.worker
4. Click "Deploy"

### 4. Verify Deployment

```bash
# Check logs
railway logs

# Check worker status
railway run python -c "from settings import DB_CONFIG; import psycopg2; print('✅ Connected')"
```


## 🔍 Monitoring

### Check Worker Health
```bash
railway logs --tail 100
```

### Check Database Tasks
```python
# Connect to your database
SELECT id, name, task_type, status, next_run_at, last_run_at
FROM scheduled_tasks
WHERE status = 'active'
ORDER BY next_run_at;
```

### Check Job Logs
```python
SELECT task_type, status, started_at, finished_at, error_message
FROM scheduled_task_logs
ORDER BY started_at DESC
LIMIT 20;
```

## 🐛 Troubleshooting

### Worker not starting
- Check environment variables
- Verify database connection
- Check Railway logs

### Jobs not executing
- Verify scheduled_tasks table has active tasks
- Check worker logs for errors
- Ensure database is accessible

### Audio transcription failing
- Verify GEMINI_API_KEY is set
- Check S3 credentials
- Verify audio files are accessible

## 📊 Performance Tips

1. **Adjust MAX_WORKERS** based on Railway plan
2. **Monitor memory usage** in Railway dashboard
3. **Check job execution times** in logs
4. **Scale vertically** if needed (upgrade Railway plan)
