# 🚀 Production Job Runner - Complete Guide

## نظرة عامة

تم تطوير نظام Production Job Runner ليحل محل النظام القديم المعتمد على `sleep` بنظام حديث يدعم:

- **Scheduler Service**: يحسب ويحدد المهام المستحقة
- **Multiple Workers**: تنفذ jobs بالتوازي
- **Database Locking**: يمنع تشغيل نفس job مرتين
- **Retry Policy**: إعادة المحاولة مع backoff
- **Health Monitoring**: مراقبة صحة النظام

## 🏗️ Architecture (5 Workers)

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Scheduler     │    │   Worker #1     │    │   Worker #2     │    │   Worker #3     │    │   Worker #4     │    │   Worker #5     │
│                 │    │                 │    │                 │    │                 │    │                 │    │                 │
│ • Calculate     │    │ • Get due task  │    │ • Get due task  │    │ • Get due task  │    │ • Get due task  │    │ • Get due task  │
│   next_run_at   │    │ • Lock task     │    │ • Lock task     │    │ • Lock task     │    │ • Lock task     │    │ • Lock task     │
│ • Clean locks   │    │ • Execute job   │    │ • Execute job   │    │ • Execute job   │    │ • Execute job   │    │ • Execute job   │
│ • Tick every 5s │    │ • Log result    │    │ • Log result    │    │ • Log result    │    │ • Log result    │    │ • Log result    │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │                       │                       │
         └───────────────────────┼───────────────────────┼───────────────────────┼───────────────────────┼───────────────────────┘
                                 │                       │                       │                       │
                    ┌─────────────────────────────────────────────────────────────────────────────────────────┐
                    │                                PostgreSQL Database                                      │
                    │                                                                                         │
                    │ • scheduled_tasks (with max_concurrent_runs per task type)                             │
                    │ • scheduled_task_logs (with worker tracking)                                           │
                    └─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 🚀 Parallel Execution Examples:

**Scenario 1: Peak Content Generation**
- Worker #1: report_generation
- Worker #2: report_generation  
- Worker #3: report_generation
- Worker #4: audio_transcription
- Worker #5: audio_transcription

**Scenario 2: Media Processing**
- Worker #1: image_generation
- Worker #2: image_generation
- Worker #3: audio_generation
- Worker #4: audio_generation
- Worker #5: scraping

**Result: Up to 5x faster content processing!**

## 📋 Database Schema Changes

### New Columns in `scheduled_tasks`:

```sql
-- Scheduling
next_run_at TIMESTAMP NULL          -- متى التشغيل التالي
last_status TEXT NULL               -- آخر حالة (ready, running, completed, failed)

-- Locking
locked_at TIMESTAMP NULL            -- متى تم قفل المهمة
locked_by TEXT NULL                 -- أي worker قفل المهمة

-- Retry Policy
fail_count INT DEFAULT 0            -- عدد المحاولات الفاشلة

-- Concurrency Control
max_concurrent_runs INT DEFAULT 1   -- عدد التشغيل المتزامن المسموح
```

### New Columns in `scheduled_task_logs`:

```sql
started_at TIMESTAMP NULL           -- متى بدأ التنفيذ
finished_at TIMESTAMP NULL          -- متى انتهى التنفيذ
locked_by TEXT NULL                 -- أي worker نفذ المهمة
```

## 🚀 Deployment

### 1. Apply Database Migration

```bash
cd backend
python apply_scheduler_migration.py
```

### 2. Deploy to Render

الـ `render.yaml` محدث ليشمل:

- **production-scheduler**: خدمة الـ scheduler (starter plan)
- **production-worker-1**: worker أول (standard plan)
- **production-worker-2**: worker ثاني (standard plan)
- **production-worker-3**: worker ثالث (standard plan)
- **production-worker-4**: worker رابع (standard plan)
- **production-worker-5**: worker خامس (standard plan)
- **automation-pipeline-worker**: النظام القديم (backup)

**Total: 5 parallel workers for maximum performance!**

### 3. Optimize Concurrency Settings

```bash
# Apply optimized concurrency settings
python optimize_concurrency.py
```

