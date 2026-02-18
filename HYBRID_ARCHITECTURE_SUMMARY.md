# 🏗️ Hybrid Architecture — ملخص التغييرات

> **التاريخ:** 2026-02-18  
> **الهدف:** تحويل النظام من Sequential Pipeline إلى Hybrid Architecture (معالجة فورية + مجدولة)

---

## 🔄 كيف يشتغل النظام الآن

```
┌─────────────────────────────────────────────────────────┐
│                   HYBRID ARCHITECTURE                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [Cron - كل X دقيقة]          worker.py               │
│    └── scrape_news()                                    │
│          ├── يحفظ الأخبار في raw_news                  │
│          └── يضيف IDs → news_pipeline_queue            │
│                              (stage: clustering)        │
│                                    │                    │
│  [Real-time - فوري]                ▼                    │
│    clustering-worker  ──► report-worker ──► image-worker│
│         ✅ done                                         │
│                                                         │
│  [Cron - كل X ساعة]           worker.py               │
│    └── broadcast_generation()                           │
│          └── يولّد البث من التقارير المكتملة           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 الملفات المُنشأة والمُعدَّلة

---

### 🆕 ملفات جديدة

#### 1. `backend/db_migrations/add_news_pipeline_queue.sql`
جدول `news_pipeline_queue` لإدارة الـ real-time pipeline:

| العمود | النوع | الوصف |
|--------|-------|-------|
| `id` | BIGSERIAL | Primary Key |
| `news_id` | BIGINT | FK → raw_news |
| `stage` | TEXT | `clustering` / `report_generation` / `image_generation` |
| `status` | TEXT | `pending` / `running` / `done` / `failed` |
| `attempt_count` | INT | عدد المحاولات |
| `locked_at` | TIMESTAMP | وقت القفل (للـ worker النشط) |
| `next_run_at` | TIMESTAMP | وقت التنفيذ القادم (backoff) |

**مميزات:**
- ✅ Unique Constraint: خبر واحد في مرحلة واحدة فقط
- ✅ Indexes للأداء
- ✅ Trigger لتحديث `updated_at`
- ✅ View `v_pipeline_queue_stats` للمراقبة

---

#### 2. `backend/pipeline_queue_workers.py`
Workers للـ real-time pipeline:

```bash
# تشغيل worker واحد
python pipeline_queue_workers.py --stage clustering
python pipeline_queue_workers.py --stage report_generation
python pipeline_queue_workers.py --stage image_generation

# تشغيل الكل معاً (للتطوير)
python pipeline_queue_workers.py

# أوامر مفيدة
python pipeline_queue_workers.py --stats          # إحصائيات الـ queue
python pipeline_queue_workers.py --reset-stuck    # إعادة المهام العالقة
python pipeline_queue_workers.py --enqueue 123    # إضافة خبر يدوياً
```

**مميزات:**
- ✅ `FOR UPDATE SKIP LOCKED` — لا تعارض بين الـ workers
- ✅ Auto-enqueue للمرحلة التالية بعد النجاح
- ✅ Retry مع backoff: `1min → 5min → 15min`
- ✅ Thread restart تلقائي إذا مات الـ thread

---

### ✏️ ملفات معدَّلة

#### 3. `backend/worker.py` — Cron Worker فقط

| قبل | بعد |
|-----|-----|
| يشغّل: scraping + clustering + report + image + broadcast | يشغّل: **scraping + broadcast فقط** |
| clustering/report/image تشتغل بالـ cron | clustering/report/image انتقلت لـ pipeline_queue_workers |

```python
# job_registry الجديد (worker.py)
{
    'scraping':             scrape_news,           # ✅ يبقى
    'broadcast_generation': generate_all_broadcasts, # ✅ يبقى
    # clustering/report/image → pipeline_queue_workers.py ❌ أُزيلت
}
```

---

#### 4. `backend/app/jobs/scraper_job.py` — يُطلق الـ Pipeline

بعد حفظ الأخبار، يضيفها فوراً للـ queue:

```python
# بعد كل scraping ناجح:
result = scrape_url(url, ...)
if result.saved_ids:
    enqueue_news_for_clustering(result.saved_ids)  # ✅ فوري
```

**دوال جديدة:**
- `enqueue_news_for_clustering(news_ids)` — يضيف الأخبار لـ `news_pipeline_queue`
- `_enqueue_latest_news(limit)` — Safety net fallback (نادراً يُستدعى)

---

#### 5. `backend/app/utils/database.py` — يرجع ID بدل bool

```python
# قبل ❌
def save_news_item(...) -> bool:
    ...
    return True  # أو False

# بعد ✅
def save_news_item(...) -> Optional[int]:
    cursor.execute("INSERT ... RETURNING id", payload)
    new_id = cursor.fetchone()[0]
    return new_id  # الـ ID الحقيقي أو None
```

---

#### 6. `backend/app/services/ingestion/scraper.py` — يجمع الـ IDs

أضفنا `saved_ids` لـ `ScrapeResult`:

```python
@dataclass
class ScrapeResult:
    ...
    saved_ids: List[int] = field(default_factory=list)  # ✅ جديد
```

كل scraper (RSS / Telegram / Web) يجمع الـ IDs الحقيقية:

```python
news_id = save_news_item(news_item, existing_titles)
if news_id:                      # int = نجح
    saved_ids.append(news_id)    # ✅ نجمع الـ ID
```

---

#### 7. `docker-compose.yml` — 4 Services

```yaml
services:
  cron-worker:         # python worker.py
  clustering-worker:   # python pipeline_queue_workers.py --stage clustering
  report-worker:       # python pipeline_queue_workers.py --stage report_generation
  image-worker:        # python pipeline_queue_workers.py --stage image_generation
```

---

#### 8. `render.yaml` — Pipeline Workers على Render

| Service | Plan | الأمر |
|---------|------|-------|
| `production-cron-worker` | starter | `python worker.py` |
| `pipeline-clustering-worker` | starter | `--stage clustering` |
| `pipeline-report-worker` | standard | `--stage report_generation` |
| `pipeline-image-worker` | standard | `--stage image_generation` |

---

## 🚀 خطوات التشغيل

### محلياً (بدون Docker)
```bash
# 1. شغّل الـ migration
psql -d your_db -f backend/db_migrations/add_news_pipeline_queue.sql

# 2. شغّل الـ workers (كل واحد في terminal منفصل)
python worker.py
python pipeline_queue_workers.py --stage clustering
python pipeline_queue_workers.py --stage report_generation
python pipeline_queue_workers.py --stage image_generation
```

### بـ Docker
```bash
docker-compose up
```

### مراقبة الـ Queue
```bash
python pipeline_queue_workers.py --stats
```

---

## ⚠️ ملاحظات مهمة

1. **قبل التشغيل:** لازم تشغّل `add_news_pipeline_queue.sql` أولاً
2. **scheduled_tasks:** تأكد إن `scraping` و `broadcast_generation` موجودين ونشطين في جدول `scheduled_tasks`
3. **clustering/report/image في scheduled_tasks:** إذا كانوا موجودين، عطّلهم بعد ما تتأكد إن الـ queue workers شغّالة:
   ```sql
   UPDATE scheduled_tasks
   SET status = 'inactive'
   WHERE task_type IN ('clustering', 'report_generation', 'image_generation');
   ```
