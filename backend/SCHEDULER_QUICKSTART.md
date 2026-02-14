# 🚀 Production Scheduler - Quick Start (5 Workers)

## 1. Apply Database Migration

```bash
cd backend
python apply_scheduler_migration.py
```

## 2. Optimize Concurrency Settings

```bash
python optimize_concurrency.py
```

This configures optimal parallel execution for content generation:
- 3x report generation simultaneously
- 3x audio transcription simultaneously  
- 2x image/audio generation simultaneously

## 3. Test Locally (Optional)

```bash
python test_scheduler_local.py
```

## 4. Deploy to Render

الـ `render.yaml` محدث ليشمل **6 خدمات**:
- `production-scheduler` (scheduler service)
- `production-worker-1` through `production-worker-5` (5 worker services)

**Result: Up to 5 jobs running simultaneously!**

## 4. Monitor System

```bash
# Health check
python scheduler_health.py

# Management commands
python manage_scheduler.py list              # List all tasks
python manage_scheduler.py health            # Health report
python manage_scheduler.py logs              # Recent logs
python manage_scheduler.py pause scraping    # Pause task
python manage_scheduler.py resume scraping   # Resume task
python manage_scheduler.py run scraping      # Force run now
python manage_scheduler.py unlock scraping   # Unlock stuck task
python manage_scheduler.py reset             # Reset all failures
```

## 5. Key Files

- `scheduler.py` - Scheduler service (calculates next_run_at)
- `worker.py` - Worker service (executes jobs)
- `scheduler_health.py` - Health monitoring
- `manage_scheduler.py` - Management tool

## 6. Architecture

```
Scheduler (1 instance)     Workers (5 instances)
     ↓                           ↓
Calculate next_run_at      Get due tasks with locking
Clean expired locks        Execute jobs in parallel
Tick every 5s             Log results
                          Update next_run_at

🚀 Performance: Up to 5 jobs simultaneously!
```

## 7. Benefits vs Old System

| Old System | New System (5 Workers) |
|------------|------------------------|
| Sleep 120s | Tick 3s |
| Sequential | **5x Parallel** |
| No locking | Database locking |
| No retry | Exponential backoff |
| Limited monitoring | Full health monitoring |
| **1 job max** | **5 jobs simultaneously** |

### 🔥 Real Speed Improvements:
- **Report Generation**: 3x faster (3 simultaneous)
- **Audio Transcription**: 3x faster (3 simultaneous)  
- **Image Generation**: 2x faster (2 simultaneous)
- **Audio Generation**: 2x faster (2 simultaneous)
- **Overall Content Generation**: Up to 5x faster!

## 8. Troubleshooting

```bash
# Check stuck tasks
python manage_scheduler.py health

# View recent failures
python manage_scheduler.py logs --limit 50

# Force run stuck task
python manage_scheduler.py run task_name

# Reset failed tasks
python manage_scheduler.py reset
```

---

**Ready for production!** 🎉