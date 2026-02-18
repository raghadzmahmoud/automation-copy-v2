-- ═══════════════════════════════════════════════════════════════
-- 🚀 Migration: Trigger Function for news_pipeline_queue
-- ═══════════════════════════════════════════════════════════════

DROP FUNCTION IF EXISTS update_news_pipeline_queue_updated_at() CASCADE;

CREATE FUNCTION update_news_pipeline_queue_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_npq_updated_at
    BEFORE UPDATE ON news_pipeline_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_news_pipeline_queue_updated_at();

COMMIT;