This will set:
- `report_generation`: 3 concurrent runs
- `audio_transcription`: 3 concurrent runs
- `social_media_generation`: 2 concurrent runs
- `image_generation`: 2 concurrent runs
- `audio_generation`: 2 concurrent runs
- `reel_generation`: 2 concurrent runs
- Other tasks: 1 concurrent run (sequential)

### 3. Monitor Health

```bash
# تقرير صحة النظام
python scheduler_health.py

# JSON output للـ API
python scheduler_health.py json

# تنظيف logs قديمة
python scheduler_health.py cleanup 30
```

## ⚙️ Configuration

### Environment Variables

#### Scheduler:
```bash
SCHEDULER_TICK_INTERVAL=5           # كل كم ثانية يحدث الـ scheduler
```

#### Workers:
```bash
WORKER_POLL_INTERVAL=3              # كل كم ثانية يبحث worker عن مهام (أسرع للـ 5 workers)
MAX_RETRY_COUNT=5                   # عدد المحاولات قبل تعطيل المهمة
```

### Concurrency Settings (Optimized for Content Generation):

```python
CONCURRENCY_SETTINGS = {
    'report_generation': 3,           # Up to 3 reports simultaneously
    'audio_transcription': 3,         # Up to 3 audio files simultaneously
    'image_generation': 2,            # Up to 2 images simultaneously
    'audio_generation': 2,            # Up to 2 audio generations
    'scraping': 1,                    # Sequential (coordination needed)
    'clustering': 1,                  # Sequential (needs all data)
    'broadcast_generation': 1,        # Sequential
}
```

### Lock Timeouts (minutes):

```python
LOCK_TIMEOUT_MINUTES = {
    'scraping': 20,
    'clustering': 15,
    'report_generation': 10,
    'social_media_generation': 15,
    'image_generation': 30,
    'audio_generation': 45,
    'reel_generation': 60,
    'broadcast_generation': 20,
    'default': 30
}
```

### Retry Backoff:

```python
RETRY_BACKOFF = {
    1: 1,    # 1st fail → 1 minute
    2: 5,    # 2nd fail → 5 minutes  
    3: 15,   # 3rd fail → 15 minutes
    4: 30,   # 4th fail → 30 minutes
    5: 60,   # 5th fail → 1 hour
}
```

## 🔄 How It Works

### Scheduler Process:

1. **Tick every 5 seconds**
2. **Update next_run_at** for active tasks using cron patterns
3. **Clean expired locks** (tasks locked > timeout)
4. **Log statistics** every minute

### Worker Process:

1. **Poll for due tasks** every 5 seconds
2. **Lock task** using `FOR UPDATE SKIP LOCKED`
3. **Execute job** function
4. **Log result** in `scheduled_task_logs`
5. **Update task** (next_run_at, remove lock)
6. **Handle failures** with retry/backoff

### Database Locking:

```sql
-- Worker gets due task with lock
SELECT id, task_type, schedule_pattern
FROM scheduled_tasks
WHERE status = 'active'
AND next_run_at <= NOW()
AND locked_at IS NULL
ORDER BY next_run_at ASC
LIMIT 1
FOR UPDATE SKIP LOCKED;

-- Lock the task
UPDATE scheduled_tasks
SET locked_at = NOW(),
    locked_by = 'worker-hostname-1234',
    last_status = 'running'
WHERE id = ?;
```

## 📊 Monitoring

### Health Check Endpoint

يمكن إضافة endpoint للـ API:

```python
@router.get("/scheduler/health")
async def scheduler_health():
    from scheduler_health import get_scheduler_health
    return get_scheduler_health()
```

### Key Metrics:

- **Active Tasks**: عدد المهام النشطة
- **Due Tasks**: عدد المهام المستحقة الآن
- **Locked Tasks**: عدد المهام قيد التنفيذ
- **Failed Tasks**: عدد المهام التي فشلت
- **Stuck Tasks**: مهام مقفلة لفترة طويلة

### Log Files:

```
logs/
├── scheduler.log                   # Scheduler logs
├── worker_hostname-1234.log        # Worker #1 logs
└── worker_hostname-5678.log        # Worker #2 logs
```

## 🔧 Troubleshooting

### Common Issues:

