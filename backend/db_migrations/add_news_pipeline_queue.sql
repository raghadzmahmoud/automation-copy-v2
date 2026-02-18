-- ═══════════════════════════════════════════════════════════════
-- 🚀 Migration: news_pipeline_queue
-- ═══════════════════════════════════════════════════════════════
-- Queue Table للـ real-time pipeline stages:
--   clustering → report_generation → image_generation
--
-- كل خبر جديد يدخل clustering فوراً بعد الـ scraping
-- ثم يتحول تلقائياً لـ report_generation ثم image_generation
-- ═══════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────
-- 1) جدول الـ Queue
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS news_pipeline_queue (
    id              BIGSERIAL PRIMARY KEY,

    -- الخبر المرتبط (NULL مسموح لأن clustering قد يشتغل على batch)
    news_id         BIGINT REFERENCES raw_news(id) ON DELETE CASCADE,

    -- المرحلة الحالية
    stage           TEXT NOT NULL CHECK (stage IN ('clustering', 'report_generation', 'image_generation')),

    -- الحالة
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'done', 'failed')),

    -- Retry
    attempt_count   INT NOT NULL DEFAULT 0,
    max_attempts    INT NOT NULL DEFAULT 3,

    -- Locking (للـ FOR UPDATE SKIP LOCKED)
    locked_at       TIMESTAMP WITH TIME ZONE NULL,
    locked_by       TEXT NULL,

    -- Scheduling
    next_run_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- نتائج
    result          TEXT NULL,
    error_message   TEXT NULL,

    -- Timestamps
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMP WITH TIME ZONE NULL,
    finished_at     TIMESTAMP WITH TIME ZONE NULL,
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- 2) Unique Constraint: خبر واحد في مرحلة واحدة فقط
-- ─────────────────────────────────────────────────────────────
-- يمنع تكرار نفس الخبر في نفس المرحلة
CREATE UNIQUE INDEX IF NOT EXISTS uq_news_pipeline_queue_news_stage
    ON news_pipeline_queue (news_id, stage)
    WHERE status NOT IN ('done', 'failed');

-- ─────────────────────────────────────────────────────────────
-- 3) Indexes للأداء
-- ─────────────────────────────────────────────────────────────

-- الأهم: جلب المهام المستحقة
CREATE INDEX IF NOT EXISTS idx_npq_pending_stage
    ON news_pipeline_queue (stage, status, next_run_at)
    WHERE status = 'pending';

-- للـ locking
CREATE INDEX IF NOT EXISTS idx_npq_locked
    ON news_pipeline_queue (locked_at)
    WHERE locked_at IS NOT NULL;

-- للبحث بالخبر
CREATE INDEX IF NOT EXISTS idx_npq_news_id
    ON news_pipeline_queue (news_id);

-- للـ monitoring
CREATE INDEX IF NOT EXISTS idx_npq_status_created
    ON news_pipeline_queue (status, created_at);

-- ─────────────────────────────────────────────────────────────
-- 4) Trigger: تحديث updated_at تلقائياً
-- ─────────────────────────────────────────────────────────────
-- Note: Function will be created separately due to parsing issues
-- DROP FUNCTION IF EXISTS update_news_pipeline_queue_updated_at() CASCADE;
-- CREATE FUNCTION update_news_pipeline_queue_updated_at()
-- RETURNS TRIGGER
-- LANGUAGE plpgsql
-- BEGIN
--     NEW.updated_at = NOW();
--     RETURN NEW;
-- END;

DROP TRIGGER IF EXISTS trg_npq_updated_at ON news_pipeline_queue;

-- ─────────────────────────────────────────────────────────────
-- 5) تعطيل clustering/report_generation/image_generation
--    من scheduled_tasks (لأنها صارت queue-based)
-- ─────────────────────────────────────────────────────────────
-- ⚠️  قم بتشغيل هذا فقط بعد تشغيل pipeline_queue_workers.py
-- UPDATE scheduled_tasks
-- SET status = 'inactive'
-- WHERE task_type IN ('clustering', 'report_generation', 'image_generation');

-- ─────────────────────────────────────────────────────────────
-- 6) View للـ monitoring
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_pipeline_queue_stats AS
SELECT
    stage,
    status,
    COUNT(*)                                    AS count,
    MIN(created_at)                             AS oldest,
    MAX(created_at)                             AS newest,
    AVG(EXTRACT(EPOCH FROM (finished_at - started_at)))
        FILTER (WHERE finished_at IS NOT NULL)  AS avg_duration_seconds
FROM news_pipeline_queue
GROUP BY stage, status
ORDER BY stage, status;

COMMENT ON TABLE news_pipeline_queue IS
'Queue للـ real-time pipeline: clustering → report_generation → image_generation.
كل خبر جديد يُضاف هنا بعد الـ scraping ويمر بالمراحل تلقائياً.';

COMMIT;
