-- ✅ Task 1: إضافة أعمدة مهمة في scheduled_tasks
-- Migration to add required columns for production job runner

-- Add new columns for proper scheduling and locking
ALTER TABLE scheduled_tasks 
ADD COLUMN IF NOT EXISTS next_run_at TIMESTAMP NULL,
ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP NULL,
ADD COLUMN IF NOT EXISTS locked_by TEXT NULL,
ADD COLUMN IF NOT EXISTS fail_count INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_status TEXT NULL,
ADD COLUMN IF NOT EXISTS max_concurrent_runs INT DEFAULT 1;

-- ✅ Task 2: Indexes للأداء
-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_due 
ON scheduled_tasks (status, next_run_at);

CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_lock 
ON scheduled_tasks (locked_at);

CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_type_status 
ON scheduled_tasks (task_type, status);

-- ✅ Task 3: تعديل جدول logs (اختياري لكن مهم)
-- Add timing columns to logs
ALTER TABLE scheduled_task_logs 
ADD COLUMN IF NOT EXISTS started_at TIMESTAMP NULL,
ADD COLUMN IF NOT EXISTS finished_at TIMESTAMP NULL,
ADD COLUMN IF NOT EXISTS locked_by TEXT NULL;

-- Update existing tasks to have next_run_at if NULL
UPDATE scheduled_tasks 
SET next_run_at = COALESCE(last_run_at, NOW()) 
WHERE next_run_at IS NULL AND status = 'active';

-- Set initial status for existing tasks
UPDATE scheduled_tasks 
SET last_status = 'ready' 
WHERE last_status IS NULL;

-- ✅ Optimize concurrency settings for content generation + social media
-- Allow multiple concurrent runs for tasks that can run in parallel
UPDATE scheduled_tasks 
SET max_concurrent_runs = CASE 
    WHEN task_type = 'report_generation' THEN 3
    WHEN task_type = 'social_media_generation' THEN 2
    WHEN task_type = 'image_generation' THEN 2
    WHEN task_type = 'audio_generation' THEN 2
    WHEN task_type = 'audio_transcription' THEN 3
    WHEN task_type = 'clustering' THEN 1
    WHEN task_type = 'scraping' THEN 1
    WHEN task_type = 'broadcast_generation' THEN 1
    WHEN task_type = 'bulletin_generation' THEN 1
    WHEN task_type = 'digest_generation' THEN 1
    WHEN task_type = 'processing_pipeline' THEN 1
    ELSE 1
END
WHERE max_concurrent_runs = 1;

-- Remove only reel generation and publishing tasks (keep social_media_generation)
UPDATE scheduled_tasks 
SET status = 'inactive'
WHERE task_type IN (
    'social_media_image_generation', 
    'reel_generation',
    'telegram_publishing',
    'facebook_publishing',
    'instagram_publishing'
);

COMMIT;