#### 1. Tasks Not Running
```bash
# Check if scheduler is updating next_run_at
python scheduler_health.py

# Look for due tasks
SELECT task_type, next_run_at, locked_at 
FROM scheduled_tasks 
WHERE status = 'active' 
AND next_run_at <= NOW();
```

#### 2. Tasks Stuck
```bash
# Check for expired locks
SELECT task_type, locked_by, locked_at,
       EXTRACT(EPOCH FROM (NOW() - locked_at))/60 as locked_minutes
FROM scheduled_tasks
WHERE locked_at IS NOT NULL;

# Manually unlock if needed
UPDATE scheduled_tasks 
SET locked_at = NULL, locked_by = NULL 
WHERE task_type = 'stuck_task_type';
```

#### 3. High Failure Rate
```bash
# Check recent failures
SELECT st.task_type, stl.error_message, stl.executed_at
FROM scheduled_task_logs stl
JOIN scheduled_tasks st ON stl.scheduled_task_id = st.id
WHERE stl.status = 'failed'
ORDER BY stl.executed_at DESC
LIMIT 10;
```

### Manual Operations:

#### Reset Failed Task:
```sql
UPDATE scheduled_tasks 
SET fail_count = 0, 
    last_status = 'ready',
    status = 'active'
WHERE task_type = 'task_name';
```

#### Pause Task:
```sql
UPDATE scheduled_tasks 
SET status = 'paused' 
WHERE task_type = 'task_name';
```

#### Force Run Task:
```sql
UPDATE scheduled_tasks 
SET next_run_at = NOW() - INTERVAL '1 minute'
WHERE task_type = 'task_name';
```

## 🔄 Migration from Old System

### Before Migration:
- النظام القديم: `start_worker_improved.py`
- Sleep-based scheduling (120 seconds)
- Sequential execution
- No proper locking
- No retry policy

### After Migration:
- **Scheduler**: `scheduler.py`
- **Workers**: `worker.py` (multiple instances)
- Tick-based scheduling (5 seconds)
- Parallel execution
- Database locking
- Exponential backoff retry

### Rollback Plan:
إذا حدثت مشاكل، يمكن العودة للنظام القديم:

1. Stop new services on Render
2. Enable `automation-pipeline-worker`
3. Reset `next_run_at` to NULL in database

## 📈 Performance Benefits

### Old System:
- ⏰ Fixed 2-minute cycles
- 🔄 Sequential job execution
- 🚫 No parallel processing
- ⚠️ Risk of job overlap
- 📊 Limited monitoring
- 🐌 **Maximum 1 job at a time**

### New System (5 Workers):
- ⚡ 3-second responsiveness
- 🔄 **Parallel job execution (up to 5 jobs simultaneously)**
- ✅ Safe concurrent processing with database locking
- 🔒 Proper job locking with FOR UPDATE SKIP LOCKED
- 📊 Comprehensive monitoring and health checks
- 🔄 Automatic retry with exponential backoff
- 📈 **Highly scalable (5x faster for parallelizable tasks)**
- 🎯 **Smart concurrency limits per task type**

### 🚀 Real Performance Gains:

| Task Type | Old System | New System | Speed Improvement |
|-----------|------------|------------|-------------------|
| Report Generation | 1 at a time | **3 simultaneously** | **3x faster** |
| Audio Transcription | 1 at a time | **3 simultaneously** | **3x faster** |
| Image Generation | 1 at a time | **2 simultaneously** | **2x faster** |
| Audio Generation | 1 at a time | **2 simultaneously** | **2x faster** |
| News Processing | Sequential | **Parallel pipeline** | **2-3x faster** |

**Overall Content Generation: Up to 5x faster during peak loads!**

## 🎯 Next Steps

1. **Deploy and Monitor**: تشغيل النظام الجديد ومراقبته
2. **Performance Tuning**: تحسين الأداء حسب الحاجة
3. **Add More Workers**: إضافة workers إضافية حسب الحمولة
4. **Advanced Features**: 
   - Job priorities
   - Job dependencies
   - Dynamic scheduling
   - Resource-based scheduling

---

## 📞 Support

للمساعدة أو الاستفسارات:
- تحقق من logs في `logs/` directory
- استخدم `python scheduler_health.py` للتشخيص
- راجع `scheduled_task_logs` table للتفاصيل